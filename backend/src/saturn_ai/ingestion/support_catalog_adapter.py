"""Offline catalog of linked Saturn support materials.

Only trusted SiteContentPackage data are consumed. No fetch, PDF parsing,
legacy source approval, or mutation of the site adapter/contracts takes place.
"""
from dataclasses import dataclass
import json
import re
from urllib.parse import urljoin, urlsplit, urlunsplit, unquote

from .saturn_contracts import SupportDocument, stable_id
from .saturn_site_adapter import SiteContentPackage, SiteParseIssue


CATALOG_VERSION = "saturn-support-catalog/0.1.0"

_INLINE = re.compile(r'(?<!!)\[([^\]\n]+)\]\(\s*(<[^>\n]+>|[^)\s]+)(?:\s+["\x27][^"\x27]+["\x27])?\s*\)')
_REFERENCE = re.compile(r'(?<!!)\[([^\]\n]+)\](?:\[([^\]\n]*)\])?')
_DEFINITION = re.compile(r'^\s{0,3}\[([^\]\n]+)\]:\s*(?:<([^>\n]+)>|(\S+))')
_HTML = re.compile(r'<a\b[^>]*\bhref\s*=\s*(["\x27])([^"\x27]+)\1[^>]*>', re.I)
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
    try:
        return urlsplit(value).path.lower().endswith(".pdf")
    except ValueError:
        return False


def _origin(entities) -> str | None:
    origins = set()
    for entity in entities:
        if entity.canonical_url:
            parts = urlsplit(entity.canonical_url)
            origins.add(urlunsplit((parts.scheme, parts.netloc, "", "", "")))
    return next(iter(origins)) if len(origins) == 1 else None


def _resolve_url(raw: str, base: str | None, public_origin: str | None) -> str:
    """Conservative URL resolution, without redirects, HTTP requests or lossy decoding."""
    if not isinstance(raw, str) or not raw or raw != raw.strip():
        raise ValueError("URL must be a non-empty unpadded string")
    if "\\" in raw or _CONTROL.search(raw) or _PERCENT_BAD.search(raw):
        raise ValueError("URL has unsafe characters or malformed percent encoding")
    try:
        parsed = urlsplit(raw)
    except ValueError:
        raise ValueError("Invalid URL structure") from None
    if raw.startswith("//"):
        raise ValueError("Protocol-relative URL is ambiguous")
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
    # Do not collapse dot segments, encoded slashes, case, or query values:
    # potentially different resources must never silently become one.
    for segment in result.path.split("/"):
        if segment in (".", "..") or unquote(segment) in (".", ".."):
            raise ValueError("URL contains path traversal")
    host = hostname.lower()
    if ":" in host and not host.startswith("["):
        host = "[" + host + "]"
    authority = host if port in (None, 443) else f"{host}:{port}"
    return urlunsplit(("https", authority, result.path or "/", result.query, ""))


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


def _markdown_links(body: str):
    """Yield direct links with one-based line, column, heading and occurrence.

    Supports inline, full/collapsed/shortcut references and quoted HTML href.
    Code fences, inline backticks and reference declarations are not links.
    """
    clean = []
    fence_char = ""
    fence_len = 0
    heading = None
    for number, line in enumerate(body.splitlines(), 1):
        fence = _FENCE.match(line)
        if fence:
            marker = fence.group(1)
            if not fence_char:
                fence_char, fence_len = marker[0], len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_len:
                fence_char, fence_len = "", 0
            clean.append((number, "", heading))
            continue
        if fence_char:
            clean.append((number, "", heading))
            continue
        visible = _mask_inline_code(line)
        marker = _HEADING.match(visible)
        if marker:
            heading = marker.group(1)
        clean.append((number, visible, heading))

    references = {}
    for _, line, _ in clean:
        match = _DEFINITION.match(line)
        if match:
            key = " ".join(match.group(1).lower().split())
            references.setdefault(key, match.group(2) or match.group(3))

    ordinal = 0
    for number, line, heading in clean:
        if _DEFINITION.match(line):
            continue
        hits = []
        used = []
        for match in _INLINE.finditer(line):
            raw = match.group(2).strip("<>")
            hits.append((match.start(), raw))
            used.append((match.start(), match.end()))
        for match in _HTML.finditer(line):
            hits.append((match.start(), match.group(2)))
            used.append((match.start(), match.end()))
        for match in _REFERENCE.finditer(line):
            if any(a <= match.start() < b for a, b in used):
                continue
            label = match.group(2) or match.group(1)
            key = " ".join(label.lower().split())
            if key in references:
                hits.append((match.start(), references[key]))
        for column, url in sorted(hits):
            if _is_pdf(url):
                ordinal += 1
                yield url, f"body:line={number}:column={column + 1}:heading={json.dumps(heading, ensure_ascii=False)}:occurrence={ordinal}", None
        # A malformed linked PDF is diagnostic, not an ordinary file mention.
        if re.search(r'\[[^\]\n]+\]\([^)\n]*\.pdf(?:[?#][^)\n]*)?$', line, re.I):
            yield None, f"body:line={number}", "malformed_markdown_link"


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

    def emit(entity, field_path, raw_url, title, kind, version=None, date=None):
        revision = revisions.get(entity.source_revision_id)
        path = revision.path if revision else f"entity:{entity.entity_id}"
        if entity.entity_id not in owners or revision is None:
            problem(path, "missing_owner_or_revision", field_path + ": owner or source revision not found")
            return
        if not isinstance(raw_url, str) or not raw_url.strip():
            problem(path, "missing_url", field_path + ": URL is required")
            return
        try:
            url = _resolve_url(raw_url, entity.canonical_url, public_origin)
        except ValueError as exc:
            problem(path, "invalid_document_url", field_path + ": " + str(exc))
            return
        document_id = "saturn-doc:" + stable_id("saturn-support-document-url-v1", url)
        locator = entity.source_revision_id + "#" + field_path
        occurrences.append(CatalogOccurrence(
            document_id, entity.entity_id, entity.source_revision_id, path,
            field_path, locator, raw_url, url, title, kind, version, date,
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

        for url, pointer, error in _markdown_links(entity.body):
            if error:
                problem(revision.path, error, pointer + ": incomplete PDF link")
            else:
                # The link label is not a reliable document title. Provenance
                # remains in the body; we do not manufacture metadata.
                emit(entity, pointer, url, None, None)

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
        url = linked[0].resolved_url
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
