"""Explicit v2 plans, canonical projections and backend reference variants."""
from dataclasses import dataclass,field
from ..domain import Claim
from .contracts import GroundedCitation


@dataclass(frozen=True)
class SourceConstraints:
    document_kind: str = 'any'
    representation: str = 'any'


@dataclass(frozen=True)
class EvidenceNeed:
    entity_id: str
    predicate: str
    selector: str = ''
    constraints: SourceConstraints = field(default_factory=SourceConstraints)


@dataclass(frozen=True)
class QueryPlanV2:
    needs: tuple[EvidenceNeed,...]
    question_sha256: str
    config_revision: str


@dataclass(frozen=True)
class CanonicalSpan:
    chunk_id: str
    start: int
    end: int
    role: str


@dataclass(frozen=True)
class FactProjection:
    entity_id: str
    predicate: str
    value: str
    source_id: str
    spans: tuple[CanonicalSpan,...]
    unit: str
    group_id: str
    cardinality: str
    complete: bool
    representation: str
    selector: str = ''
    valid: bool = True
    complete_for_source: bool = False


@dataclass(frozen=True)
class TypedReference:
    kind: str
    entity_id: str
    source_id: str
    value: str
    title: str
    url: str
    document_id: str
    content_hash: str
    anchor_chunk_id: str
    page: int | None


@dataclass(frozen=True)
class NeedBinding:
    need_index: int
    evidence_ids: tuple[str,...]
    projection_ids: tuple[str,...] = ()
    reference: TypedReference | None = None


@dataclass(frozen=True)
class GateV2:
    state: str
    reason: str
    evidence_ids: tuple[str,...] = ()
    bindings: tuple[NeedBinding,...] = ()
    anchor_ids: tuple[str,...] = ()


@dataclass(frozen=True)
class GroundedResultV2:
    status: str
    gate_state: str
    reason_code: str | None
    snapshot_id: str
    claims: tuple[Claim,...] = ()
    sources: tuple[GroundedCitation,...] = ()
    references: tuple[TypedReference,...] = ()
    plan: QueryPlanV2 | None = None
    bindings: tuple[NeedBinding,...] = ()
    anchor_ids: tuple[str,...] = ()
    schema_version: int = 2
    test_only: bool = True
