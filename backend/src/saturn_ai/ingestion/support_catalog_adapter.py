"""Offline catalog of linked Saturn support materials.

Only trusted SiteContentPackage data are consumed. No fetch, PDF parsing,
legacy source approval, or mutation of the site adapter/contracts takes place.
"""
from dataclasses import dataclass
from html import unescape as html_unescape
import json
import re
import string
from urllib.parse import urljoin, urlsplit, urlunsplit, unquote

from .saturn_contracts import SupportDocument, stable_id
from .saturn_site_adapter import SiteContentPackage, SiteParseIssue


CATALOG_VERSION = "saturn-support-catalog/0.1.0"

_DEFINITION = re.compile(r'^\s{0,3}\[([^\]\n]+)\]:\s*(?:<([^>\n]+)>|(\S+))')
_HTML_TAG = re.compile(r"""<a(?=[\s/>])(?:(?:"[^"]*"|'[^']*'|[^'"<>])*)>""", re.I)
_HTML_ATTR = re.compile(r"""(?<!\S)([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>]+)))?""")
_AUTOLINK = re.compile(r"<(https://[^\s<>]+)>", re.I)
_FENCE = re.compile(r'^\s{0,3}(' + chr(96) + r'{3,}|~{3,})')
_HEADING = re.compile(r'^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$')
_PERCENT_BAD = re.compile(r'%(?![0-9A-Fa-f]{2})')
_CONTROL = re.compile(r'[\x00-\x20\x7f]')


@dataclass(frozen=True)
class CatalogOccurrence:
    """Lossless source-specific metadata; keeps collisions traceable."""

    document_id: str
    owner_entity_id: str
    source_revision_id: str
    source_path: str
    field_path: str
    source_locator: str
    raw_url: str
    resolved_url: str
    title: str | None
    kind: str | None
    version: str | None
    date: str | None


@dataclass(frozen=True)
class PdfCandidate:
    document_id: str
    resolved_url: str
    raw_urls: tuple[str, ...]
    owner_entity_ids: tuple[str, ...]
    source_locators: tuple[str, ...]
    source_revision_ids: tuple[str, ...]


@dataclass(frozen=True)
class SupportCatalogResult:
    documents: tuple[SupportDocument, ...]
    pdf_candidates: tuple[PdfCandidate, ...]
    occurrences: tuple[CatalogOccurrence, ...]
    issues: tuple[SiteParseIssue, ...]
    upstream_ready: bool
    catalog_version: str = CATALOG_VERSION

    @property
    def ready_for_promotion(self) -> bool:
        return self.upstream_ready and not any(x.severity == "error" for x in self.issues)

    @property
    def error_count(self) -> int:
        return sum(x.severity == "error" for x in self.issues)


def _is_pdf(value: str) -> bool:
    """One percent-decoding pass for PDF detection; no query or fragment inference."""
    try:
        return unquote(urlsplit(value).path).lower().endswith(".pdf")
    except (ValueError, TypeError):
        return False


def _origin(entities) -> str | None:
    origins = set()
    for entity in entities:
        if entity.canonical_url:
            parts = urlsplit(entity.canonical_url)
            origins.add(urlunsplit((parts.scheme, parts.netloc, "", "", "")))
    return next(iter(origins)) if len(origins) == 1 else None


def _checked_path(path: str) -> None:
    """Check each encoded path segment before resolution, without rewriting it."""
    for segment in path.split("/"):
        value = segment
        for _ in range(8):
            if value in (".", "..") or "/" in value or "\\" in value:
                raise ValueError("URL contains path traversal or encoded separators")
            if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
                raise ValueError("URL contains encoded control characters")
            try:
                decoded = unquote(value, errors="strict")
            except UnicodeDecodeError:
                raise ValueError("Invalid encoded URL path") from None
            if decoded == value:
                break
            value = decoded
        else:
            raise ValueError("URL exceeds safe percent-decoding depth")
        if value in (".", "..") or "/" in value or "\\" in value:
            raise ValueError("URL contains path traversal or encoded separators")


