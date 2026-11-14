"""Stage 5D: deterministic Saturn answer assembly and final operational gate.

Only the public, issuing-session entrypoint can produce an answer. Stage 5C is
executed afresh; no caller-supplied verification object is an authorization.
All materialization happens from the original pinned snapshot under its session
lock. No external provider or retrieval is called inside the final read lock.
"""
from dataclasses import replace
import json

from ..ingestion.saturn_contracts import stable_id
from .saturn_answer_contracts import (
    ANSWER_STATUSES, MAX_ANSWER_CITATIONS, MAX_ANSWER_DOCUMENTS,
    MAX_ANSWER_STATEMENTS, MAX_ANSWER_TEXT_CHARS, SaturnAnswerResult,
    SaturnAnswerStatement,
)
from .saturn_answer_renderer import (
    document_reference, plain, render_answer, structured_field,
    structured_relation,
)
from .saturn_citations import claim_citation, document_citation
from .saturn_claim_contracts import (
    SaturnClaimDraft, SaturnClaimVerificationResult, SaturnVerifiedClaim,
)
from .saturn_claim_verifier import verify_pinned_draft
from .saturn_context import SaturnAnswerSession, _safe_policy
from .saturn_contracts import SaturnContextError, SaturnEvidenceContext
from .saturn_generation import SaturnClaimVerificationService
from .saturn_sufficiency_gate import SaturnQuestionGate

_FAILURE_STATES = frozenset(("failed", "resource_budget_exceeded"))
_COVERED = frozenset(("covered_structured", "document_found"))
_CLARIFY = frozenset(("needs_clarification", "potential_conflict",
                     "unresolved_question"))
_TECHNICAL = frozenset(("structured_field", "structured_relation"))
_ERROR_DIAGNOSTICS = frozenset((
    "provider_unavailable", "provider_not_allowed", "invalid_provider_output",
    "claim_budget_exceeded",
))


def _reject(code):
    raise SaturnContextError(code) from None


def _error_code(verification):
    if verification.verification_state == "resource_budget_exceeded":
        return "resource_budget_exceeded"
    codes = [key for key, count in verification.diagnostics
             if key in _ERROR_DIAGNOSTICS and type(count) is int and count > 0]
    return sorted(codes)[0] if codes else "claim_verification_unavailable"


def _check_identity(context, assessment, verification):
    if (type(verification) is not SaturnClaimVerificationResult or
            assessment.question_sha256 != context.question_sha256 or
            assessment.snapshot_id != context.snapshot_id or
            assessment.bundle_id != context.bundle_id or
            verification.question_sha256 != context.question_sha256 or
            verification.snapshot_id != context.snapshot_id or
            verification.bundle_id != context.bundle_id or
            type(verification.verified_claims) is not tuple or
            type(verification.rejected_claims) is not tuple or
            type(verification.unresolved_need_ids) is not tuple or
            type(verification.diagnostics) is not tuple or
            verification.verification_state not in (
                "complete", "incomplete", "failed", "generation_not_required",
                "resource_budget_exceeded") or
            len(assessment.needs) != len(assessment.findings) or
            len(assessment.needs) > MAX_ANSWER_STATEMENTS or
            any(n.need_id != f.need_id for n, f in
                zip(assessment.needs, assessment.findings)) or
            len({n.need_id for n in assessment.needs}) != len(assessment.needs) or
            len(verification.verified_claims) > MAX_ANSWER_STATEMENTS or
            any(type(c) is not SaturnVerifiedClaim for c in
                verification.verified_claims) or
            any(type(s) is not str for s in verification.unresolved_need_ids)):
        _reject("answer_integrity_failure")
    if verification.verification_state in _FAILURE_STATES and (
            verification.verified_claims or verification.rejected_claims):
        _reject("answer_integrity_failure")
    if (verification.verification_state == "generation_not_required" and
            (not assessment.findings or
             any(f.status != "document_found" for f in assessment.findings) or
             verification.verified_claims)):
        _reject("answer_integrity_failure")
    if (verification.verification_state == "complete" and
            (verification.rejected_claims or
             any(f.status not in _COVERED for f in assessment.findings))):
        _reject("answer_integrity_failure")


