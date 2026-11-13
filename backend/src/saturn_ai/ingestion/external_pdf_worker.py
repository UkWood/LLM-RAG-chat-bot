"""Saturn PDF subprocess worker; development/test isolation, NOT an OS sandbox.

Navigation is syntax-validated but never followed, fetched, indexed or emitted.
No networking or filesystem paths are needed for parsing. Production use MUST
remain disabled until an independently configured OS-level confinement exists.
"""
import json
import math
import sys
from urllib.parse import urlsplit


# Fixed navigation budgets; deliberately independent of source-document contents.
MAX_ANNOTATIONS = 256
MAX_ANNOTATIONS_PER_PAGE = 64
MAX_NAV_OBJECTS = 4096
MAX_INDIRECTION_HOPS = 4
MAX_NAV_DEPTH = 6
MAX_DICTIONARY_KEYS = 16
MAX_ARRAY_ITEMS = 64
MAX_URI_BYTES = 2048
MAX_XYZ_COORDINATE = 1_000_000


class WorkerRejection(Exception):
    pass


def _reject(code):
    raise WorkerRejection(code)


class _InertNavigation:
    """Bounded, fail-closed inspection of narrowly permitted PDF navigation."""

    def __init__(self, reader):
        from pypdf.generic import IndirectObject

        self.reader = reader
        self.seen = 0
        self.annotations = 0
        # Physical page references only, never names or another PDF reader.
        self.page_ids = set()
        for page in reader.pages:
            ref = page.indirect_reference
            if (type(ref) is not IndirectObject or ref.pdf is not reader):
                _reject("invalid_pdf")
            self.page_ids.add((ref.idnum, ref.generation))

    def _touch(self, depth):
        if depth > MAX_NAV_DEPTH:
            _reject("invalid_pdf")
        self.seen += 1
        if self.seen > MAX_NAV_OBJECTS:
            _reject("resource_limit")

    def _resolve(self, value, depth):
        from pypdf.generic import IndirectObject

        visited = set()
        self._touch(depth)
        hops = 0
        while type(value) is IndirectObject:
            if hops >= MAX_INDIRECTION_HOPS:
                _reject("resource_limit")
            if value.pdf is not self.reader:
                _reject("invalid_pdf")
            identity = (value.idnum, value.generation)
            if identity in visited:
                _reject("invalid_pdf")
            visited.add(identity)
            hops += 1
            self._touch(depth + hops)
            value = value.get_object()
        return value

    def _dictionary(self, value, depth, keys):
        from pypdf.generic import DictionaryObject, NameObject

        value = self._resolve(value, depth)
        if type(value) is not DictionaryObject:
            _reject("invalid_pdf")
        if len(value) > MAX_DICTIONARY_KEYS:
            _reject("resource_limit")
        if any(type(key) is not NameObject or key not in keys for key in value):
            _reject("invalid_pdf")
        return value

    def _array(self, value, depth, *, length=None):
        from pypdf.generic import ArrayObject

        value = self._resolve(value, depth)
        if type(value) is not ArrayObject:
            _reject("invalid_pdf")
        if len(value) > MAX_ARRAY_ITEMS:
            _reject("resource_limit")
        if length is not None and len(value) != length:
            _reject("invalid_pdf")
        return value

    def _name(self, value, name, depth):
        from pypdf.generic import NameObject

        value = self._resolve(value, depth)
        if type(value) is not NameObject or value != name:
            _reject("invalid_pdf")

    def _number(self, value, depth, *, coordinate=False):
        from pypdf.generic import FloatObject, NumberObject

        value = self._resolve(value, depth)
        if type(value) not in (NumberObject, FloatObject):
            _reject("invalid_pdf")
        try:
            numeric = float(value)
        except (ValueError, OverflowError, TypeError):
            _reject("invalid_pdf")
        if not math.isfinite(numeric) or (coordinate and abs(numeric) > MAX_XYZ_COORDINATE):
            _reject("invalid_pdf")
        return numeric

    def _integer(self, value, depth, lower, upper):
        from pypdf.generic import NumberObject

        value = self._resolve(value, depth)
        if type(value) is not NumberObject or not lower <= int(value) <= upper:
            _reject("invalid_pdf")

    def _zero_integer(self, value, depth):
        self._integer(value, depth, 0, 0)

    def _xyz(self, value, depth):
        from pypdf.generic import IndirectObject, NullObject

        value = self._array(value, depth, length=5)
        target = value[0]
        # Page reference is inspected, never followed; membership is computed
        # from the same reader's canonical physical page references.
        self._touch(depth + 1)
        if (type(target) is not IndirectObject or target.pdf is not self.reader or
                (target.idnum, target.generation) not in self.page_ids):
            _reject("invalid_pdf")
        self._name(value[1], "/XYZ", depth + 1)
        for parameter in value[2:4]:
            resolved = self._resolve(parameter, depth + 1)
            if type(resolved) is not NullObject:
                self._number_value(resolved, coordinate=True)
        # The real-corpus contract permits ONLY NumberObject(0), not null,
        # a floating-point zero or any other zoom value.
        self._zero_integer(value[4], depth + 1)

    @staticmethod
    def _number_value(value, *, coordinate=False):
        from pypdf.generic import FloatObject, NumberObject
        if type(value) not in (NumberObject, FloatObject):
            _reject("invalid_pdf")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            _reject("invalid_pdf")
        if not math.isfinite(number) or (coordinate and abs(number) > MAX_XYZ_COORDINATE):
            _reject("invalid_pdf")
        return number

    def _border(self, value, depth):
        border = self._array(value, depth, length=3)
        for item in border:
            self._zero_integer(item, depth + 1)

    def _bs(self, value, depth):
        bs = self._dictionary(value, depth, {"/W"})
        if set(bs) != {"/W"}:
            _reject("invalid_pdf")
        self._zero_integer(bs.raw_get("/W"), depth + 1)

    def _uri(self, value, depth):
        from pypdf.generic import TextStringObject
        import ipaddress
        import re
        import unicodedata

        value = self._resolve(value, depth)
        if type(value) is not TextStringObject:
            _reject("invalid_pdf")
        try:
            encoded = str(value).encode("utf-8", "strict")
        except UnicodeError:
            _reject("invalid_pdf")
        if not 1 <= len(encoded) <= MAX_URI_BYTES:
            _reject("invalid_pdf")
        if any(char.isspace() or unicodedata.category(char) == "Cc" or
               char == "\\" for char in value):
            _reject("invalid_pdf")
        try:
            parsed = urlsplit(str(value))
            if (parsed.scheme not in ("http", "https") or not parsed.netloc or
                    "#" in value or
                    parsed.username is not None or parsed.password is not None or
                    not parsed.hostname or parsed.hostname.endswith(".")):
                _reject("invalid_pdf")
            _ = parsed.port  # Reject malformed/non-numeric ports without connecting.
            host = parsed.hostname
            if host.startswith("[") or host.endswith("]"):
                _reject("invalid_pdf")
            try:
                ipaddress.ip_address(host)
            except ValueError:
                labels = host.split(".")
                if (len(host) > 253 or any(not 1 <= len(label) <= 63 or
                        not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label)
                        for label in labels)):
                    _reject("invalid_pdf")
        except ValueError:
            _reject("invalid_pdf")
        # Absolutely no requests, DNS resolution, citation or evidence generated.

    def _action(self, value, depth):
        action = self._dictionary(value, depth, {"/S", "/Type", "/URI"})
        if set(action) != {"/S", "/Type", "/URI"}:
            _reject("invalid_pdf")
        self._name(action.raw_get("/S"), "/URI", depth + 1)
        self._name(action.raw_get("/Type"), "/Action", depth + 1)
        self._uri(action.raw_get("/URI"), depth + 1)

    def _annotation(self, value):
        variant_a = {"/BS", "/Dest", "/F", "/Rect", "/StructParent", "/Subtype"}
        variant_b = {"/Border", "/Dest", "/Rect", "/Subtype", "/Type"}
        variant_c = {"/A", "/Border", "/Rect", "/Subtype", "/Type"}
        annot = self._dictionary(value, 1, variant_a | variant_b | variant_c)
        keys = set(annot)
        if keys not in (variant_a, variant_b, variant_c):
            _reject("invalid_pdf")
        self._name(annot.raw_get("/Subtype"), "/Link", 2)
        if keys != variant_a:
            self._name(annot.raw_get("/Type"), "/Annot", 2)
        rect = self._array(annot.raw_get("/Rect"), 2, length=4)
        coordinates = [self._number(item, 3) for item in rect]
        if coordinates[0] > coordinates[2] or coordinates[1] > coordinates[3]:
            _reject("invalid_pdf")
        if keys == variant_a:
            self._bs(annot.raw_get("/BS"), 2)
            self._integer(annot.raw_get("/F"), 2, 4, 4)
            self._integer(annot.raw_get("/StructParent"), 2, 0, 2147483647)
            self._xyz(annot.raw_get("/Dest"), 2)
        else:
            self._border(annot.raw_get("/Border"), 2)
            if keys == variant_b:
                self._xyz(annot.raw_get("/Dest"), 2)
            else:
                self._action(annot.raw_get("/A"), 2)

    def validate(self, root):
        if "/OpenAction" in root:
            self._xyz(root.raw_get("/OpenAction"), 1)
        for page in self.reader.pages:
            if "/Annots" not in page:
                continue
            annotations = self._array(page.raw_get("/Annots"), 1)
            if len(annotations) > MAX_ANNOTATIONS_PER_PAGE:
                _reject("resource_limit")
            self.annotations += len(annotations)
            if self.annotations > MAX_ANNOTATIONS:
                _reject("resource_limit")
            for entry in annotations:
                self._annotation(entry)


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
                "/AA", "/Names", "/AcroForm", "/Collection", "/JavaScript",
                "/EmbeddedFiles", "/Perms", "/RichMedia")):
            _reject("invalid_pdf")
        count = len(reader.pages)
        if not 1 <= count <= max_pages:
            _reject("page_limit")
        # Whole-document navigation validation strictly precedes any text extraction.
        for page in reader.pages:
            if any(key in page for key in ("/AA", "/OpenAction", "/JS", "/RichMedia", "/AF")):
                _reject("invalid_pdf")
        _InertNavigation(reader).validate(root)
        pages = []
        text_bytes = 0
        decoded_bytes = 0
        for number, page in enumerate(reader.pages, 1):
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
