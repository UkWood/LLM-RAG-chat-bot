"""Offline-only deterministic draft provider used to test Stage 5C contracts."""
from typing import Protocol

from ..ingestion.saturn_contracts import canonical_json
from .saturn_claim_contracts import (
    MAX_QUOTE_CHARS, SaturnClaimDraft, SaturnGenerationRequest,
)


class SaturnClaimDraftProvider(Protocol):
    def generate(self, request: SaturnGenerationRequest) -> tuple[SaturnClaimDraft, ...]:
        ...


def _field_payload(evidence):
    return canonical_json({
        "entity_id": evidence.entity_id,
        "field_path": evidence.field_path,
        "fact_id": evidence.fact_id,
        "source_revision_id": evidence.source_revision_id,
        "raw_value_json": evidence.raw_value_json,
        "unit": evidence.unit,
        "qualifiers_json": evidence.qualifiers_json,
    })


def _relation_payload(evidence):
    return canonical_json({
        "relation_id": evidence.relation_id,
        "subject_entity_id": evidence.subject_entity_id,
        "predicate": evidence.predicate,
        "object_entity_id": evidence.object_entity_id,
        "source_revision_id": evidence.source_revision_id,
        "source_field_path": evidence.source_field_path,
    })


class SaturnFakeClaimProvider:
    """An allowlisted offline fixture, not a general provider or production model.

    Test cases may patch generate() to simulate malicious/unavailable providers.
    The verifier MUST distrust even the output of this exact class.
    """
    def generate(self, request: SaturnGenerationRequest) -> tuple[SaturnClaimDraft, ...]:
        proposals = []
        for item in request.evidence:
            if item.evidence_type == "site_field":
                kind, payload = "field_value", _field_payload(item)
            elif item.evidence_type == "relation":
                kind, payload = "relation", _relation_payload(item)
            elif item.evidence_type in ("site_passage", "pdf_passage"):
                kind, payload = "passage_quote", item.source_text[:MAX_QUOTE_CHARS]
            else:
                # Unknown types are never an invitation to invent a fact.
                continue
            proposals.append(SaturnClaimDraft(item.need_id, item.evidence_id, kind, payload))
        return tuple(proposals)
