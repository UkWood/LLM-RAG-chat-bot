"""Offline HTTPS transport/SSRF regression tests. Never contact real services."""
import os
import socket
import ssl
import unittest
from unittest.mock import patch, MagicMock
from dataclasses import replace

from saturn_ai.ingestion.external_document_transport import (
    DocumentError, DocumentFetchPolicy, HTTPSPdfTransport,
    _PinnedHTTPSConnection, _public_addresses, validate_url,
)


URL = "https://www.mnppsaturn.ru/ftp/datasheet.pdf?ver=1"
POLICY = DocumentFetchPolicy(
    allowed_hosts=("www.mnppsaturn.ru",),
    allowed_path_prefixes=("/ftp", "/public", "/photos"),
)


class FakeResponse:
    def __init__(self, content=b"%PDF-test", status=200, headers=None):
        self.content = content
        self.status = status
        self.headers = {"Content-Type": "application/pdf",
                        "Content-Length": str(len(content))}
        if headers:
            self.headers.update(headers)
        self.pos = 0

    def getheader(self, name, default=None):
        return self.headers.get(name, default)

    def read(self, size):
        piece = self.content[self.pos:self.pos + size]
        self.pos += len(piece)
        return piece


class FakeConnection:
    instances = []

    def __init__(self, hostname, peer_ip, port, timeout, context):
        self.hostname = hostname
        self.peer_ip = peer_ip
        self.port = port
        self.timeout = timeout
        self.context = context
        self.sock = MagicMock()
        self.response = FakeResponse()
        self.closed = False
        self.request_args = None
        FakeConnection.instances.append(self)

    def request(self, *args, **kwargs):
        self.request_args = (args, kwargs)

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