def _resolve_url(
    raw: str,
    base: str | None,
    public_origin: str | None,
    *,
    preserve_fragment: bool = False,
) -> str:
    """Resolve interpreted URL without lossy path/query normalization.

    With preserve_fragment=True this is a per-occurrence destination.
    With preserve_fragment=False this is the stable document resource identity.
    """
    if not isinstance(raw, str) or not raw or raw != raw.strip() or len(raw) > 8192:
        raise ValueError("URL must be a non-empty bounded unpadded string")
    if "\\" in raw or _CONTROL.search(raw) or _PERCENT_BAD.search(raw):
        raise ValueError("URL has unsafe characters or malformed percent encoding")
    try:
        parsed = urlsplit(raw)
    except ValueError:
        raise ValueError("Invalid URL structure") from None
    if raw.startswith("//"):
        raise ValueError("Protocol-relative URL is ambiguous")
    _checked_path(parsed.path)  # MUST precede urljoin (which collapses dot segments)
    if parsed.scheme:
        if parsed.scheme.lower() != "https":
            raise ValueError("Only HTTPS URLs are accepted")
        target = raw
    elif parsed.netloc:
        raise ValueError("Relative URL contains an authority")
    elif parsed.path.startswith("/"):
        if not public_origin:
            raise ValueError("Trusted public origin is unavailable")
        target = public_origin + raw
    else:
        if not base:
            raise ValueError("Relative URL has no verified canonical page URL")
        target = urljoin(base, raw)
    try:
        result = urlsplit(target)
        hostname = result.hostname
        port = result.port
    except ValueError:
        raise ValueError("Invalid resolved URL") from None
    if (result.scheme.lower() != "https" or not hostname or
            result.username is not None or result.password is not None or
            not result.netloc or not result.path.startswith("/")):
        raise ValueError("Invalid HTTPS origin or credentials")
    _checked_path(result.path)
    host = hostname.lower()
    if ":" in host and not host.startswith("["):
        host = "[" + host + "]"
    authority = host if port in (None, 443) else f"{host}:{port}"
    return urlunsplit(("https", authority, result.path or "/", result.query,
                       result.fragment if preserve_fragment else ""))


def _mask_inline_code(line: str) -> str:
    """Blank backtick spans without moving the original character offsets."""
    chars = list(line)
    i = 0
    tick = chr(96)
    while i < len(line):
        if line[i] != tick:
            i += 1
            continue
        j = i
        while j < len(line) and line[j] == tick:
            j += 1
        run = line[i:j]
        k = line.find(run, j)
        if k < 0:
            i = j
            continue
        for pos in range(i, k + len(run)):
            chars[pos] = " "
        i = k + len(run)
    return "".join(chars)


def _mask_html_comments(line: str, inside: bool) -> tuple[str, bool]:
    """Suppress HTML comments, including multiline comments, at exact offsets."""
    chars = list(line)
    pos = 0
    while pos < len(line):
        if inside:
            end = line.find("-->", pos)
            stop = len(line) if end < 0 else end + 3
            for i in range(pos, stop):
                chars[i] = " "
            if end < 0:
                break
            inside = False
            pos = stop
            continue
        start = line.find("<!--", pos)
        if start < 0:
            break
        end = line.find("-->", start + 4)
        stop = len(line) if end < 0 else end + 3
        for i in range(start, stop):
            chars[i] = " "
        inside = end < 0
        pos = stop
    return "".join(chars), inside


def _is_escaped(value: str, pos: int) -> bool:
    count = 0
    while pos > count and value[pos - count - 1] == "\\":
        count += 1
    return count % 2 == 1


def _markdown_unescape(value: str) -> str:
    """Unescape only Markdown's backslash-escaped ASCII punctuation."""
    output = []
    index = 0
    while index < len(value):
        if (value[index] == "\\" and index + 1 < len(value) and
                value[index + 1] in string.punctuation):
            output.append(value[index + 1])
            index += 2
        else:
            output.append(value[index])
            index += 1
    return "".join(output)


def _read_label(value: str, pos: int) -> tuple[str, int] | None:
    """Balanced label, including escaped and nested square brackets."""
    if pos >= len(value) or value[pos] != "[":
        return None
    depth = 1
    index = pos + 1
    while index < len(value):
        ch = value[index]
        if ch == "\\" and index + 1 < len(value):
            index += 2
            continue
        if ch == "[":
            depth += 1
            if depth > 12:
                return None
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return value[pos + 1:index], index + 1
        index += 1
    return None


