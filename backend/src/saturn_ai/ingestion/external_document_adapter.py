"""External Document Adapter v0.1: trusted catalog -> immutable PDF evidence.

Pure catalog validation precedes any network activity. Transport, extraction and
revision cache are injected; this module does not use legacy Registry approvals.
No persistence, scheduler, OCR or retrieval is implemented.
"""
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import urlsplit, urlunsplit

from .external_document_transport import (
    DocumentError, DocumentFetchPolicy, HTTPSPdfTransport, validate_url,
)
from .external_document_extractor import (
    ExtractedPdf, PARSER_VERSION, SubprocessPdfExtractor, validate_extraction,
)
from .saturn_contracts import (
    EvidenceUnit, PdfRevision, canonical_json, stable_id,
)
from .support_catalog_adapter import SupportCatalogResult


class CatalogValidationError(ValueError):
    """A non-promotable/inconsistent catalog is refused before ALL requests."""


@dataclass(frozen=True)
class DocumentDiagnostic:
    document_id: str
    code: str


@dataclass(frozen=True)
class DocumentStatus:
    document_id: str
    status: str
    revision_id: str | None


@dataclass(frozen=True)
class DocumentAssociation:
    document_id: str
    revision_id: str | None
    owner_entity_ids: tuple[str, ...]
    source_locators: tuple[str, ...]
    source_revision_ids: tuple[str, ...]


@dataclass(frozen=True)
class CachedPdfExtraction:
    revision: PdfRevision
    extraction: ExtractedPdf


@dataclass(frozen=True)
class ExternalDocumentResult:
    statuses: tuple[DocumentStatus, ...]
    revisions: tuple[PdfRevision, ...]
    evidence: tuple[EvidenceUnit, ...]
    associations: tuple[DocumentAssociation, ...]
    diagnostics: tuple[DocumentDiagnostic, ...]
    cached_extractions: tuple[CachedPdfExtraction, ...]
    parser_version: str
    ready_for_promotion: bool
    complete: bool


