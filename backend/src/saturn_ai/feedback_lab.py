"""Stage 5J local-only expert feedback HTTP lab.

One pinned real stand is loaded at startup. Every question calls the already
accepted Stage 4B-5D run_question() with a NEW real local model provider.
There is no production endpoint, fake inference or cloud fallback.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
from pathlib import Path
import re
import secrets
import socket
import subprocess
from threading import BoundedSemaphore
from time import perf_counter
from urllib.parse import parse_qs, urlsplit
import uuid

from .feedback_journal import (
    JournalError, JournalWriteError, MarkdownFeedbackJournal, _valid_text,
)
from .grounding.saturn_local_provider import SaturnLocalClaimProvider, SaturnLocalModelConfig
from .ingestion.github_snapshot_provider import GitHubSnapshotProvider
from .real_corpus_stand import prepare_real_stand, run_question

EXACT_MODEL_ENDPOINT = "http://127.0.0.1:11435/v1/chat/completions"
MAX_HTTP_BODY = 20000
_ID = re.compile(r"^[a-f0-9]{32}$")


def _code_revision() -> str:
    repo = Path(__file__).resolve().parents[3]
    try:
        run = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True,
                             capture_output=True, text=True, timeout=5)
        value = run.stdout.strip()
        if re.fullmatch(r"[0-9a-f]{40}", value):
            return value
    except (OSError, subprocess.SubprocessError):
        pass
    raise RuntimeError("code_revision_unavailable")


class FeedbackLabService:
    """Independent of HTTP; exposed lab operations write the journal first."""

    def __init__(self, *, stand, journal: MarkdownFeedbackJournal,
                 model_config: SaturnLocalModelConfig, run_id: str,
                 code_revision: str, question_runner=run_question):
        if model_config.endpoint != EXACT_MODEL_ENDPOINT:
            raise ValueError("lab_model_endpoint_must_be_exact_loopback")
        if not re.fullmatch(r"[0-9a-f]{40}", code_revision):
            raise ValueError("invalid_code_revision")
        if not re.fullmatch(r"[0-9a-f]{32}", run_id):
            raise ValueError("invalid_experiment_run_id")
        self.stand = stand
        self.journal = journal
        self.config = model_config
        self.run_id = run_id
        self.code_revision = code_revision
        self._runner = question_runner
        self._capacity = BoundedSemaphore(4)

    def ask(self, question: str) -> dict:
        _valid_text(question, label="question", limit=4000, nonempty=True)
        if not self._capacity.acquire(blocking=False):
            raise JournalError("lab_capacity_reached")
        try:
            # Persist the request before attempting any model/retrieval work.
            request = self.journal.start_request(
                question, channel="lab", run_id=self.run_id)
            start = perf_counter()
            error_code = None
            try:
                # Fresh provider per request: no cross-request usage or latency state.
                provider = SaturnLocalClaimProvider(self.config)
                outcome = self._runner(self.stand, question, draft_provider=provider)
                if outcome["answer"]["status"] == "error":
                    reason = outcome["answer"].get("reason_code")
                    error_code = reason if isinstance(reason, str) and re.fullmatch(
                        r"[a-zA-Z0-9_]{1,100}", reason) else "rag_error_status"
            except Exception as exc:
                # Exception messages may include raw prompts, URLs or credentials.
                # Only a fixed internal error label + exception class are retained.
                error_code = "lab_runtime_" + type(exc).__name__
                if not re.fullmatch(r"[a-zA-Z0-9_]{1,100}", error_code):
                    error_code = "lab_runtime_exception"
                outcome = {
                    "answer": {
                        "status": "error",
                        "answer_text": "Техническая ошибка обработки вопроса.",
                        "reason_code": "lab_runtime_failure",
                        "snapshot_id": self.stand.snapshot.snapshot_id,
                        "bundle_id": self.stand.bundle.manifest.bundle_id,
                        "policy_revision": "lab-runtime-error",
                        "citations": [],
                        "diagnostics": [["lab_runtime_failure", 1]],
                        "unresolved_need_ids": [],
                    },
                    "stage_trace": {"runtime_failure": error_code},
                    "local_inference": None,
                }
            elapsed_ms = (perf_counter() - start) * 1000
            self.journal.finish_request(
                request, outcome=outcome, duration_ms=elapsed_ms,
                code_revision=self.code_revision, model_id=self.config.model_id,
                model_sha256=self.config.declared_model_sha256,
                error_code=error_code,
            )
            return self.journal.get_entry(request.request_id)
        finally:
            self._capacity.release()

    def review(self, request_id: str, expert: str, comment: str) -> dict:
        self.journal.save_review(request_id, expert=expert, comment=comment)
        return self.journal.get_entry(request_id)


class FeedbackLabHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, port: int, service: FeedbackLabService):
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("invalid_lab_port")
        self.lab_service = service
        self.csrf_token = secrets.token_hex(32)
        self.csp_nonce = secrets.token_urlsafe(24)
        # Deliberately NO host argument. IPv4 only, always loopback.
        self.address_family = socket.AF_INET
        super().__init__(("127.0.0.1", port), FeedbackLabHandler)

    @property
    def lab_origin(self) -> str:
        return "http://127.0.0.1:" + str(self.server_address[1])


class FeedbackLabHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # Never log raw paths, query strings, user questions or cookies.
        pass

    def _send(self, status: int, data: bytes, *, content_type: str,
              disposition: str | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        # Do not reuse a connection after rejecting a request with unread body.
        self.send_header("Connection", "close")
        self.close_connection = True
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'nonce-" +
                         self.server.csp_nonce + "'; style-src 'unsafe-inline'; "
                         "connect-src 'self'; base-uri 'none'; form-action 'none'; "
                         "frame-ancestors 'none'")
        if disposition:
            self.send_header("Content-Disposition", disposition)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, status, data):
        self._send(status, json.dumps(data, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8"),
                   content_type="application/json; charset=utf-8")

    def _reject(self, status: int, code: str):
        self._json(status, {"error": code})

    def _host_ok(self):
        host = self.headers.get_all("Host", [])
        return len(host) == 1 and host[0] == (
            "127.0.0.1:" + str(self.server.server_address[1]))

    def _origin_ok(self):
        origins = self.headers.get_all("Origin", [])
        fetch_site = self.headers.get("Sec-Fetch-Site")
        return (
            len(origins) == 1 and origins[0] == self.server.lab_origin
            and (fetch_site is None or fetch_site in ("same-origin", "none"))
            and hmac.compare_digest(
                self.headers.get("X-Lab-CSRF", ""),
                self.server.csrf_token)
        )

    @staticmethod
    def _filter(query: str):
        parsed = parse_qs(query, keep_blank_values=True, strict_parsing=True)
        if set(parsed) - {"status"} or len(parsed.get("status", [])) > 1:
            raise ValueError("invalid_query")
        value = parsed.get("status", [None])[0]
        if value == "":
            value = None
        if value is not None and value not in ("accepted", "commented", "unreviewed"):
            raise ValueError("invalid_review_filter")
        return value

    def do_GET(self):
        if not self._host_ok():
            return self._reject(403, "invalid_host")
        parsed = urlsplit(self.path)
        try:
            if parsed.path == "/" and not parsed.query:
                page = Path(__file__).with_name("feedback_lab_ui.html").read_text("utf-8")
                page = page.replace("__CSRF__", self.server.csrf_token).replace(
                    "__NONCE__", self.server.csp_nonce)
                return self._send(200, page.encode("utf-8"),
                                  content_type="text/html; charset=utf-8")
            if parsed.path == "/api/entries":
                status = self._filter(parsed.query)
                entries = self.server.lab_service.journal.list_entries(
                    status=status, limit=100)
                return self._json(200, {"entries": entries})
            if parsed.path.startswith("/api/entries/") and not parsed.query:
                request_id = parsed.path.removeprefix("/api/entries/")
                if not _ID.fullmatch(request_id):
                    return self._reject(400, "invalid_request_id")
                entry = self.server.lab_service.journal.get_entry(request_id)
                return self._json(200, entry)
            if parsed.path == "/api/export":
                params = parse_qs(parsed.query, keep_blank_values=True,
                                  strict_parsing=True)
                if (set(params) - {"status", "format"} or
                        len(params.get("format", [])) != 1 or
                        len(params.get("status", [])) > 1):
                    return self._reject(400, "invalid_export_query")
                fmt = params["format"][0]
                status = params.get("status", [None])[0] or None
                if status is not None and status not in (
                        "accepted", "commented", "unreviewed"):
                    return self._reject(400, "invalid_review_filter")
                journal = self.server.lab_service.journal
                if fmt == "json":
                    raw = journal.export_json(status=status).encode("utf-8")
                    return self._send(200, raw, content_type="application/json; charset=utf-8",
                                      disposition='attachment; filename="lab-journal.json"')
                if fmt == "csv":
                    raw = ("\ufeff" + journal.export_csv(status=status)).encode("utf-8")
                    return self._send(200, raw, content_type="text/csv; charset=utf-8",
                                      disposition='attachment; filename="lab-journal.csv"')
                return self._reject(400, "invalid_export_format")
            return self._reject(404, "not_found")
        except ValueError:
            return self._reject(400, "invalid_request")
        except JournalError as error:
            return self._reject(500, str(error))
        except OSError:
            return self._reject(500, "journal_or_ui_unavailable")

    def do_POST(self):
        if not self._host_ok() or not self._origin_ok():
            return self._reject(403, "origin_or_csrf_denied")
        if self.headers.get("Transfer-Encoding") or len(
                self.headers.get_all("Content-Length", [])) != 1:
            return self._reject(400, "invalid_body_length")
        if self.headers.get("Content-Type") != "application/json":
            return self._reject(415, "json_required")
        try:
            length = int(self.headers["Content-Length"])
            if not 1 <= length <= MAX_HTTP_BODY:
                return self._reject(413, "body_too_large")
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if type(data) is not dict:
                return self._reject(400, "invalid_json_object")
            if self.path == "/api/ask":
                if set(data) != {"question"}:
                    return self._reject(400, "invalid_ask_payload")
                entry = self.server.lab_service.ask(data["question"])
                return self._json(200, {"entry": entry})
            if self.path.startswith("/api/reviews/"):
                request_id = self.path.removeprefix("/api/reviews/")
                if not _ID.fullmatch(request_id) or set(data) != {"expert", "comment"}:
                    return self._reject(400, "invalid_review_payload")
                entry = self.server.lab_service.review(
                    request_id, data["expert"], data["comment"])
                return self._json(200, {"entry": entry})
            return self._reject(404, "not_found")
        except (ValueError, UnicodeError, TypeError, KeyError):
            return self._reject(400, "invalid_request")
        except JournalWriteError:
            return self._reject(507, "journal_write_failed")
        except JournalError as error:
            return self._reject(500, str(error))
        except OSError:
            return self._reject(500, "io_error")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Stage 5J local-only expert RAG lab")
    parser.add_argument("--allow-real-network", action="store_true")
    parser.add_argument("--allow-development-pdf-worker", action="store_true")
    parser.add_argument("--allow-local-inference", action="store_true")
    parser.add_argument("--journal-root", type=Path, required=True)
    parser.add_argument("--local-model-id", required=True)
    parser.add_argument("--local-model-sha256", required=True)
    parser.add_argument("--local-endpoint", default=EXACT_MODEL_ENDPOINT)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not all((args.allow_real_network, args.allow_development_pdf_worker,
                args.allow_local_inference)):
        parser.error("Explicit real-source, development PDF and local inference opt-ins required")
    if args.local_endpoint != EXACT_MODEL_ENDPOINT:
        parser.error("Only exact SSH-forwarded loopback endpoint is allowed")
    if not 1024 <= args.port <= 65535:
        parser.error("Lab HTTP port must be 1024..65535")
    model_config = SaturnLocalModelConfig(
        endpoint=args.local_endpoint, model_id=args.local_model_id,
        declared_model_sha256=args.local_model_sha256)
    journal = MarkdownFeedbackJournal(args.journal_root)
    code_revision = _code_revision()
    # Network and PDF work happen exactly once, before HTTP begins serving.
    stand = prepare_real_stand(
        provider=GitHubSnapshotProvider.from_env(),
        enable_development_pdf_worker=True)
    run_id = uuid.uuid4().hex
    service = FeedbackLabService(
        stand=stand, journal=journal, model_config=model_config,
        run_id=run_id, code_revision=code_revision)
    server = FeedbackLabHTTPServer(args.port, service)
    print("Stage 5J LAB ONLY: " + server.lab_origin +
          " | experiment=" + run_id + " | snapshot=" + stand.snapshot.snapshot_id,
          flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