def _read_inline_destination(value: str, pos: int) -> tuple[str, int] | None:
    """Bounded Markdown destination with nested/escaped parentheses and optional title."""
    if pos >= len(value) or value[pos] != "(":
        return None
    index = pos + 1
    while index < len(value) and value[index] in " \t":
        index += 1
    if index >= len(value):
        return None
    if value[index] == "<":
        start = index + 1
        index += 1
        while index < len(value) and (value[index] != ">" or _is_escaped(value, index)):
            index += 1
        if index == len(value):
            return None
        raw = value[start:index]
        index += 1
    else:
        start = index
        depth = 0
        while index < len(value):
            ch = value[index]
            if ch == "\\" and index + 1 < len(value):
                index += 2
                continue
            if ch == "(":
                depth += 1
                if depth > 12:
                    return None
            elif ch == ")":
                if depth == 0:
                    break
                depth -= 1
            elif ch in " \t" and depth == 0:
                break
            index += 1
        if depth or index == start:
            return None
        raw = value[start:index]
    if not raw:
        return None
    if index < len(value) and value[index] in " \t":
        while index < len(value) and value[index] in " \t":
            index += 1
        if index < len(value) and value[index] in ("'", '"'):
            quote = value[index]
            index += 1
            while index < len(value) and (value[index] != quote or _is_escaped(value, index)):
                index += 1
            if index >= len(value):
                return None
            index += 1
            while index < len(value) and value[index] in " \t":
                index += 1
    if index >= len(value) or value[index] != ")":
        return None
    return raw, index + 1


def _anchor_href(tag: str) -> str | None:
    """Only href is a link; data-href, other attributes and bare tokens are not."""
    for match in _HTML_ATTR.finditer(tag[2:-1]):
        if match.group(1).lower() == "href":
            return next((value for value in match.groups()[1:] if value is not None), None)
    return None


def _markdown_links(body: str):
    """Scan supported PDF links with exact original line, column, heading, ordinal.

    Yields (raw_url, interpreted_destination, locator, parse_error). No
    Markdown renderer, JavaScript execution, network calls, or PDF reading.
    """
    clean = []
    fence_char = ""
    fence_len = 0
    heading = None
    in_comment = False
    for number, line in enumerate(body.splitlines(), 1):
        if fence_char:
            fence = _FENCE.match(line)
            if fence:
                marker = fence.group(1)
                if marker[0] == fence_char and len(marker) >= fence_len:
                    fence_char, fence_len = "", 0
            clean.append((number, "", heading))
            continue
        # Inline code is inert; comments can contain inert fence-like text.
        visible = _mask_inline_code(line)
        visible, in_comment = _mask_html_comments(visible, in_comment)
        fence = _FENCE.match(visible)
        if fence:
            marker = fence.group(1)
            fence_char, fence_len = marker[0], len(marker)
            clean.append((number, "", heading))
            continue
        match = _HEADING.match(visible)
        if match:
            heading = match.group(1)
        clean.append((number, visible, heading))

    references: dict[str, str] = {}
    for _, line, _ in clean:
        definition = _DEFINITION.match(line)
        if definition:
            key = " ".join(definition.group(1).lower().split())
            references.setdefault(key, definition.group(2) or definition.group(3))

    ordinal = 0
    for number, line, heading in clean:
        if _DEFINITION.match(line):
            continue
        hits: list[tuple[int, str, str]] = []
        occupied: list[tuple[int, int]] = []
        for match in _HTML_TAG.finditer(line):
            occupied.append((match.start(), match.end()))
            raw = _anchor_href(match.group(0))
            if raw is not None:
                interpreted = html_unescape(raw)
                if _is_pdf(interpreted):
                    hits.append((match.start(), raw, interpreted))
        for match in _AUTOLINK.finditer(line):
            if any(start <= match.start() < end for start, end in occupied):
                continue
            occupied.append((match.start(), match.end()))
            raw = match.group(1)
            if _is_pdf(raw):
                hits.append((match.start(), raw, raw))
        index = 0
        while index < len(line):
            if (line[index] != "[" or _is_escaped(line, index) or
                    any(start <= index < end for start, end in occupied)):
                index += 1
                continue
            if (index > 0 and line[index - 1] == "!" and
                    not _is_escaped(line, index - 1)):
                index += 1
                continue  # image, never a document
            label = _read_label(line, index)
            if label is None:
                index += 1
                continue
            text, end = label
            raw = None
            finish = end
            if end < len(line) and line[end] == "(":
                target = _read_inline_destination(line, end)
                if target is not None:
                    raw, finish = target
            elif end < len(line) and line[end] == "[":
                reference = _read_label(line, end)
                if reference is not None:
                    ref_label, finish = reference
                    key = " ".join((ref_label or text).lower().split())
                    raw = references.get(key)
            else:
                raw = references.get(" ".join(text.lower().split()))
            if raw is not None:
                interpreted = _markdown_unescape(raw)
                if _is_pdf(interpreted):
                    hits.append((index, raw, interpreted))
                index = finish
            else:
                index = end
        for column, raw, interpreted in sorted(hits, key=lambda item: item[0]):
            ordinal += 1
            locator = (
                f"body:line={number}:column={column + 1}:"
                f"heading={json.dumps(heading, ensure_ascii=False)}:"
                f"occurrence={ordinal}"
            )
            yield raw, interpreted, locator, None
        # Diagnose a clear incomplete PDF link, only on unmasked source text.
        if re.search(r'(?<!\\)\[[^\]\n]+\]\([^)\n]*\.pdf(?:[?#][^)\n]*)?$', line, re.I):
            yield None, None, f"body:line={number}", "malformed_markdown_link"