def _canonical_resource(value: str) -> str:
    parts = urlsplit(value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def _check_catalog(catalog: SupportCatalogResult, policy: DocumentFetchPolicy) -> None:
    if not isinstance(catalog, SupportCatalogResult) or not catalog.ready_for_promotion:
        raise CatalogValidationError("Catalog must be a validated, promotable SupportCatalogResult")
    candidates = catalog.pdf_candidates
    if len(candidates) > policy.max_requests:
        raise CatalogValidationError("Catalog exceeds request budget")
    docs = {doc.document_id: doc for doc in catalog.documents}
    if len(docs) != len(catalog.documents):
        raise CatalogValidationError("Duplicate support document ID")
    ids = [candidate.document_id for candidate in candidates]
    if len(ids) != len(set(ids)):
        raise CatalogValidationError("Duplicate PDF candidate ID")
    for candidate in candidates:
        doc = docs.get(candidate.document_id)
        if (doc is None or doc.url != candidate.resolved_url or
                not candidate.owner_entity_ids or not candidate.source_locators or
                not candidate.source_revision_ids or
                doc.owner_entity_ids != candidate.owner_entity_ids or
                doc.source_locators != candidate.source_locators):
            raise CatalogValidationError("PDF candidate/document mismatch")
        groups = (
            candidate.owner_entity_ids, candidate.source_locators,
            candidate.source_revision_ids, candidate.raw_urls,
        )
        if any(type(group) is not tuple or not group or
               group != tuple(sorted(set(group))) or
               any(type(x) is not str or not x for x in group)
               for group in groups):
            raise CatalogValidationError("Ambiguous PDF candidate provenance")
        occurrences = [o for o in catalog.occurrences
                       if o.document_id == candidate.document_id]
        if not occurrences:
            raise CatalogValidationError("PDF candidate lacks source occurrences")
        if (candidate.owner_entity_ids != tuple(sorted({o.owner_entity_id for o in occurrences})) or
                candidate.source_locators != tuple(sorted({o.source_locator for o in occurrences})) or
                candidate.source_revision_ids != tuple(sorted({o.source_revision_id for o in occurrences})) or
                candidate.raw_urls != tuple(sorted({o.raw_url for o in occurrences}))):
            raise CatalogValidationError("Incomplete candidate provenance")
        for occurrence in occurrences:
            if (not occurrence.source_path or not occurrence.field_path or
                    not occurrence.owner_entity_id or not occurrence.source_revision_id or
                    occurrence.source_locator != occurrence.source_revision_id + "#" + occurrence.field_path or
                    _canonical_resource(occurrence.resolved_url) != doc.url):
                raise CatalogValidationError("Inconsistent PDF source locator")
        # Validate structure of every URL before the first request; policy-denied
        # hosts/paths are represented as per-document diagnostic statuses later.
        try:
            validate_url(candidate.resolved_url, policy)
        except DocumentError as exc:
            if exc.code == "invalid_url":
                raise CatalogValidationError("Malformed candidate URL") from None


def _revision_id(revision: PdfRevision) -> str:
    return stable_id("saturn-pdf-revision-v1", revision.document_id,
                     revision.url, revision.bytes_sha256, revision.parser_version)


def _text_hash(extraction: ExtractedPdf) -> str:
    payload = [[number, value] for number, value in extraction.pages]
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _evidence(revision: PdfRevision, extraction: ExtractedPdf) -> tuple[EvidenceUnit, ...]:
    revision_id = _revision_id(revision)
    return tuple(
        EvidenceUnit(
            evidence_id=stable_id("saturn-pdf-passage-v1", revision_id, number,
                                  sha256(text.encode("utf-8")).hexdigest()),
            evidence_type="pdf_passage", source_revision_id=revision_id,
            locator=revision.url + "#page=" + str(number),
            page_number=number, text=text,
        )
        for number, text in extraction.pages if text
    )


def _verified_cache(
    cached_extractions: tuple[CachedPdfExtraction, ...],
    policy: DocumentFetchPolicy,
) -> dict[str, CachedPdfExtraction]:
    result = {}
    if type(cached_extractions) is not tuple:
        raise TypeError("Cache must be an immutable tuple")
    for entry in cached_extractions:
        if not isinstance(entry, CachedPdfExtraction):
            raise TypeError("Cache must contain CachedPdfExtraction")
        revision = entry.revision
        if revision.extraction_state != "extracted":
            continue
        try:
            validate_extraction(entry.extraction, policy)
        except DocumentError:
            continue
        if _text_hash(entry.extraction) != revision.extracted_text_sha256:
            continue
        rid = _revision_id(revision)
        if rid in result and result[rid] != entry:
            raise CatalogValidationError("Conflicting immutable cached revision")
        result[rid] = entry
    return result


def adapt_external_documents(
    catalog: SupportCatalogResult,
    policy: DocumentFetchPolicy,
    *,
    transport=None,
    extractor=None,
    previous_cache: tuple[CachedPdfExtraction, ...] = (),
    parser_version: str = PARSER_VERSION,
) -> ExternalDocumentResult:
    """A complete fresh result; cache only reuses matching verified extraction.

    No HTTP request is attempted if upstream catalog integrity checks fail.
    The real worker requires explicit test/development opt-in and is not
    enabled for production, pending OS-level sandbox configuration.
    """
    if not isinstance(policy, DocumentFetchPolicy):
        raise TypeError("DocumentFetchPolicy is required")
    if not isinstance(parser_version, str) or not parser_version.strip():
        raise ValueError("Parser version required")
    _check_catalog(catalog, policy)
    cache = _verified_cache(previous_cache, policy)
    fetcher = transport if transport is not None else HTTPSPdfTransport()
    parser = extractor if extractor is not None else SubprocessPdfExtractor()
    statuses = []
    revisions = []
    evidence = []
    associations = []
    diagnostics = []
    new_cache = []
    for candidate in catalog.pdf_candidates:
        document_id = candidate.document_id
        association_args = (
            candidate.owner_entity_ids, candidate.source_locators,
            candidate.source_revision_ids,
        )
        revision = None
        revision_id = None
        status = None
        error = None
        try:
            validate_url(candidate.resolved_url, policy)
            data = fetcher.fetch(candidate.resolved_url, policy)
            if type(data) is not bytes or not data.startswith(b"%PDF-"):
                raise DocumentError("invalid_pdf")
            if len(data) > policy.max_pdf_bytes:
                raise DocumentError("size_limit")
            digest = sha256(data).hexdigest()
            revision = PdfRevision(
                document_id=document_id, url=candidate.resolved_url,
                bytes_sha256=digest, parser_version=parser_version,
                extraction_state="fetched",
            )
            revision_id = _revision_id(revision)
            cached = cache.get(revision_id)
            if cached is not None:
                extraction = cached.extraction
            else:
                extraction = parser.extract(data, policy)
                validate_extraction(extraction, policy)
            text_units = [value for _, value in extraction.pages if value]
            if text_units:
                revision = PdfRevision(
                    document_id=document_id, url=candidate.resolved_url,
                    bytes_sha256=digest, parser_version=parser_version,
                    extraction_state="extracted", page_count=extraction.page_count,
                    extracted_text_sha256=_text_hash(extraction),
                )
                evidence.extend(_evidence(revision, extraction))
                new_cache.append(CachedPdfExtraction(revision, extraction))
                if len(text_units) == extraction.page_count:
                    status = "extracted"
                else:
                    status = "partial_text"
                    diagnostics.append(DocumentDiagnostic(document_id, "ocr_required"))
            else:
                revision = PdfRevision(
                    document_id=document_id, url=candidate.resolved_url,
                    bytes_sha256=digest, parser_version=parser_version,
                    extraction_state="fetched", page_count=extraction.page_count,
                )
                status = "ocr_required"
                diagnostics.append(DocumentDiagnostic(document_id, "ocr_required"))
        except DocumentError as exc:
            error = exc.code
        except (OSError, ValueError, TypeError):
            error = "parser_error" if revision is not None else "network_error"
        if error:
            status = error
            diagnostics.append(DocumentDiagnostic(document_id, error))
            if revision is not None:
                revision = PdfRevision(
                    document_id=document_id, url=revision.url,
                    bytes_sha256=revision.bytes_sha256,
                    parser_version=parser_version,
                    extraction_state="failed",
                    page_count=revision.page_count,
                )
        statuses.append(DocumentStatus(document_id, status, revision_id))
        associations.append(DocumentAssociation(document_id, revision_id, *association_args))
        if revision is not None:
            revisions.append(revision)
    complete = all(s.status == "extracted" for s in statuses)
    return ExternalDocumentResult(
        statuses=tuple(statuses), revisions=tuple(revisions),
        evidence=tuple(evidence), associations=tuple(associations),
        diagnostics=tuple(diagnostics), cached_extractions=tuple(new_cache),
        parser_version=parser_version,
        ready_for_promotion=complete and catalog.ready_for_promotion,
        complete=complete,
    )