class TransportTests(unittest.TestCase):
    def setUp(self):
        FakeConnection.instances = []

    def test_exact_host_and_segment_bounded_paths(self):
        host, path, port = validate_url(URL, POLICY)
        self.assertEqual((host, path, port),
                         ("www.mnppsaturn.ru", "/ftp/datasheet.pdf?ver=1", 443))
        for url, code in [
            ("https://evil-www.mnppsaturn.ru/ftp/a.pdf", "policy_denied"),
            ("https://www.mnppsaturn.ru.evil.org/ftp/a.pdf", "policy_denied"),
            ("https://www.mnppsaturn.ru/ftpX/a.pdf", "policy_denied"),
            ("https://www.mnppsaturn.ru/other/a.pdf", "policy_denied"),
            ("http://www.mnppsaturn.ru/ftp/a.pdf", "invalid_url"),
            ("ftp://www.mnppsaturn.ru/ftp/a.pdf", "invalid_url"),
            ("file:///ftp/a.pdf", "invalid_url"),
            ("https://user:password@www.mnppsaturn.ru/ftp/a.pdf", "invalid_url"),
            ("https://www.mnppsaturn.ru:444/ftp/a.pdf", "policy_denied"),
            ("https://127.0.0.1/ftp/a.pdf", "invalid_url"),
            ("https://www.mnppsaturn.ru/ftp/a.pdf#fragment", "invalid_url"),
            ("https://www.mnppsaturn.ru/ftp/../a.pdf", "invalid_url"),
            ("https://www.mnppsaturn.ru/ftp/%252e%252e/a.pdf", "invalid_url"),
            ("https://www.mnppsaturn.ru/ftp/%252Fetc/a.pdf", "invalid_url"),
            ("https://www.mnppsaturn.ru/ftp/%5cetc/a.pdf", "invalid_url"),
            ("https://www.mnppsaturn.ru/ftp/a.pdf%ZZ", "invalid_url"),
        ]:
            with self.subTest(url=url):
                with self.assertRaises(DocumentError) as exc:
                    validate_url(url, POLICY)
                self.assertEqual(exc.exception.code, code)
        self.assertRaises(DocumentError, validate_url, URL, DocumentFetchPolicy())

    def test_policy_limits_and_immutability(self):
        for bad in [
            {"max_pdf_bytes": 0}, {"max_pdf_bytes": 32 * 1024 * 1024},
            {"max_pages": 0}, {"max_text_bytes": -1},
            {"worker_ram_bytes": 1024 * 1024 * 1024},
            {"connect_timeout": 0}, {"read_timeout": 0},
            {"download_deadline": 0}, {"worker_wall_seconds": 0},
            {"max_attempts": 2}, {"max_requests": 0},
            {"allowed_hosts": ("www.mnppsaturn.ru.evil", "www.mnppsaturn.ru.evil")},
            {"allowed_path_prefixes": ("/",)},
            {"allowed_path_prefixes": ("/ftp/",)},
            {"allowed_ports": (80,)},
        ]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    replace(POLICY, **bad)

    def test_private_and_mixed_dns_answers_are_all_denied(self):
        for address in ["127.0.0.1", "10.0.0.2", "169.254.1.1",
                        "192.168.1.1", "0.0.0.0", "::1",
                        "fc00::1", "fe80::1", "::ffff:8.8.8.8"]:
            with self.subTest(ip=address):
                with patch("socket.getaddrinfo", return_value=[
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
                    (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (address, 443)),
                ]):
                    with self.assertRaises(DocumentError) as exc:
                        _public_addresses("www.mnppsaturn.ru", 443)
                    self.assertEqual(exc.exception.code, "dns_or_ssrf_denied")

    def test_dns_failure_and_empty_answers(self):
        for answer in ([], socket.gaierror("bad DNS")):
            with patch("socket.getaddrinfo", side_effect=answer if isinstance(answer, Exception) else None,
                       return_value=answer if isinstance(answer, list) else None):
                with self.assertRaises(DocumentError) as exc:
                    _public_addresses("www.mnppsaturn.ru", 443)
                self.assertEqual(exc.exception.code, "dns_or_ssrf_denied")

    def _fetch_mock(self, response=None, *, request_error=None):
        with patch("saturn_ai.ingestion.external_document_transport._public_addresses",
                   return_value=("8.8.8.8",)), patch(
                       "saturn_ai.ingestion.external_document_transport._PinnedHTTPSConnection",
                       FakeConnection):
            if request_error is not None:
                original = FakeConnection.request
                def failing(instance, *args, **kwargs):
                    raise request_error
                FakeConnection.request = failing
            try:
                if response is not None:
                    # Fake connection is constructed inside .fetch; swap the
                    # response at the class level for this test invocation.
                    old = FakeConnection.getresponse
                    FakeConnection.getresponse = lambda self: response
                try:
                    return HTTPSPdfTransport().fetch(URL, POLICY)
                finally:
                    if response is not None:
                        FakeConnection.getresponse = old
            finally:
                if request_error is not None:
                    FakeConnection.request = original

    def test_dns_pinned_no_proxy_environment_and_https_request(self):
        with patch.dict(os.environ, {"HTTPS_PROXY": "http://127.0.0.1:5555"}):
            content = self._fetch_mock()
        self.assertEqual(content, b"%PDF-test")
        conn = FakeConnection.instances[0]
        self.assertEqual(conn.hostname, "www.mnppsaturn.ru")
        self.assertEqual(conn.peer_ip, "8.8.8.8")
        self.assertEqual(conn.port, 443)
        self.assertTrue(conn.closed)
        self.assertEqual(conn.request_args[0], ("GET", "/ftp/datasheet.pdf?ver=1"))
        self.assertEqual(conn.request_args[1]["headers"]["Host"], conn.hostname)

    def test_redirect_http_mime_encoding_size_length_and_html(self):
        responses = [
            (FakeResponse(status=301), "redirect_denied"),
            (FakeResponse(status=302, headers={"Location": "http://127.0.0.1/"}), "redirect_denied"),
            (FakeResponse(status=500), "http_error"),
            (FakeResponse(headers={"Content-Type": "text/html"}), "invalid_pdf"),
            (FakeResponse(headers={"Content-Encoding": "gzip"}), "invalid_pdf"),
            (FakeResponse(headers={"Content-Length": "99"}), "invalid_pdf"),
            (FakeResponse(headers={"Content-Length": "wrong"}), "invalid_pdf"),
            (FakeResponse(headers={"Transfer-Encoding": "gzip"}), "invalid_pdf"),
            (FakeResponse(headers={"Transfer-Encoding": "chunked"}), "invalid_pdf"),
            (FakeResponse(content=b"<html>bad</html>", headers={"Content-Type": "application/pdf"}), "invalid_pdf"),
        ]
        for response, code in responses:
            with self.subTest(code=code, status=response.status):
                with self.assertRaises(DocumentError) as exc:
                    self._fetch_mock(response)
                self.assertEqual(exc.exception.code, code)
        with patch("saturn_ai.ingestion.external_document_transport._public_addresses",
                   return_value=("8.8.8.8",)), patch(
                       "saturn_ai.ingestion.external_document_transport._PinnedHTTPSConnection",
                       FakeConnection):
            original = FakeConnection.getresponse
            FakeConnection.getresponse = lambda self: FakeResponse(content=b"%PDF-test")
            try:
                with self.assertRaises(DocumentError) as exc:
                    HTTPSPdfTransport().fetch(URL, replace(POLICY, max_pdf_bytes=5))
                self.assertEqual(exc.exception.code, "size_limit")
            finally:
                FakeConnection.getresponse = original

    def test_tls_failure_and_socket_timeout_are_errors(self):
        for failure, code in [
            (ssl.SSLCertVerificationError("bad hostname"), "network_error"),
            (socket.timeout("socket read"), "timeout"),
        ]:
            with self.subTest(code=code):
                with self.assertRaises(DocumentError) as exc:
                    self._fetch_mock(request_error=failure)
                self.assertEqual(exc.exception.code, code)

    def test_dns_rebinding_is_not_a_second_hostname_lookup(self):
        """Raw socket receives numeric reviewed IP; TLS SNI uses original host."""
        raw = MagicMock()
        raw.getpeername.return_value = ("8.8.8.8", 443)
        context = MagicMock()
        context.wrap_socket.return_value = MagicMock()
        connection = _PinnedHTTPSConnection(
            "www.mnppsaturn.ru", "8.8.8.8", 443, 10, context)
        with patch("socket.create_connection", return_value=raw) as connect:
            connection.connect()
        connect.assert_called_once_with(("8.8.8.8", 443), 10)
        context.wrap_socket.assert_called_once_with(raw, server_hostname="www.mnppsaturn.ru")
        raw.getpeername.return_value = ("127.0.0.1", 443)
        with patch("socket.create_connection", return_value=raw):
            with self.assertRaises(DocumentError):
                connection.connect()

    def test_denied_url_never_reaches_network(self):
        with patch("saturn_ai.ingestion.external_document_transport._public_addresses") as dns, patch(
                "saturn_ai.ingestion.external_document_transport._PinnedHTTPSConnection") as conn:
            with self.assertRaises(DocumentError):
                HTTPSPdfTransport().fetch("https://www.mnppsaturn.ru/private/doc.pdf", POLICY)
            dns.assert_not_called()
            conn.assert_not_called()