def adapt_support_catalog(package: SiteContentPackage) -> SupportCatalogResult:
    """Derive a complete fresh catalog from one existing SiteContentPackage."""
    if not isinstance(package, SiteContentPackage):
        raise TypeError("SiteContentPackage is required")
    revisions = {revision.revision_id: revision for revision in package.source_revisions}
    owners = {entity.entity_id for entity in package.entities if not entity.draft}
    public_origin = _origin(package.entities)
    issues: list[SiteParseIssue] = []
    occurrences: list[CatalogOccurrence] = []

    def problem(path: str, code: str, message: str, severity="error") -> None:
        issues.append(SiteParseIssue(path, "support_catalog", code, message, severity))

    def emit(entity, field_path, raw_url, title, kind, version=None, date=None, *, interpreted_url=None):
        revision = revisions.get(entity.source_revision_id)
        path = revision.path if revision else f"entity:{entity.entity_id}"
        if entity.entity_id not in owners or revision is None:
            problem(path, "missing_owner_or_revision", field_path + ": owner or source revision not found")
            return
        if not isinstance(raw_url, str) or not raw_url.strip():
            problem(path, "missing_url", field_path + ": URL is required")
            return
        try:
            destination = interpreted_url if interpreted_url is not None else raw_url
            url = _resolve_url(destination, entity.canonical_url, public_origin)
            source_url = _resolve_url(destination, entity.canonical_url, public_origin,
                                      preserve_fragment=True)
        except ValueError as exc:
            problem(path, "invalid_document_url", field_path + ": " + str(exc))
            return
        document_id = "saturn-doc:" + stable_id("saturn-support-document-url-v1", url)
        locator = entity.source_revision_id + "#" + field_path
        occurrences.append(CatalogOccurrence(
            document_id, entity.entity_id, entity.source_revision_id, path,
            field_path, locator, raw_url, source_url, title, kind, version, date,
        ))

    for entity in sorted(package.entities, key=lambda e: (e.collection, e.slug)):
        if entity.draft:
            continue
        revision = revisions.get(entity.source_revision_id)
        if revision is None:
            problem("entity:" + entity.entity_id, "missing_source_revision",
                    "Entity source revision not found")
            continue
        try:
            metadata = json.loads(entity.raw_frontmatter_json)
        except (TypeError, ValueError):
            problem(revision.path, "invalid_frontmatter", "Invalid canonical frontmatter")
            continue
        for field in ("documents", "certificates"):
            if field not in metadata:
                continue
            if field == "documents" and entity.collection not in ("products", "systems"):
                # Unsupported typed field on another collection is retained by
                # SiteContentPackage facts; do not silently type-interpret it.
                continue
            if field == "certificates" and entity.collection != "products":
                continue
            entries = metadata[field]
            if not isinstance(entries, list):
                problem(revision.path, "invalid_document_field_type", field + " must be a list")
                continue
            for index, item in enumerate(entries):
                pointer = f"{field}[{index}]"
                if not isinstance(item, dict):
                    problem(revision.path, "malformed_document_entry", pointer + " must be an object")
                    continue
                scan = field == "certificates" and item.get("kind") == "scan"
                raw_url = item.get("image") if scan else item.get("url")
                kind = item.get("kind")
                title = item.get("title")
                if scan and title is None:
                    display_title = None
                else:
                    display_title = title
                if (not isinstance(kind, str) or not kind.strip() or
                        (display_title is not None and
                         (not isinstance(display_title, str) or not display_title.strip()))):
                    problem(revision.path, "malformed_document_entry",
                            pointer + " requires valid kind and optional title")
                    continue
                if display_title is None and not scan:
                    problem(revision.path, "malformed_document_entry",
                            pointer + " requires a title")
                    continue
                version, date = item.get("version"), item.get("date")
                if any(v is not None and (not isinstance(v, str) or not v.strip())
                       for v in (version, date)):
                    problem(revision.path, "invalid_document_metadata", pointer + ": version/date must be text")
                    continue
                if not isinstance(raw_url, str) or not raw_url.strip():
                    problem(revision.path, "missing_url", pointer + ": URL/image is required")
                    continue
                emit(entity, pointer, raw_url, display_title, kind, version, date)

        for raw, interpreted, pointer, error in _markdown_links(entity.body):
            if error:
                problem(revision.path, error, pointer + ": incomplete PDF link")
            else:
                # The link label is not a reliable document title. Provenance
                # remains in the body; we do not manufacture metadata.
                emit(entity, pointer, raw, None, None, interpreted_url=interpreted)

    # A malformed manually constructed package must not silently hide orphan
    # document facts. Normal upstream packages always have matching entities.
    for fact in package.facts:
        if (fact.entity_id not in owners and
                re.match(r'^(documents|certificates)(?:\[|$)', fact.field_path)):
            problem("fact:" + fact.fact_id, "missing_owner",
                    "Document fact references an absent or excluded owner")

    grouped: dict[str, list[CatalogOccurrence]] = {}
    for item in occurrences:
        grouped.setdefault(item.document_id, []).append(item)
    documents = []
    pdfs = []
    for doc_id in sorted(grouped):
        linked = tuple(sorted(grouped[doc_id],
                              key=lambda x: (x.source_path, x.field_path, x.owner_entity_id)))
        url = _resolve_url(linked[0].resolved_url, None, None)
        owners_for_doc = tuple(sorted({x.owner_entity_id for x in linked}))
        locators = tuple(sorted({x.source_locator for x in linked}))
        chosen = {}
        for key in ("title", "kind", "version", "date"):
            values = sorted({getattr(x, key) for x in linked if getattr(x, key) is not None})
            if len(values) > 1:
                provenance = "; ".join(
                    f"{x.source_path}#{x.field_path}={getattr(x, key)!r}"
                    for x in linked if getattr(x, key) is not None
                )
                problem(linked[0].source_path, "conflicting_document_metadata",
                        f"{url}: {key} conflicts: {provenance}")
            chosen[key] = values[0] if values else None
        # Source fields may omit metadata. Fallbacks are presentation labels,
        # not evidence claims (see occurrence.title / kind = None).
        doc = SupportDocument(
            document_id=doc_id, title=chosen["title"] or url.rsplit("/", 1)[-1],
            kind=chosen["kind"] or "other", url=url,
            owner_entity_ids=owners_for_doc, source_locators=locators,
            version=chosen["version"], date=chosen["date"],
        )
        documents.append(doc)
        if _is_pdf(url):
            pdfs.append(PdfCandidate(
                doc_id, url, tuple(sorted({x.raw_url for x in linked})),
                owners_for_doc, locators,
                tuple(sorted({x.source_revision_id for x in linked})),
            ))
    return SupportCatalogResult(
        documents=tuple(documents),
        pdf_candidates=tuple(pdfs),
        occurrences=tuple(sorted(occurrences, key=lambda x: (
            x.document_id, x.source_path, x.field_path, x.owner_entity_id))),
        issues=tuple(sorted(issues, key=lambda x: (x.path, x.code, x.message))),
        upstream_ready=package.ready_for_promotion,
    )
