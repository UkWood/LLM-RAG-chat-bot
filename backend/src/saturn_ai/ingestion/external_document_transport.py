"""Explicit HTTPS/PDF fetch policy and DNS-pinned, bounded transport.

The sole HTTP transport deliberately ignores proxy environment variables.
Every network peer is a literal IP from the validated DNS answer set, while
TLS verification and SNI remain tied to the original allowlisted DNS hostname.
"""
from dataclasses import dataclass
from http.client import HTTPSConnection, HTTPException, IncompleteRead
import ipaddress
import re
import socket
import ssl
import time
from urllib.parse import unquote, urlsplit, urlunsplit


CODES = frozenset({
    "policy_denied", "invalid_url", "dns_or_ssrf_denied", "redirect_denied",
    "network_error", "http_error", "timeout", "size_limit", "invalid_pdf",
    "encrypted_pdf", "parser_error", "page_limit", "resource_limit",
    "ocr_required",
})
_BAD_PERCENT = re.compile(r"%(?![0-9a-fA-F]{2})")
_CONTROL = re.compile(r"[\x00-\x20\x7f]")


class DocumentError(Exception):
    def __init__(self, code: str):
        if code not in CODES:
            raise ValueError("Unrecognized document error code")
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class DocumentFetchPolicy:
    """Default-deny, immutable configuration. Limits cannot exceed v0.1 caps."""

    allowed_hosts: tuple[str, ...] = ()
    allowed_path_prefixes: tuple[str, ...] = ()
    allowed_ports: tuple[int, ...] = (443,)
    max_pdf_bytes: int = 16 * 1024 * 1024
    max_pages: int = 200
    max_text_bytes: int = 2 * 1024 * 1024
    max_page_text_bytes: int = 128 * 1024
    max_decoded_stream_bytes: int = 4 * 1024 * 1024
    max_total_stream_bytes: int = 16 * 1024 * 1024
    worker_ram_bytes: int = 512 * 1024 * 1024
    worker_cpu_seconds: int = 20
    worker_wall_seconds: int = 60
    connect_timeout: int = 10
    read_timeout: int = 20
    download_deadline: int = 60
    max_requests: int = 100
    max_attempts: int = 1

    def __post_init__(self):
        bounds = {
            "max_pdf_bytes": 16 * 1024 * 1024,
            "max_pages": 200,
            "max_text_bytes": 2 * 1024 * 1024,
            "max_page_text_bytes": 2 * 1024 * 1024,
            "max_decoded_stream_bytes": 16 * 1024 * 1024,
            "max_total_stream_bytes": 64 * 1024 * 1024,
            "worker_ram_bytes": 512 * 1024 * 1024,
            "worker_cpu_seconds": 60,
            "worker_wall_seconds": 60,
            "connect_timeout": 10,
            "read_timeout": 20,
            "download_deadline": 60,
            "max_requests": 1000,
        }
        for key, maximum in bounds.items():
            value = getattr(self, key)
            if type(value) is not int or not 0 < value <= maximum:
                raise ValueError("Invalid PDF policy limit: " + key)
        if self.max_attempts != 1 or type(self.max_attempts) is not int:
            raise ValueError("v0.1 deliberately disallows automatic fetch retries")
        if type(self.allowed_hosts) is not tuple or type(self.allowed_path_prefixes) is not tuple:
            raise ValueError("Hosts and prefixes must be explicit immutable tuples")
        if type(self.allowed_ports) is not tuple or not self.allowed_ports:
            raise ValueError("Explicit allowed ports are required")
        if any(type(p) is not int or p != 443 for p in self.allowed_ports):
            raise ValueError("v0.1 permits only the HTTPS default port")
        if len(set(self.allowed_hosts)) != len(self.allowed_hosts):
            raise ValueError("Duplicate allowed hostname")
        for host in self.allowed_hosts:
            if (not isinstance(host, str) or len(host) > 253 or not host or
                    host != host.lower() or host.endswith(".") or
                    not re.fullmatch(r"[a-z0-9][a-z0-9.-]*[a-z0-9]", host) or
                    ".." in host or _is_ip_literal(host)):
                raise ValueError("Invalid exact allowlisted DNS hostname")
        if len(set(self.allowed_path_prefixes)) != len(self.allowed_path_prefixes):
            raise ValueError("Duplicate path prefix")
        for prefix in self.allowed_path_prefixes:
            if (not isinstance(prefix, str) or not prefix.startswith("/") or
                    prefix == "/" or prefix.endswith("/") or "?" in prefix or
                    "#" in prefix or "%" in prefix or "\\" in prefix or
                    _CONTROL.search(prefix) or
                    any(seg in ("", ".", "..") for seg in prefix[1:].split("/"))):
                raise ValueError("Unsafe path prefix; use /ftp, not /ftp/")


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def validate_url(url: str, policy: DocumentFetchPolicy) -> tuple[str, str, int]:
    """Validate URL BEFORE DNS, preserving the exact request path/query bytes."""
    if not isinstance(policy, DocumentFetchPolicy):
        raise TypeError("DocumentFetchPolicy required")
    if (not isinstance(url, str) or not url or len(url) > 8192 or
            url != url.strip() or "\\" in url or _CONTROL.search(url) or
            _BAD_PERCENT.search(url) or url.startswith("//")):
        raise DocumentError("invalid_url")
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port or 443
    except ValueError:
        raise DocumentError("invalid_url") from None
    if (parts.scheme != "https" or not host or not parts.netloc or
            parts.username is not None or parts.password is not None or
            parts.fragment or not parts.path.startswith("/") or
            host.endswith(".") or _is_ip_literal(host) or
            not host.isascii()):
        raise DocumentError("invalid_url")
    if host not in policy.allowed_hosts or port not in policy.allowed_ports:
        raise DocumentError("policy_denied")
    # Reject nested encoding, dot segments and encoded separators BEFORE request.
    for segment in parts.path.split("/"):
        current = segment
        for _ in range(8):
            if (current in (".", "..") or "/" in current or "\\" in current or
                    any(ord(c) < 32 or ord(c) == 127 for c in current)):
                raise DocumentError("invalid_url")
            try:
                decoded = unquote(current, errors="strict")
            except UnicodeDecodeError:
                raise DocumentError("invalid_url") from None
            if decoded == current:
                break
            current = decoded
        else:
            raise DocumentError("invalid_url")
        if current in (".", "..") or "/" in current or "\\" in current:
            raise DocumentError("invalid_url")
    # Match whole segments, not simple string startswith (/ftp is not /ftpX).
    if not any(parts.path == p or parts.path.startswith(p + "/")
               for p in policy.allowed_path_prefixes):
        raise DocumentError("policy_denied")
    if not parts.path.lower().endswith(".pdf") and not unquote(parts.path).lower().endswith(".pdf"):
        raise DocumentError("invalid_url")
    return host, urlunsplit(("", "", parts.path, parts.query, "")), port


