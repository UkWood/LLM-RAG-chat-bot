"""Bounded page-text extraction, with injectable test extractor.

The included subprocess worker is intentionally disabled by default. POSIX
resource limits are not a security sandbox. Production requires a separately
reviewed OS/container confinement boundary and execution adapter.
"""
from dataclasses import dataclass
import json
import os
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
        try:
            completed = subprocess.run(
                args, input=raw, capture_output=True, check=False,
                timeout=policy.worker_wall_seconds,
                env={"PATH": os.defpath, "PYTHONIOENCODING": "utf-8",
                     "PYTHONDONTWRITEBYTECODE": "1"},
            )
        except subprocess.TimeoutExpired:
            raise DocumentError("timeout") from None
        except OSError:
            raise DocumentError("resource_limit") from None
        if len(completed.stdout) > policy.max_text_bytes * 6 + policy.max_pages * 128:
            raise DocumentError("resource_limit")
        try:
            data = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeError, ValueError):
            raise DocumentError("parser_error") from None
        if completed.returncode != 0:
            code = data.get("error") if type(data) is dict else None
            if code not in CODES:
                code = "resource_limit" if completed.returncode < 0 else "parser_error"
            raise DocumentError(code)
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
