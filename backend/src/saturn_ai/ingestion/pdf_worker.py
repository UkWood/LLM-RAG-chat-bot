"""Standalone bounded extractor. Authored fixtures only; not an OS security sandbox."""
import json
import sys


def extract():
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    # No API, download hooks, annotations, actions or attachments are processed.
    from io import BytesIO
    from pypdf import PdfReader
    data = sys.stdin.buffer.read(1_000_001)
    if len(data) > 1_000_000 or not data.startswith(b'%PDF-'):
        raise ValueError('Invalid PDF bytes')
    reader = PdfReader(BytesIO(data), strict=True)
    if reader.is_encrypted:
        raise ValueError('Encrypted PDF')
    root = reader.trailer['/Root']
    if any(key in root for key in ('/OpenAction', '/AA', '/Names', '/AcroForm', '/Collection')):
        raise ValueError('Unsupported active/attached PDF content')
    max_pages = int(sys.argv[1])
    if not 1 <= len(reader.pages) <= max_pages:
        raise ValueError('PDF page limit')
    pages, total = [], 0
    for number, page in enumerate(reader.pages, 1):
        if any(key in page for key in ('/AA', '/Annots')):
            raise ValueError('PDF annotations disabled')
        content = page.get_contents()
        if content is not None and len(content.get_data()) > 2_000_000:
            raise ValueError('PDF decoded stream limit')
        text = page.extract_text().strip()
        total += len(text)
        if not text or '\x00' in text or len(text) > 20000 or total > 100000:
            raise ValueError('PDF text quality/size gate')
        pages.append({'page': number, 'text': text})
    return pages


if __name__ == '__main__':
    try:
        result = extract()
        sys.stdout.write(json.dumps(result, ensure_ascii=False))
    except Exception:
        # Never expose parser exceptions, document content or paths to caller logs.
        sys.exit(2)