def _public_addresses(host: str, port: int) -> tuple[str, ...]:
    try:
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM,
                                     proto=socket.IPPROTO_TCP)
        ips = tuple(sorted({entry[4][0] for entry in answers}))
    except (socket.gaierror, OSError, ValueError):
        raise DocumentError("dns_or_ssrf_denied") from None
    if not ips:
        raise DocumentError("dns_or_ssrf_denied")
    for value in ips:
        try:
            ip = ipaddress.ip_address(value)
        except ValueError:
            raise DocumentError("dns_or_ssrf_denied") from None
        if not ip.is_global or (ip.version == 6 and ip.ipv4_mapped is not None):
            raise DocumentError("dns_or_ssrf_denied")
    return ips


class _PinnedHTTPSConnection(HTTPSConnection):
    def __init__(self, hostname, peer_ip, port, timeout, context):
        super().__init__(hostname, port, timeout=timeout, context=context)
        self._peer_ip = peer_ip

    def connect(self):
        # Numeric IP only: no second DNS lookup after address validation.
        raw = socket.create_connection((self._peer_ip, self.port), self.timeout)
        try:
            if ipaddress.ip_address(raw.getpeername()[0]) != ipaddress.ip_address(self._peer_ip):
                raise DocumentError("dns_or_ssrf_denied")
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


class HTTPSPdfTransport:
    def fetch(self, url: str, policy: DocumentFetchPolicy) -> bytes:
        host, target, port = validate_url(url, policy)
        started = time.monotonic()
        addresses = _public_addresses(host, port)
        if time.monotonic() - started >= policy.download_deadline:
            raise DocumentError("timeout")
        remaining = policy.download_deadline - (time.monotonic() - started)
        conn = _PinnedHTTPSConnection(
            host, addresses[0], port, min(policy.connect_timeout, remaining),
            ssl.create_default_context(),
        )
        try:
            conn.request("GET", target, headers={
                "Host": host, "Accept": "application/pdf",
                "Accept-Encoding": "identity", "Connection": "close",
                "User-Agent": "SaturnExternalDocumentAdapter/0.1",
            })
            response = conn.getresponse()
            if 300 <= response.status < 400:
                raise DocumentError("redirect_denied")
            if response.status != 200:
                raise DocumentError("http_error")
            encoding = response.getheader("Content-Encoding")
            if encoding and encoding.lower().strip() != "identity":
                raise DocumentError("invalid_pdf")
            mime = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
            if mime not in ("application/pdf", "application/octet-stream"):
                raise DocumentError("invalid_pdf")
            transfer = response.getheader("Transfer-Encoding")
            content_length = response.getheader("Content-Length")
            if transfer and (transfer.strip().lower() != "chunked" or content_length):
                raise DocumentError("invalid_pdf")
            expected = None
            if content_length is not None:
                if not content_length.isascii() or not content_length.isdecimal():
                    raise DocumentError("invalid_pdf")
                expected = int(content_length)
                if expected > policy.max_pdf_bytes:
                    raise DocumentError("size_limit")
            blocks = []
            total = 0
            while True:
                remaining = policy.download_deadline - (time.monotonic() - started)
                if remaining <= 0:
                    raise DocumentError("timeout")
                if conn.sock:
                    conn.sock.settimeout(min(policy.read_timeout, remaining))
                chunk = response.read(min(65536, policy.max_pdf_bytes - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > policy.max_pdf_bytes:
                    raise DocumentError("size_limit")
                blocks.append(chunk)
            if expected is not None and total != expected:
                raise DocumentError("invalid_pdf")
            result = b"".join(blocks)
            if not result.startswith(b"%PDF-"):
                raise DocumentError("invalid_pdf")
            return result
        except DocumentError:
            raise
        except (socket.timeout, TimeoutError):
            raise DocumentError("timeout") from None
        except (ssl.SSLError, OSError, HTTPException, IncompleteRead, ValueError):
            raise DocumentError("network_error") from None
        finally:
            conn.close()