def _check_claim(snapshot, need, finding, evidence, claim):
    if (finding.status not in ("covered_structured", "text_candidate") or
            evidence.evidence_id not in finding.evidence_ids or
            claim.evidence_id != evidence.evidence_id or
            claim.need_id != need.need_id or
            claim.source_revision_id != evidence.source_revision_id or
            claim.verification_status not in ("verified_structured",
                                               "quote_integrity_verified") or
            (finding.status == "covered_structured" and
             claim.verification_status != "verified_structured") or
            (finding.status == "text_candidate" and
             claim.verification_status != "quote_integrity_verified")):
        _reject("answer_integrity_failure")
    try:
        independent, failure = verify_pinned_draft(
            snapshot, need, evidence, SaturnClaimDraft(
                claim.need_id, claim.evidence_id, claim.claim_kind,
                claim.canonical_payload))
    except Exception:
        _reject("claim_verification_unavailable")
    if failure is not None or independent != claim:
        _reject("answer_integrity_failure")
    try:
        if claim.verification_status == "verified_structured":
            payload = json.loads(claim.canonical_payload)
            if not isinstance(payload, dict):
                _reject("answer_integrity_failure")
        else:
            payload = None
    except (ValueError, TypeError):
        _reject("answer_integrity_failure")
    return payload


def _checked_entities(snapshot):
    result = {}
    for entity in snapshot.entities:
        if entity.entity_id in result:
            _reject("citation_identity_mismatch")
        result[entity.entity_id] = entity
    return result


def _published_policy(snapshot, result, policy):
    """Additional output-specific restrictions beyond Stage 5A context recheck.

    In particular, a relation's *object* and a citation's link-source/owner
    revisions must be evaluated, not merely the retrieval record's subject.
    """
    entities = _checked_entities(snapshot)
    for citation in result.citations:
        if (citation.source_revision_id in policy.blocked_source_revision_ids or
                citation.source_revision_id in policy.blocked_pdf_revision_ids or
                citation.evidence_id in policy.blocked_evidence_ids or
                citation.document_id in policy.blocked_document_ids or
                citation.pdf_revision_id in policy.blocked_pdf_revision_ids or
                citation.entity_id in policy.blocked_entity_ids or
                any(rev in policy.blocked_source_revision_ids
                    for rev in citation.source_revision_ids) or
                any(owner in policy.blocked_entity_ids or
                    owner not in entities or
                    entities[owner].source_revision_id in
                    policy.blocked_source_revision_ids
                    for owner in citation.owner_entity_ids)):
            _reject("policy_blocked")
    # A relation's *object* may be blocked even if the subject evidence is
    # allowed. Its ID was independently checked against the canonical payload
    # while building the statement, so no score-based relation lookup occurs.
    for statement in result.statements:
        if statement.statement_kind != "structured_relation":
            continue
        obj = entities.get(statement.object_entity_id)
        if obj is None:
            _reject("citation_identity_mismatch")
        if (obj.entity_id in policy.blocked_entity_ids or
                obj.source_revision_id in policy.blocked_source_revision_ids):
            _reject("policy_blocked")


def _make_statement(need, citation, kind, text, *, evidence_id=None,
                    document_id=None, object_entity_id=None):
    return SaturnAnswerStatement(
        statement_id=stable_id("saturn-answer-statement-v1", need.need_id,
                               evidence_id, document_id, kind, citation.citation_id),
        need_id=need.need_id, statement_kind=kind, text=text,
        citation_ids=(citation.citation_id,), evidence_id=evidence_id,
        document_id=document_id, object_entity_id=object_entity_id,
    )


