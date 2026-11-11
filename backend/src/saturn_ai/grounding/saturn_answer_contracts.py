"""Stage 5D: immutable, bounded public answer/citation contracts.

Citation provenance is canonical backend data, never an assertion by the LLM.
A source_quote is an explicitly *non-entailing* extract, not a technical fact.
"""
from dataclasses import dataclass

from ..ingestion.support_catalog_adapter import CatalogOccurrence

MAX_ANSWER_STATEMENTS = 6
MAX_ANSWER_DOCUMENTS = 10
MAX_ANSWER_CITATIONS = 16
MAX_ANSWER_TEXT_CHARS = 12_000

ANSWER_STATUSES = frozenset((
    "answered", "partial", "clarification", "needs_support", "error",
))


@dataclass(frozen=True)
class SaturnAnswerStatement:
    statement_id: str
    need_id: str
    statement_kind: str
    text: str
    citation_ids: tuple[str, ...]
    evidence_id: str | None = None
    document_id: str | None = None


@dataclass(frozen=True)
class SaturnCitation:
    citation_id: str
    source_type: str
    source_revision_id: str | None
    title: str
    canonical_url: str
    locator: str | None
    evidence_id: str | None = None
    document_id: str | None = None
    entity_id: str | None = None
    source_repository: str | None = None
    source_branch: str | None = None
    source_path: str | None = None
    source_commit_sha: str | None = None
    source_blob_sha: str | None = None
    source_content_sha256: str | None = None
    field_path: str | None = None
    relation_source_field_path: str | None = None
    pdf_bytes_sha256: str | None = None
    pdf_parser_version: str | None = None
    physical_page: int | None = None
    owner_entity_ids: tuple[str, ...] = ()
    source_revision_ids: tuple[str, ...] = ()
    source_locators: tuple[str, ...] = ()
    occurrences: tuple[CatalogOccurrence, ...] = ()
    document_kind: str | None = None
    document_version: str | None = None
    document_date: str | None = None
    extraction_status: str | None = None
    pdf_revision_id: str | None = None


@dataclass(frozen=True)
class SaturnAnswerResult:
    question_sha256: str
    snapshot_id: str
    bundle_id: str
    policy_revision: str
    status: str
    answer_text: str
    statements: tuple[SaturnAnswerStatement, ...]
    citations: tuple[SaturnCitation, ...]
    unresolved_need_ids: tuple[str, ...]
    reason_code: str | None
    diagnostics: tuple[tuple[str, int], ...]
