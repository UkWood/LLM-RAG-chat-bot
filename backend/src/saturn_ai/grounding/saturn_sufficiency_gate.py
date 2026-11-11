"""Stage 5B conservative evidence sufficiency gate.

Selected Stage 5A evidence is NOT an answer. No search, LLM, inferred relation,
unit conversion, answer status or final citation is performed here.
"""
from dataclasses import dataclass
import json
import re

from .saturn_context import SaturnAnswerSession
from .saturn_contracts import SaturnContextError, SaturnEvidenceContext
from .saturn_question_needs import SaturnQuestionNeed, parse_saturn_question_needs

_COVERED = frozenset(("covered_structured", "document_found"))
_POSITIVE = frozenset(("covered_structured", "document_found", "text_candidate"))


@dataclass(frozen=True)
class SaturnNeedFinding:
    need_id: str
    status: str
    evidence_ids: tuple[str, ...]
    document_ids: tuple[str, ...]
    reason_code: str


@dataclass(frozen=True)
class SaturnNeedsAssessment:
    question_sha256: str
    snapshot_id: str
    bundle_id: str
    policy_revision: str
    needs: tuple[SaturnQuestionNeed, ...]
    findings: tuple[SaturnNeedFinding, ...]
    gate_status: str
    diagnostics: tuple[tuple[str, int], ...]


def _finding(need, status, reason, *, evidence=(), documents=()):
    return SaturnNeedFinding(
        need.need_id, status,
        tuple(sorted({x.evidence_id for x in evidence})),
        tuple(sorted({x.document_id for x in documents})),
        reason,
    )


def _passage_candidates(need, context):
    """Only a candidate, even if the passage literally names the field.

    PDF passages must retain a canonical owner link to the requested entity.
    No semantic interpretation of Markdown/PDF is attempted.
    """
    label = need.field_path if need.kind == "field_value" else need.predicate
    if not label or need.entity_id is None:
        return ()
    escaped = re.escape(label)
    pattern = re.compile(r"(?<!\w)" + escaped + r"(?!\w)")
    return tuple(e for e in context.answer_evidence
                 if e.evidence_type in ("site_passage", "pdf_passage")
                 and ((e.evidence_type == "site_passage" and
                       e.entity_id == need.entity_id) or
                      (e.evidence_type == "pdf_passage" and
                       need.entity_id in e.pdf_owner_entity_ids))
                 and pattern.search(e.source_text) is not None)


def _comparison_status(evidence):
    """Only same scope/qualifiers/units are comparable.

    No conversion and no assumption that strings resembling decimal numbers
    are semantically equivalent. Multi-valued fields are not single-valued.
    """
    scopes = {(e.source_revision_id, e.unit, e.qualifiers_json)
              for e in evidence}
    if len(scopes) != 1:
        return "ambiguous", "incomparable_scope"
    # The strict parser cannot express qualifiers, so a conditional field
    # does not silently become an unconditional engineering answer.
    if any(e.qualifiers_json not in (None, "{}") for e in evidence):
        return "ambiguous", "unqualified_question"
    values = {e.raw_value_json for e in evidence}
    if len(values) == 1:
        normalized = {e.normalized_value_json for e in evidence}
        if len(normalized) > 1:
            return "ambiguous", "incomparable_normalization"
        return "covered_structured", "exact_field_evidence"
    try:
        decoded = [json.loads(value) for value in values]
    except (TypeError, ValueError):
        return "ambiguous", "incomparable_value"
    if any(isinstance(value, (list, dict, bool)) or value is None
           for value in decoded):
        return "ambiguous", "non_scalar_values"
    # Distinct numeric primitives in canonical JSON are directly comparable.
    if all(type(value) in (int, float) for value in decoded):
        return "potential_conflict", "different_numeric_values"
    if all(isinstance(value, str) for value in decoded):
        # Pure unsigned integer literal disagreement is directly observable;
        # no value conversion is needed to flag a *potential* conflict.
        if all(re.fullmatch(r"[0-9]+", value) for value in decoded):
            return "potential_conflict", "different_integer_literals"
        # Decimal notation, attached units, +/- or ranges have no approved
        # conversion/canonicalization in v0.1.
        if any(re.match(r"^[+\-\u2212]?\d", value) for value in decoded):
            return "ambiguous", "incomparable_numeric_literals"
        return "potential_conflict", "different_literal_values"
    return "ambiguous", "incomparable_value_types"