def _build(snapshot, context, assessment, verification):
    _check_identity(context, assessment, verification)
    needs = assessment.needs
    if verification.verification_state in _FAILURE_STATES:
        return _result(context, "", "error", (), (), tuple(
            n.need_id for n in needs), _error_code(verification))

    if assessment.gate_status in _CLARIFY:
        return _result(context, "", "clarification", (), (),
                       tuple(n.need_id for n in needs),
                       "conflicting_evidence" if assessment.gate_status ==
                       "potential_conflict" else "question_ambiguous")

    by_evidence = {e.evidence_id: e for e in context.answer_evidence}
    by_document = {d.document_id: d for d in context.document_references}
    claims = {}
    for claim in verification.verified_claims:
        if claim.need_id in claims:
            _reject("answer_integrity_failure")
        claims[claim.need_id] = claim
    known_need_ids = {n.need_id for n in needs}
    if set(claims) - known_need_ids:
        _reject("answer_integrity_failure")
    if set(verification.unresolved_need_ids) - known_need_ids:
        _reject("answer_integrity_failure")

    entities = _checked_entities(snapshot)
    statements, citations, seen_citations, unresolved = [], [], {}, []
    supported = 0
    document_count = 0
    for need, finding in zip(needs, assessment.findings):
        claim = claims.get(need.need_id)
        if finding.status == "document_found":
            if (need.kind != "document_lookup" or
                    len(finding.document_ids) != 1):
                _reject("answer_integrity_failure")
            reference = by_document.get(finding.document_ids[0])
            if reference is None:
                _reject("citation_identity_mismatch")
            citation = document_citation(snapshot, reference, need)
            statement = _make_statement(
                need, citation, "document_reference",
                document_reference(reference), document_id=reference.document_id)
            document_count += 1
            supported += 1
        elif claim is not None:
            evidence = by_evidence.get(claim.evidence_id)
            if evidence is None:
                _reject("citation_identity_mismatch")
            payload = _check_claim(snapshot, need, finding, evidence, claim)
            citation = claim_citation(snapshot, evidence, claim, payload)
            if claim.verification_status == "quote_integrity_verified":
                # A verified quotation does not entail the engineering answer.
                # Its statement and citation are separately marked contextual;
                # render_answer deliberately excludes it from main answer_text.
                statement = _make_statement(
                    need, citation, "source_quote",
                    "Цитата источника (не подтверждает характеристику): " +
                    plain(claim.canonical_payload),
                    evidence_id=evidence.evidence_id)
                unresolved.append(need.need_id)
            elif claim.claim_kind == "field_value" and need.kind == "field_value":
                entity = entities.get(need.entity_id)
                if entity is None or claim.entity_id != entity.entity_id:
                    _reject("citation_identity_mismatch")
                statement = _make_statement(
                    need, citation, "structured_field", structured_field(
                        entity.title, payload["field_path"], payload["raw_value_json"],
                        payload["unit"], payload["qualifiers_json"]),
                    evidence_id=evidence.evidence_id)
                supported += 1
            elif claim.claim_kind == "relation" and need.kind == "relation":
                subject = entities.get(need.entity_id)
                obj = entities.get(need.object_entity_id)
                if (subject is None or obj is None or
                        payload["subject_entity_id"] != subject.entity_id or
                        payload["object_entity_id"] != obj.entity_id):
                    _reject("citation_identity_mismatch")
                statement = _make_statement(
                    need, citation, "structured_relation", structured_relation(
                        subject.title, payload["predicate"], obj.title),
                    evidence_id=evidence.evidence_id,
                    object_entity_id=obj.entity_id)
                supported += 1
            else:
                _reject("answer_integrity_failure")
        else:
            unresolved.append(need.need_id)
            continue
        statements.append(statement)
        existing = seen_citations.get(citation.citation_id)
        if existing is not None and existing != citation:
            _reject("citation_identity_mismatch")
        if existing is None:
            citations.append(citation)
            seen_citations[citation.citation_id] = citation

    if (len([s for s in statements if s.statement_kind in _TECHNICAL])
            > MAX_ANSWER_STATEMENTS or
            document_count > MAX_ANSWER_DOCUMENTS or
            len(citations) > MAX_ANSWER_CITATIONS):
        return _result(context, "", "error", (), (),
                       tuple(n.need_id for n in needs), "output_budget_exceeded")

    if (verification.verification_state == "complete" and unresolved) or (
            verification.verification_state == "generation_not_required" and
            unresolved):
        _reject("answer_integrity_failure")
    # If all needs are apparently satisfied but Stage 5C still rejected an
    # additional proposal, calling this 'partial' would falsely imply a
    # missing question need. Treat inconsistent all-covered output as an
    # explicit integrity error; publish no positive statements.
    if (supported == len(needs) and supported > 0 and
            (verification.rejected_claims or verification.unresolved_need_ids or
             verification.verification_state not in (
                 "complete", "generation_not_required"))):
        return _result(context, "", "error", (), (),
                       tuple(n.need_id for n in needs),
                       "answer_integrity_failure")
    # Rejected proposals prohibit a full positive answer, but cannot turn an
    # independently confirmed fact into an invented/unverified assertion.
    if (supported == len(needs) and supported > 0 and not
            verification.rejected_claims and not
            verification.unresolved_need_ids and
            verification.verification_state in ("complete",
                                                "generation_not_required") and
            all(f.status in _COVERED for f in assessment.findings)):
        status, reason = "answered", None
    elif supported:
        status, reason = "partial", "answer_incomplete"
    else:
        status, reason = "needs_support", "insufficient_evidence"
    return _result(context, "", status, tuple(statements), tuple(citations),
                   tuple(unresolved), reason)


