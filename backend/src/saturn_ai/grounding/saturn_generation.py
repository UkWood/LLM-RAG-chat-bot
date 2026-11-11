"""Stage 5C bounded offline proposals and independent source verification.

Uses a fresh Stage 5B assessment, only a Stage 5A issued context, and never
exposes a snapshot manager or unrestricted corpus to the draft provider.
"""
from .saturn_claim_contracts import (
    MAX_CLAIM_PAYLOAD_CHARS, MAX_CLAIM_PROPOSALS, MAX_GENERATION_EVIDENCE, MAX_GENERATION_NEEDS,
    MAX_GENERATION_TEXT_CHARS, SaturnClaimDraft, SaturnClaimVerificationResult,
    SaturnGenerationEvidence, SaturnGenerationNeed, SaturnGenerationRequest,
    SaturnRejectedClaim,
)
from .saturn_claim_provider import SaturnClaimDraftProvider, SaturnFakeClaimProvider
from .saturn_local_provider import SaturnLocalClaimProvider
from .saturn_claim_verifier import verify_pinned_draft
from .saturn_context import SaturnAnswerSession
from .saturn_contracts import SaturnContextError, SaturnEvidenceContext
from .saturn_sufficiency_gate import SaturnQuestionGate


def _result(context, revision, assessment, *, verified=(), rejected=(),
            state="incomplete", error=None):
    verified, rejected = tuple(verified), tuple(rejected)
    structured = {c.need_id for c in verified
                  if c.verification_status == "verified_structured"}
    unresolved = tuple(n.need_id for n, f in zip(assessment.needs, assessment.findings)
                       if f.status != "document_found" and n.need_id not in structured)
    if (state == "complete" and (rejected or unresolved or
            any(f.status not in ("covered_structured", "document_found")
                for f in assessment.findings))):
        state = "incomplete"
    counts = {
        "verified_structured": len(structured),
        "verified_quotes": sum(c.verification_status == "quote_integrity_verified"
                               for c in verified),
        "rejected_claims": len(rejected),
        "unresolved_needs": len(unresolved),
    }
    if error:
        counts[error] = 1
    for r in rejected:
        counts[r.reason_code] = counts.get(r.reason_code, 0) + 1
    return SaturnClaimVerificationResult(
        context.question_sha256, context.snapshot_id, context.bundle_id,
        revision, verified, rejected, unresolved, state, tuple(sorted(counts.items())))


def _select(assessment, context):
    indexed = {e.evidence_id: e for e in context.answer_evidence}
    needs, evidence, selected = [], [], []
    for need, finding in zip(assessment.needs, assessment.findings):
        if finding.status not in ("covered_structured", "text_candidate"):
            continue
        valid = []
        for eid in finding.evidence_ids:
            item = indexed.get(eid)
            if item is None:
                raise SaturnContextError("evidence_integrity_failure")
            if ((finding.status == "covered_structured" and
                 ((need.kind == "field_value" and item.evidence_type == "site_field") or
                  (need.kind == "relation" and item.evidence_type == "relation"))) or
                (finding.status == "text_candidate" and
                 item.evidence_type in ("site_passage", "pdf_passage"))):
                valid.append(item)
        if not valid:
            raise SaturnContextError("evidence_integrity_failure")
        item = min(valid, key=lambda e: e.evidence_id)
        needs.append(SaturnGenerationNeed(
            need.need_id, need.kind, need.entity_id, need.field_path,
            need.predicate, need.object_entity_id))
        evidence.append(SaturnGenerationEvidence(
            need.need_id, item.evidence_id, item.evidence_type,
            item.source_revision_id, item.entity_id, item.fact_id, item.field_path,
            item.raw_value_json, item.unit, item.qualifiers_json, item.relation_id,
            item.subject_entity_id, item.predicate, item.object_entity_id,
            item.source_field_path, item.source_text))
        selected.append((need, item))
    return tuple(needs), tuple(evidence), tuple(selected)


def _verification(snapshot, drafts, selected):
    allowed = {(need.need_id, item.evidence_id): (need, item)
               for need, item in selected}
    valid_needs = {need.need_id for need, _ in selected}
    used, verified, rejected = set(), [], []
    for index, draft in enumerate(drafts):
        pair = (draft.need_id, draft.evidence_id)
        if draft.need_id not in valid_needs:
            rejected.append(SaturnRejectedClaim(index, "unknown_need_id"))
            continue
        if pair not in allowed:
            rejected.append(SaturnRejectedClaim(index, "unknown_evidence_id"))
            continue
        if draft.need_id in used:
            rejected.append(SaturnRejectedClaim(index, "claim_duplicate"))
            continue
        used.add(draft.need_id)
        need, item = allowed[pair]
        try:
            claim, reason = verify_pinned_draft(snapshot, need, item, draft)
        except Exception:
            # An unexpected verifier failure is not a source mismatch.
            # Abort the entire operation; never publish preceding claims or
            # expose internal diagnostics through exception chaining.
            raise SaturnContextError("claim_verification_unavailable") from None
        if claim is not None:
            verified.append(claim)
        else:
            rejected.append(SaturnRejectedClaim(index,
                                                reason or "claim_identity_mismatch"))
    return tuple(verified), tuple(rejected)


