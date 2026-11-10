"""Saturn PDF subprocess worker; development/test isolation, NOT an OS sandbox.

No networking or filesystem paths are needed for parsing. Production use MUST
remain disabled until an independently configured OS-level confinement exists.
"""
import json
import sys


class WorkerRejection(Exception):
    pass


def _reject(code):
    raise WorkerRejection(code)


def extract(raw: bytes, limits: tuple[int, ...]):
    from io import BytesIO
    from pypdf import PdfReader

    max_pdf, max_pages, max_text, max_page_text, max_stream, max_all_stream = limits
    if not raw.startswith(b"%PDF-") or not 8 <= len(raw) <= max_pdf:
        _reject("invalid_pdf")
    try:
        reader = PdfReader(BytesIO(raw), strict=True)
        if reader.is_encrypted:
            _reject("encrypted_pdf")
        root = reader.trailer["/Root"].get_object()
        if any(name in root for name in (
                "/OpenAction", "/AA", "/Names", "/AcroForm", "/Collection",
                "/JavaScript", "/EmbeddedFiles", "/Perms", "/RichMedia")):
            _reject("invalid_pdf")
        count = len(reader.pages)
        if not 1 <= count <= max_pages:
            _reject("page_limit")
        pages = []
        text_bytes = 0
        decoded_bytes = 0
        for number, page in enumerate(reader.pages, 1):
            if any(key in page for key in (
                    "/AA", "/Annots", "/OpenAction", "/JS", "/RichMedia", "/AF")):
                _reject("invalid_pdf")
            content = page.get_contents()
            if content is not None:
                stream = content.get_data()
                decoded_bytes += len(stream)
                if len(stream) > max_stream or decoded_bytes > max_all_stream:
                    _reject("resource_limit")
                del stream
            text = page.extract_text() or ""
            text = text.strip()
            if any((ord(ch) < 32 and ch not in "\n\r\t") or ord(ch) == 127
                   for ch in text):
                _reject("parser_error")
            size = len(text.encode("utf-8"))
            text_bytes += size
            if size > max_page_text or text_bytes > max_text:
                _reject("resource_limit")
            pages.append({"number": number, "text": text})
        return {"page_count": count, "pages": pages}
    except WorkerRejection:
        raise
    except MemoryError:
        _reject("resource_limit")
    except Exception:
        _reject("parser_error")


def main():
    try:
        if len(sys.argv) != 9:
            _reject("parser_error")
        numbers = tuple(int(s) for s in sys.argv[1:])
        if len(numbers) != 8 or any(value < 1 for value in numbers):
            _reject("parser_error")
        *limits, ram, cpu = numbers
        # Real process limits are enforced by the kernel on POSIX, but do not
        # block network syscalls or guarantee filesystem confinement.
        import resource
        for kind, value in (
                (resource.RLIMIT_AS, ram),
                (resource.RLIMIT_CPU, cpu),
                (resource.RLIMIT_FSIZE, 0),
                (resource.RLIMIT_CORE, 0)):
            resource.setrlimit(kind, (value, value))
        raw = sys.stdin.buffer.read(limits[0] + 1)
        if len(raw) > limits[0]:
            _reject("size_limit")
        result = extract(raw, tuple(limits))
        sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    except WorkerRejection as exc:
        sys.stdout.write(json.dumps({"error": str(exc)}))
        return 2
    except (OSError, ValueError):
        sys.stdout.write('{"error":"resource_limit"}')
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