def _result(context, revision, status, statements, citations, unresolved, reason):
    if status not in ANSWER_STATUSES:
        _reject("answer_integrity_failure")
    text = render_answer(status, statements)
    if len(text) > MAX_ANSWER_TEXT_CHARS:
        # Preserve ALL affected needs before fail-closed clearing of output.
        affected_need_ids = tuple(dict.fromkeys(
            [statement.need_id for statement in statements] + list(unresolved)))
        status, statements, citations = "error", (), ()
        reason = "output_budget_exceeded"
        unresolved = affected_need_ids
        text = render_answer(status, ())
    diagnostics = tuple(sorted((
        ("citation_count", len(citations)),
        ("document_statement_count", sum(
            s.statement_kind == "document_reference" for s in statements)),
        ("statement_count", len(statements)),
        ("technical_statement_count", sum(
            s.statement_kind in _TECHNICAL for s in statements)),
        ("unresolved_need_count", len(unresolved)),
    )))
    return SaturnAnswerResult(
        question_sha256=context.question_sha256,
        snapshot_id=context.snapshot_id, bundle_id=context.bundle_id,
        policy_revision=revision, status=status, answer_text=text,
        statements=statements, citations=citations,
        unresolved_need_ids=unresolved, reason_code=reason,
        diagnostics=diagnostics,
    )


class SaturnAnswerAssemblyService:
    """Public backend answer flow; no caller-provided claims or assessment."""

    def __init__(self, *, verifier: SaturnClaimVerificationService):
        if type(verifier) is not SaturnClaimVerificationService:
            raise TypeError("A Saturn claim verification service is required")
        self._verifier = verifier
        self._gate = SaturnQuestionGate()

    def assemble(self, *, session: SaturnAnswerSession,
                 context: SaturnEvidenceContext) -> SaturnAnswerResult:
        """Public entrypoint retains the exact original answer contract."""
        result, _, _ = self._assemble_once(session=session, context=context)
        return result

    def _assemble_diagnostics(self, *, session: SaturnAnswerSession,
                              context: SaturnEvidenceContext):
        """Internal Stage 5E trace of the SAME generation that produced the answer.

        No caller-supplied claims, assessment or provider output can enter this
        operation. The original verifier and final policy gate still run.
        """
        return self._assemble_once(session=session, context=context)

    def _assemble_once(self, *, session: SaturnAnswerSession,
                       context: SaturnEvidenceContext):
        if (not isinstance(session, SaturnAnswerSession) or
                not isinstance(context, SaturnEvidenceContext)):
            _reject("context_identity_mismatch")
        # Early ownership, fingerprint, and current policy checks.
        session.recheck_policy(context)
        # Stage 5C obtains its own fresh 5B finding and independent canonical
        # verification. No externally supplied frozen result is accepted.
        verification = self._verifier.verify(session=session, context=context)
        if type(verification) is not SaturnClaimVerificationResult:
            _reject("claim_verification_unavailable")
        # The pinned lock spans re-assessment, canonical citation assembly,
        # final policy capture and return. close() cannot overtake this window.
        with session._lock:
            session.recheck_policy(context)
            assessment = self._gate.assess(session=session, context=context)
            result, _ = session._evaluate_pinned(
                context, lambda snapshot: _build(
                    snapshot, context, assessment, verification))
            # Final check is *after* all canonical output has been constructed.
            revision = session.recheck_policy(context)
            policy = _safe_policy(session._service.policy_provider)
            _published_policy(session._bundle.snapshot, result, policy)
            # A revision-only change is permitted; revocation is not.
            revision = session.recheck_policy(context)
            policy = _safe_policy(session._service.policy_provider)
            _published_policy(session._bundle.snapshot, result, policy)
            if revision != policy.revision:
                _reject("policy_unavailable")
            return replace(result, policy_revision=revision), assessment, verification
