"""Immutable, Saturn-specific request evidence (Stage 5A).

These source-backed records are not legacy approval objects, answer claims, or
permission to skip the next operational-policy check.
"""
from dataclasses import dataclass

from ..ingestion.support_catalog_adapter import CatalogOccurrence

MAX_CONTEXT_EVIDENCE = 10
MAX_CONTEXT_DOCUMENTS = 10
MAX_CONTEXT_TEXT_CHARS = 20_000
MAX_SESSION_CONTEXTS = 16


class SaturnContextError(RuntimeError):
    """Stable safe reason code; never includes raw query, PDF text or URL."""
    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__("Saturn evidence context rejected: " + reason_code)


@dataclass(frozen=True)
class SaturnTypedEvidence:
    evidence_id: str
    evidence_type: str
    snapshot_id: str
    source_revision_id: str
    entity_id: str | None
    locator: str
    canonical_url: str | None
    source_text: str
    canonical_kind: str
    canonical_id: str
    # site_field only
    fact_id: str | None = None
    field_path: str | None = None
    raw_value_json: str | None = None
    normalized_value_json: str | None = None
    unit: str | None = None
    qualifiers_json: str | None = None
    # relation only
    relation_id: str | None = None
    subject_entity_id: str | None = None
    predicate: str | None = None
    object_entity_id: str | None = None
    source_field_path: str | None = None
    # pdf_passage only; the physical page is not an inferred page index
    pdf_document_id: str | None = None
    original_url: str | None = None
    pdf_revision_id: str | None = None
    bytes_sha256: str | None = None
    parser_version: str | None = None
    physical_page: int | None = None
    pdf_owner_entity_ids: tuple[str, ...] = ()
    pdf_source_locators: tuple[str, ...] = ()
    pdf_link_source_revision_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SaturnDocumentReference:
    """A catalog document MATCH; never a technical answer evidence unit."""
    document_id: str
    title: str
    kind: str
    version: str | None
    date: str | None
    original_url: str
    owner_entity_ids: tuple[str, ...]
    source_locators: tuple[str, ...]
    occurrences: tuple[CatalogOccurrence, ...]
    extraction_status: str | None
    pdf_revision_id: str | None


@dataclass(frozen=True)
class SaturnEvidenceContext:
    question: str
    question_sha256: str
    snapshot_id: str
    bundle_id: str
    mode: str
    policy_revision: str
    answer_evidence: tuple[SaturnTypedEvidence, ...]
    document_references: tuple[SaturnDocumentReference, ...]
    # Deliberately bounded, no request body, raw content or credentials.
    diagnostics: tuple[tuple[str, int], ...]
