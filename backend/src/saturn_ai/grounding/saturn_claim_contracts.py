"""Stage 5C immutable offline generation and independently verified claim contracts.

All identifiers remain pinned to the Stage 5A session. These are not answer
statuses or final citations; the provider cannot award verification statuses.
"""
from dataclasses import dataclass


MAX_GENERATION_NEEDS = 6
MAX_GENERATION_EVIDENCE = 6
MAX_GENERATION_TEXT_CHARS = 8_000
MAX_CLAIM_PROPOSALS = 6
MAX_QUOTE_CHARS = 1_000


@dataclass(frozen=True)
class SaturnGenerationNeed:
    need_id: str
    kind: str
    entity_id: str | None
    field_path: str | None
    predicate: str | None
    object_entity_id: str | None


@dataclass(frozen=True)
class SaturnGenerationEvidence:
    """Minimal provider-facing selection; never includes URLs or the full corpus."""
    need_id: str
    evidence_id: str
    evidence_type: str
    source_revision_id: str
    entity_id: str | None
    fact_id: str | None
    field_path: str | None
    raw_value_json: str | None
    unit: str | None
    qualifiers_json: str | None
    relation_id: str | None
    subject_entity_id: str | None
    predicate: str | None
    object_entity_id: str | None
    source_field_path: str | None
    source_text: str


@dataclass(frozen=True)
class SaturnGenerationRequest:
    question_sha256: str
    snapshot_id: str
    bundle_id: str
    policy_revision: str
    needs: tuple[SaturnGenerationNeed, ...]
    evidence: tuple[SaturnGenerationEvidence, ...]


@dataclass(frozen=True)
class SaturnClaimDraft:
    need_id: str
    evidence_id: str
    claim_kind: str
    asserted_payload: str


@dataclass(frozen=True)
class SaturnVerifiedClaim:
    need_id: str
    evidence_id: str
    claim_kind: str
    verification_status: str
    canonical_payload: str
    source_revision_id: str
    entity_id: str | None
    # Source-derived, never provider-assigned PDF physical page.
    physical_page: int | None = None


@dataclass(frozen=True)
class SaturnRejectedClaim:
    """No untrusted provider payload, arbitrary IDs or source text are reflected."""
    proposal_index: int
    reason_code: str


@dataclass(frozen=True)
class SaturnClaimVerificationResult:
    question_sha256: str
    snapshot_id: str
    bundle_id: str
    policy_revision: str
    verified_claims: tuple[SaturnVerifiedClaim, ...]
    rejected_claims: tuple[SaturnRejectedClaim, ...]
    unresolved_need_ids: tuple[str, ...]
    verification_state: str
    diagnostics: tuple[tuple[str, int], ...]