def _assess_need(need, context, snapshot, facts, relations):
    if need.kind == "unresolved":
        return _finding(need, "unresolved", "unsupported_question_form")
    if need.resolution_status == "ambiguous":
        return _finding(need, "ambiguous", "ambiguous_entity")
    if need.resolution_status != "resolved":
        return _finding(need, "missing_in_context", "entity_not_in_snapshot")

    if need.kind == "document_lookup":
        # An exact title is metadata ONLY, not a technical property.
        matches = tuple(doc for doc in context.document_references
                        if doc.title == need.document_title
                        and (need.entity_id is None or
                             need.entity_id in doc.owner_entity_ids))
        if len(matches) > 1:
            return _finding(need, "ambiguous", "ambiguous_document_title",
                            documents=matches)
        if matches:
            return _finding(need, "document_found", "exact_document_metadata",
                            documents=matches)
        return _finding(need, "missing_in_context", "document_not_in_context")

    if need.kind == "field_value":
        matches = []
        for item in context.answer_evidence:
            if (item.evidence_type != "site_field" or
                    item.entity_id != need.entity_id or
                    item.field_path != need.field_path):
                continue
            source = facts.get(item.fact_id)
            if (source is not None and item.canonical_kind == "SiteFact" and
                    item.canonical_id == source.fact_id and
                    source.entity_id == need.entity_id and
                    source.field_path == need.field_path and
                    source.source_revision_id == item.source_revision_id):
                matches.append(item)
        if matches:
            status, reason = _comparison_status(matches)
            return _finding(need, status, reason, evidence=matches)
        candidates = _passage_candidates(need, context)
        if candidates:
            return _finding(need, "text_candidate",
                            "passage_requires_claim_verification",
                            evidence=candidates)
        return _finding(need, "missing_in_context", "field_not_in_context")

    if need.kind == "relation":
        matches = []
        for item in context.answer_evidence:
            if (item.evidence_type != "relation" or
                    item.subject_entity_id != need.entity_id or
                    item.predicate != need.predicate or
                    item.object_entity_id != need.object_entity_id):
                continue
            source = relations.get(item.relation_id)
            if (source is not None and item.canonical_kind == "SiteRelation" and
                    item.canonical_id == source.relation_id and
                    source.subject_entity_id == need.entity_id and
                    source.predicate == need.predicate and
                    source.object_entity_id == need.object_entity_id and
                    source.source_revision_id == item.source_revision_id):
                matches.append(item)
        if matches:
            return _finding(need, "covered_structured", "exact_source_relation",
                            evidence=matches)
        return _finding(need, "missing_in_context", "relation_not_in_context")
    return _finding(need, "unresolved", "unsupported_need_kind")


def _aggregate(findings):
    statuses = {finding.status for finding in findings}
    if "potential_conflict" in statuses:
        return "potential_conflict"
    if "unresolved" in statuses:
        return "unresolved_question"
    if "ambiguous" in statuses:
        return "needs_clarification"
    if findings and all(x.status in _COVERED for x in findings):
        return "provisionally_covered"
    if any(x.status in _POSITIVE for x in findings) and len(findings) > 1:
        return "partially_covered"
    return "insufficient_evidence"


def _assess_pinned(context, snapshot):
    needs = parse_saturn_question_needs(context.question, snapshot)
    facts = {fact.fact_id: fact for fact in snapshot.facts}
    relations = {relation.relation_id: relation for relation in snapshot.relations}
    findings = tuple(_assess_need(need, context, snapshot, facts, relations)
                     for need in needs)
    # Every need must receive exactly one finding, including unparsed suffixes.
    if (len(needs) != len(findings) or
            len({need.need_id for need in needs}) != len(needs) or
            tuple(need.need_id for need in needs) !=
            tuple(finding.need_id for finding in findings)):
        raise SaturnContextError("evidence_integrity_failure")
    diagnostics_map = {"need_count": len(needs)}
    for status in sorted({finding.status for finding in findings}):
        diagnostics_map["finding_" + status] = sum(
            finding.status == status for finding in findings)
    return needs, findings, _aggregate(findings), tuple(sorted(diagnostics_map.items()))


class SaturnQuestionGate:
    """Public Stage 5B entrypoint; accepts only issuing-session contexts."""

    def assess(self, *, session: SaturnAnswerSession,
               context: SaturnEvidenceContext) -> SaturnNeedsAssessment:
        if not isinstance(session, SaturnAnswerSession):
            raise SaturnContextError("context_identity_mismatch")
        if not isinstance(context, SaturnEvidenceContext):
            raise SaturnContextError("context_identity_mismatch")
        # Stage 5A owns the pinned bundle and lock; no active snapshot capture.
        # Recheck both before AND after inspection. A policy revision change
        # without revocation is allowed and reflected in this assessment.
        (needs, findings, status, diagnostics), policy_revision = (
            session._evaluate_pinned(
                context, lambda snapshot: _assess_pinned(context, snapshot))
        )
        return SaturnNeedsAssessment(
            context.question_sha256, context.snapshot_id, context.bundle_id,
            policy_revision, needs, findings, status, diagnostics,
        )
