"""Bounded offline grounding contracts, separate from M1 and model metadata."""
from dataclasses import dataclass
from ..domain import Claim


@dataclass(frozen=True)
class QuestionPlan:
    entity_id: str
    aspect: str


@dataclass(frozen=True)
class GateResult:
    state: str
    reason: str
    evidence_ids: tuple[str,...] = ()


@dataclass(frozen=True)
class GroundedCitation:
    chunk_id: str
    source_id: str
    title: str
    url: str
    document_id: str
    content_hash: str
    source_commit: str | None
    heading_path: tuple[str,...]
    page_start: int | None
    page_end: int | None


@dataclass(frozen=True)
class GroundedResult:
    status: str
    gate_state: str
    reason_code: str | None
    snapshot_id: str
    claims: tuple[Claim,...] = ()
    sources: tuple[GroundedCitation,...] = ()
    test_only: bool = True
    schema_version: int = 1