class SaturnClaimVerificationService:
    """Only two exact, audited draft-provider classes are allowed in the pilot.

    The Stage 5C verifier remains independent of either provider's claims.
    """

    def __init__(self, *, provider: SaturnClaimDraftProvider):
        self._provider = provider
        self._gate = SaturnQuestionGate()

    def verify(self, *, session: SaturnAnswerSession,
               context: SaturnEvidenceContext) -> SaturnClaimVerificationResult:
        if (not isinstance(session, SaturnAnswerSession) or
                not isinstance(context, SaturnEvidenceContext)):
            raise SaturnContextError("context_identity_mismatch")
        assessment = self._gate.assess(session=session, context=context)
        session.recheck_policy(context)
        findings = assessment.findings
        if assessment.gate_status in (
                "unresolved_question", "needs_clarification", "potential_conflict"):
            return _result(context, session.recheck_policy(context), assessment)
        if findings and all(f.status == "document_found" for f in findings):
            return _result(context, session.recheck_policy(context), assessment,
                           state="generation_not_required")
        needs, evidence, selected = _select(assessment, context)
        if not needs:
            return _result(context, session.recheck_policy(context), assessment)
        if (len(needs) > MAX_GENERATION_NEEDS or
                len(evidence) > MAX_GENERATION_EVIDENCE or
                sum(len(x.source_text) for x in evidence) > MAX_GENERATION_TEXT_CHARS):
            return _result(context, session.recheck_policy(context), assessment,
                           state="resource_budget_exceeded",
                           error="claim_budget_exceeded")
        if type(self._provider) not in (SaturnFakeClaimProvider, SaturnLocalClaimProvider):
            return _result(context, session.recheck_policy(context), assessment,
                           state="failed", error="provider_not_allowed")
        revision = session.recheck_policy(context)
        request = SaturnGenerationRequest(
            context.question_sha256, context.snapshot_id, context.bundle_id,
            revision, needs, evidence)
        try:
            drafts = self._provider.generate(request)
        except Exception:
            session.recheck_policy(context)
            return _result(context, session.recheck_policy(context), assessment,
                           state="failed", error="provider_unavailable")
        session.recheck_policy(context)
        if type(drafts) is not tuple:
            return _result(context, session.recheck_policy(context), assessment,
                           state="failed", error="invalid_provider_output")
        if len(drafts) > MAX_CLAIM_PROPOSALS:
            return _result(context, session.recheck_policy(context), assessment,
                           state="resource_budget_exceeded",
                           error="claim_budget_exceeded")
        if any(type(x) is not SaturnClaimDraft for x in drafts):
            return _result(context, session.recheck_policy(context), assessment,
                           state="failed", error="invalid_provider_output")
        if any(type(x.need_id) is not str or type(x.evidence_id) is not str or
               type(x.claim_kind) is not str or type(x.asserted_payload) is not str
               for x in drafts):
            return _result(context, session.recheck_policy(context), assessment,
                           state="failed", error="invalid_provider_output")
        # Reject oversized untrusted strings before any canonical comparison.
        # Need/evidence IDs are fixed-length hashes in the real contracts.
        if any(len(x.need_id) > 128 or len(x.evidence_id) > 128 or
               len(x.claim_kind) > 64 or
               len(x.asserted_payload) > MAX_CLAIM_PAYLOAD_CHARS
               for x in drafts):
            return _result(context, session.recheck_policy(context), assessment,
                           state="resource_budget_exceeded",
                           error="claim_budget_exceeded")
        # External provider is NOT called within _evaluate_pinned. Acquire
        # session lock for post-provider verification and final assembly only.
        with session._lock:
            (verified, rejected), final_revision = session._evaluate_pinned(
                context, lambda snapshot: _verification(snapshot, drafts, selected))
            supported = {c.need_id for c in verified
                         if c.verification_status == "verified_structured"}
            complete = (not rejected and
                        all(f.status in ("covered_structured", "document_found")
                            for f in findings) and
                        all(f.status != "covered_structured" or
                            n.need_id in supported
                            for n, f in zip(assessment.needs, findings)))
            return _result(context, final_revision, assessment,
                           verified=verified, rejected=rejected,
                           state="complete" if complete else "incomplete")
