"""Bounded page-text extraction, with injectable test extractor.

The included subprocess worker is intentionally disabled by default. POSIX
resource limits are not a security sandbox. Production requires a separately
reviewed OS/container confinement boundary and execution adapter.
"""
from dataclasses import dataclass
import json
import os
import selectors
import time
from pathlib import Path
import subprocess
import sys

from .external_document_transport import DocumentError, DocumentFetchPolicy, CODES


PARSER_VERSION = "saturn-pdf-pypdf-6.10.0/0.1.0"


@dataclass(frozen=True)
class ExtractedPdf:
    """All physical pages, including blank/image-only pages with empty text."""

    page_count: int
    pages: tuple[tuple[int, str], ...]


def validate_extraction(extracted: ExtractedPdf, policy: DocumentFetchPolicy) -> None:
    if not isinstance(extracted, ExtractedPdf):
        raise DocumentError("parser_error")
    if (type(extracted.page_count) is not int or not 1 <= extracted.page_count <= policy.max_pages or
            type(extracted.pages) is not tuple or
            len(extracted.pages) != extracted.page_count):
        raise DocumentError("parser_error")
    total = 0
    for physical_number, item in enumerate(extracted.pages, 1):
        if (type(item) is not tuple or len(item) != 2 or
                type(item[0]) is not int or item[0] != physical_number or
                not isinstance(item[1], str) or "\x00" in item[1] or
                item[1] != item[1].strip()):
            raise DocumentError("parser_error")
        length = len(item[1].encode("utf-8"))
        if length > policy.max_page_text_bytes:
            raise DocumentError("resource_limit")
        total += length
        if total > policy.max_text_bytes:
            raise DocumentError("resource_limit")



def _run_worker_bounded(args: list[str], raw: bytes, policy: DocumentFetchPolicy) -> tuple[int, bytes]:
    """Stream stdin/stdout concurrently under a strict cap and wall deadline.

    POSIX pipe descriptors are multiplexed to prevent stdin/stdout deadlocks.
    stderr is sent to DEVNULL: no unbounded capture, PDF bytes, or exceptions
    in diagnostics. A live worker is always killed and reaped on failure.
    """
    output_limit = policy.max_text_bytes * 6 + policy.max_pages * 128
    environment = {"PATH": os.defpath, "PYTHONIOENCODING": "utf-8",
                   "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.Popen(
            args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, close_fds=True, env=environment,
        )
    except OSError:
        raise DocumentError("resource_limit") from None
    started = time.monotonic()
    selector = selectors.DefaultSelector()
    try:
        if proc.stdin is None or proc.stdout is None:
            raise DocumentError("resource_limit")
        os.set_blocking(proc.stdin.fileno(), False)
        os.set_blocking(proc.stdout.fileno(), False)
        selector.register(proc.stdout, selectors.EVENT_READ)
        if raw:
            selector.register(proc.stdin, selectors.EVENT_WRITE)
        else:
            proc.stdin.close()
        offset = 0
        total = 0
        parts: list[bytes] = []
        while selector.get_map():
            remaining = policy.worker_wall_seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise DocumentError("timeout")
            events = selector.select(remaining)
            if not events:
                raise DocumentError("timeout")
            for key, _ in events:
                if key.fileobj is proc.stdin:
                    try:
                        written = os.write(proc.stdin.fileno(), raw[offset:offset + 65536])
                    except BrokenPipeError:
                        written = -1
                    except BlockingIOError:
                        continue
                    if written > 0:
                        offset += written
                    if written <= 0 or offset >= len(raw):
                        selector.unregister(proc.stdin)
                        proc.stdin.close()
                else:
                    try:
                        block = os.read(proc.stdout.fileno(), min(
                            65536, output_limit - total + 1))
                    except BlockingIOError:
                        continue
                    if not block:
                        selector.unregister(proc.stdout)
                        proc.stdout.close()
                    else:
                        total += len(block)
                        if total > output_limit:
                            raise DocumentError("resource_limit")
                        parts.append(block)
        remaining = policy.worker_wall_seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise DocumentError("timeout")
        try:
            return proc.wait(timeout=remaining), b"".join(parts)
        except subprocess.TimeoutExpired:
            raise DocumentError("timeout") from None
    except OSError:
        raise DocumentError("resource_limit") from None
    finally:
        selector.close()
        if proc.poll() is None:
            proc.kill()
        for stream in (proc.stdin, proc.stdout):
            if stream is not None and not stream.closed:
                stream.close()
        proc.wait()


def _parse_worker_reply(returncode: int, output: bytes):
    """Classify signal termination BEFORE attempting JSON decoding."""
    if returncode < 0:
        raise DocumentError("resource_limit")
    try:
        data = json.loads(output.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise DocumentError("parser_error") from None
    if returncode != 0:
        code = data.get("error") if type(data) is dict else None
        raise DocumentError(code if isinstance(code, str) and code in CODES else "parser_error")
    return data


class SubprocessPdfExtractor:
    """Development-only worker; no production-ready isolation claim."""

    def __init__(self, *, enable_development_worker: bool = False):
        self._enabled = enable_development_worker

    def extract(self, raw: bytes, policy: DocumentFetchPolicy) -> ExtractedPdf:
        if not self._enabled:
            raise DocumentError("policy_denied")
        if not isinstance(raw, bytes) or len(raw) > policy.max_pdf_bytes:
            raise DocumentError("size_limit")
        if not raw.startswith(b"%PDF-"):
            raise DocumentError("invalid_pdf")
        args = [
            sys.executable, "-I", "-B",
            str(Path(__file__).with_name("external_pdf_worker.py")),
            str(policy.max_pdf_bytes), str(policy.max_pages),
            str(policy.max_text_bytes), str(policy.max_page_text_bytes),
            str(policy.max_decoded_stream_bytes),
            str(policy.max_total_stream_bytes),
            str(policy.worker_ram_bytes), str(policy.worker_cpu_seconds),
        ]
        returncode, output = _run_worker_bounded(args, raw, policy)
        data = _parse_worker_reply(returncode, output)
        if (type(data) is not dict or set(data) != {"page_count", "pages"} or
                type(data["pages"]) is not list):
            raise DocumentError("parser_error")
        pages = []
        for item in data["pages"]:
            if (type(item) is not dict or set(item) != {"number", "text"}):
                raise DocumentError("parser_error")
            pages.append((item["number"], item["text"]))
        result = ExtractedPdf(data["page_count"], tuple(pages))
        validate_extraction(result, policy)
        return result
