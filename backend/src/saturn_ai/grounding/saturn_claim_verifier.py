"""Independent canonical-snapshot verification of Stage 5C atomic drafts.

Only Stage 5A issued evidence tied to a currently eligible Stage 5B finding
may reach these functions. Neither draft text nor its claimed provenance is
trusted. Validation is exact, not semantic entailment.
"""
import json

from ..ingestion.saturn_contracts import canonical_json, stable_id
from .saturn_claim_contracts import MAX_QUOTE_CHARS, SaturnVerifiedClaim
from .saturn_claim_provider import _field_payload, _relation_payload


def _substantive(raw):
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return False
    return not (
        value is None or
        (isinstance(value, (str, list, dict)) and not value) or
        (isinstance(value, str) and not value.strip())
    )


def verify_pinned_draft(snapshot, need, evidence, draft):
    """Return (verified_claim | None, safe_reason | None).

    Reconstruct exact source identity from the pinned canonical snapshot.
    Do NOT trust supplied payload, context text alone, retrieval score, or URL.
    """
    if (draft.need_id != need.need_id or
            draft.evidence_id != evidence.evidence_id or
            evidence.snapshot_id != snapshot.snapshot_id):
        return None, "claim_identity_mismatch"

    units = {unit.evidence_id: unit for unit in snapshot.answer_evidence}
    pointers = {ptr.evidence_id: ptr for ptr in snapshot.evidence_pointers}
    unit, pointer = units.get(evidence.evidence_id), pointers.get(evidence.evidence_id)
    if (unit is None or pointer is None or
            unit.evidence_type != evidence.evidence_type or
            unit.source_revision_id != evidence.source_revision_id or
            unit.entity_id != evidence.entity_id or
            unit.locator != evidence.locator or
            unit.text != evidence.source_text or
            pointer.canonical_kind != evidence.canonical_kind or
            pointer.canonical_id != evidence.canonical_id or
            pointer.canonical_url != evidence.canonical_url):
        return None, "claim_identity_mismatch"

    if draft.claim_kind == "field_value" and need.kind == "field_value":
        if (evidence.evidence_type != "site_field" or
                evidence.canonical_kind != "SiteFact"):
            return None, "claim_identity_mismatch"
        fact = next((x for x in snapshot.facts
                     if x.fact_id == evidence.fact_id), None)
        if (fact is None or pointer.canonical_id != fact.fact_id or
                fact.entity_id != need.entity_id or
                fact.field_path != need.field_path or
                fact.source_revision_id != evidence.source_revision_id or
                fact.entity_id != evidence.entity_id or
                fact.field_path != evidence.field_path or
                fact.raw_value_json != evidence.raw_value_json or
                fact.normalized_value_json != evidence.normalized_value_json or
                fact.unit != evidence.unit or
                fact.qualifiers_json != evidence.qualifiers_json or
                not _substantive(fact.raw_value_json)):
            return None, "claim_identity_mismatch"
        # Build the expected payload from *canonical* fact values, not from
        # the provider. Representation changes (0,5 -> 0.5) are never allowed.
        expected = canonical_json({
            "entity_id": fact.entity_id,
            "field_path": fact.field_path,
            "fact_id": fact.fact_id,
            "source_revision_id": fact.source_revision_id,
            "raw_value_json": fact.raw_value_json,
            "unit": fact.unit,
            "qualifiers_json": fact.qualifiers_json,
        })
        if draft.asserted_payload != expected:
            return None, "claim_value_mismatch"
        return SaturnVerifiedClaim(
            need.need_id, evidence.evidence_id, "field_value",
            "verified_structured", expected, fact.source_revision_id,
            fact.entity_id,
        ), None

    if draft.claim_kind == "relation" and need.kind == "relation":
        if (evidence.evidence_type != "relation" or
                evidence.canonical_kind != "SiteRelation"):
            return None, "claim_identity_mismatch"
        rel = next((r for r in snapshot.relations
                    if r.relation_id == evidence.relation_id), None)
        if (rel is None or pointer.canonical_id != rel.relation_id or
                rel.subject_entity_id != need.entity_id or
                rel.predicate != need.predicate or
                rel.object_entity_id != need.object_entity_id or
                rel.subject_entity_id != evidence.subject_entity_id or
                rel.predicate != evidence.predicate or
                rel.object_entity_id != evidence.object_entity_id or
                rel.source_revision_id != evidence.source_revision_id or
                rel.source_field_path != evidence.source_field_path or
                evidence.entity_id != rel.subject_entity_id):
            return None, "claim_identity_mismatch"
        expected = canonical_json({
            "relation_id": rel.relation_id,
            "subject_entity_id": rel.subject_entity_id,
            "predicate": rel.predicate,
            "object_entity_id": rel.object_entity_id,
            "source_revision_id": rel.source_revision_id,
            "source_field_path": rel.source_field_path,
        })
        if draft.asserted_payload != expected:
            return None, "claim_relation_mismatch"
        return SaturnVerifiedClaim(
            need.need_id, evidence.evidence_id, "relation",
            "verified_structured", expected, rel.source_revision_id,
            rel.subject_entity_id,
        ), None

    if (draft.claim_kind == "passage_quote" and
            need.kind in ("field_value", "relation") and
            evidence.evidence_type in ("site_passage", "pdf_passage")):
        if (type(draft.asserted_payload) is not str or
                not 0 < len(draft.asserted_payload) <= MAX_QUOTE_CHARS or
                draft.asserted_payload not in unit.text):
            return None, "claim_quote_mismatch"
        page = None
        if evidence.evidence_type == "site_passage":
            entity = next((x for x in snapshot.entities
                           if x.entity_id == evidence.entity_id), None)
            if (entity is None or pointer.canonical_kind != "SiteEntity" or
                    pointer.canonical_id != entity.entity_id or
                    entity.source_revision_id != evidence.source_revision_id or
                    need.entity_id != entity.entity_id):
                return None, "claim_identity_mismatch"
            # Stage 5A separately authenticates the exact passage segmentation.
        else:
            if pointer.canonical_kind != "PdfRevision":
                return None, "claim_identity_mismatch"
            pdf = next((p for p in snapshot.pdf_revisions
                        if stable_id("saturn-pdf-revision-v1", p.document_id,
                                     p.url, p.bytes_sha256, p.parser_version)
                        == evidence.source_revision_id), None)
            match = next((m for m in snapshot.document_matches
                          if pdf is not None and
                          m.document.document_id == pdf.document_id), None)
            if (pdf is None or match is None or
                    pointer.canonical_id != evidence.source_revision_id or
                    evidence.pdf_revision_id != evidence.source_revision_id or
                    evidence.pdf_document_id != pdf.document_id or
                    evidence.bytes_sha256 != pdf.bytes_sha256 or
                    evidence.parser_version != pdf.parser_version or
                    evidence.original_url != pdf.url or
                    evidence.physical_page != unit.page_number or
                    evidence.physical_page is None or
                    not 1 <= evidence.physical_page <= pdf.page_count or
                    evidence.pdf_owner_entity_ids != match.document.owner_entity_ids or
                    need.entity_id not in evidence.pdf_owner_entity_ids or
                    match.pdf_revision_id != evidence.pdf_revision_id or
                    match.extraction_status != "extracted"):
                return None, "claim_identity_mismatch"
            page = unit.page_number
        # An exact quote is NOT verified engineering truth.
        return SaturnVerifiedClaim(
            need.need_id, evidence.evidence_id, "passage_quote",
            "quote_integrity_verified", draft.asserted_payload,
            evidence.source_revision_id, evidence.entity_id, page,
        ), None

    return None, "claim_identity_mismatch"
