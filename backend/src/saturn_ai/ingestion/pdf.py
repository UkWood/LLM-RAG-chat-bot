"""Bounded local PDF adapter. No network/download/OCR; fixture-only runner."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from .contracts import Document, identifier, make_chunk
from .registry import SourceRecord

PARSER_VERSION = 'pdf-v1'


def parse_pdf(record: SourceRecord, content: bytes, *, max_pages: int = 20) -> Document:
    digest = sha256(content).hexdigest()
    if (record.source_kind != 'external_document' or len(content) > 1_000_000
            or not record.permits('local_index', digest)
            or type(max_pages) is not int or not 1 <= max_pages <= 20):
        raise ValueError('PDF source denied or over limit')
    try:
        result = subprocess.run([sys.executable, '-I', str(Path(__file__).with_name('pdf_worker.py')), str(max_pages)],
                                input=content, capture_output=True, timeout=5, check=False,
                                env={'PATH': os.defpath, 'PYTHONIOENCODING': 'utf-8'})
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('PDF worker unavailable or timed out') from None
    if result.returncode != 0 or len(result.stdout) > 1_000_000:
        raise ValueError('PDF extraction rejected; quarantine required')
    try:
        pages = json.loads(result.stdout)
        if not isinstance(pages, list) or not 1 <= len(pages) <= max_pages:
            raise ValueError('Invalid extracted pages')
        for number, page in enumerate(pages, 1):
            if (not isinstance(page, dict) or set(page) != {'page', 'text'}
                    or type(page['page']) is not int or page['page'] != number
                    or not isinstance(page['text'], str) or not page['text'].strip()
                    or len(page['text']) > 20000):
                raise ValueError('Invalid extracted page')
    except (ValueError, TypeError):
        raise ValueError('Invalid PDF worker response') from None
    docid = identifier(record.source_id, digest, record.url, PARSER_VERSION)
    chunks = tuple(make_chunk(docid, record.source_id, page['text'], (), 'pdf.page', page['page']) for page in pages)
    return Document(docid, record.source_id, digest, PARSER_VERSION, record.title,
                    record.discovered_from, 'Document', None, record.url, chunks)
