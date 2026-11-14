"""Offline Saturn 4A->4B->5A->5B->5C->5D->5E runner.

The runtime boundary receives only the question and a predetermined profile.
Gold objects are read by the scorer after that boundary returns. No network,
models, API keys, legacy GroundedResult or production deployment.
"""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import argparse
import json
import subprocess
import sys

from ..grounding.saturn_answer_contracts import SaturnAnswerResult
from ..grounding.saturn_answer_assembly import SaturnAnswerAssemblyService
from ..grounding.saturn_claim_provider import SaturnFakeClaimProvider
from ..grounding.saturn_generation import SaturnClaimVerificationService
from ..grounding.saturn_sufficiency_gate import SaturnQuestionGate
from ..ingestion.saturn_contracts import canonical_json
from ..retrieval.saturn_channel import SaturnRetrievalService, build_saturn_retrieval_bundle
from .saturn_answer_dataset import validate_gold
from .saturn_answer_freeze import (
    BlindRun, EVALUATOR_REVISION, BlindIntegrityError, config_hash, validate_freeze)
from .saturn_answer_reporting import build_report, report_bytes
from .saturn_answer_scoring import SaturnStageTrace, score_answer
from .saturn_fixture import fixture_snapshot, calibration_gold_bytes


@dataclass(frozen=True)
class SaturnEvaluationProfile:
    name: str
    mode: str = "lexical"
    top_k: int = 10

    def __post_init__(self):
        if (self.name not in ("synthetic_calibration", "synthetic_blind", "real_sample") or
                self.mode != "lexical" or type(self.top_k) is not int or
                self.top_k != 10):
            raise ValueError("Unsupported or unfrozen Saturn v0.1 evaluation profile")


def _code_revision():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True,
            text=True, timeout=5)
        code = result.stdout.strip()
        if len(code) == 40 and all(c in "0123456789abcdef" for c in code):
            return code
    except (OSError, subprocess.SubprocessError):
        pass
    return "unavailable"


def _safe_error(snapshot_id, bundle_id, question):
    return SaturnAnswerResult(
        question_sha256=sha256(question.encode("utf-8")).hexdigest(),
        snapshot_id=snapshot_id, bundle_id=bundle_id,
        policy_revision="evaluation-error",
        status="error", answer_text="Не удалось выполнить проверку.",
        statements=(), citations=(), unresolved_need_ids=(),
        reason_code="evaluation_runtime_failure",
        diagnostics=(("evaluation_runtime_failure", 1),),
    )


def _run_question(service, assembly, gate, verifier, question, profile):
    """One pinned bundle/session. No case labels or gold enter runtime."""
    pinned_bundle = None
    try:
        with service.open_answer_session() as session:
            with session._lock:
                bundle = session._bundle
                pinned_bundle = bundle
                # The diagnostic search uses the SAME captured bundle as
                # build_context; never service.search_saturn(active) here.
                retrieval = service._search_captured(
                    bundle, question, profile.mode, profile.top_k)
                context = session.build_context(
                    question, mode=profile.mode, top_k=profile.top_k)
                if (retrieval.snapshot_id != context.snapshot_id or
                        retrieval.bundle_id != context.bundle_id or
                        retrieval.index_manifest != bundle.manifest or
                        tuple(c.evidence_id for c in retrieval.answer_evidence) !=
                        tuple(e.evidence_id for e in context.answer_evidence) or
                        tuple(d.match.document.document_id for d in retrieval.document_matches) !=
                        tuple(d.document_id for d in context.document_references)):
                    raise ValueError("pinned diagnostic context drift")
                # Stage 5D calls 5C exactly once. Its internal diagnostic
                # result is the same verified generation used for final answer.
                # gate/verifier arguments are retained for v0.1 caller ABI,
                # but MUST NOT be invoked independently here.
                answer, assessment, verified = assembly._assemble_diagnostics(
                    session=session, context=context)
                if any((item.snapshot_id != context.snapshot_id or
                        item.bundle_id != context.bundle_id or
                        item.question_sha256 != context.question_sha256)
                       for item in (assessment, verified, answer)):
                    raise ValueError("stage identity drift")
                policy = service.policy_provider.capture()
                trace = SaturnStageTrace(
                    snapshot_id=context.snapshot_id,
                    retrieval_diagnostics_complete=True,
                    bundle_id=context.bundle_id,
                    question_sha256=context.question_sha256,
                    ranked_evidence_ids=tuple(c.evidence_id for c in retrieval.answer_evidence),
                    selected_evidence_ids=tuple(e.evidence_id for e in context.answer_evidence),
                    selected_document_ids=tuple(d.document_id for d in context.document_references),
                    ranked_document_ids=tuple(d.match.document.document_id
                                              for d in retrieval.document_matches),
                    parsed_need_kinds=tuple(n.kind for n in assessment.needs),
                    finding_statuses=tuple(f.status for f in assessment.findings),
                    needs=assessment.needs,
                    need_findings=assessment.findings,
                    verified_evidence_ids=tuple(c.evidence_id for c in verified.verified_claims
                                                if c.verification_status == "verified_structured"),
                    verified_need_ids=tuple(c.need_id for c in verified.verified_claims
                                             if c.verification_status == "verified_structured"),
                    policy_blocked_evidence_ids=tuple(sorted(policy.blocked_evidence_ids)),
                    policy_blocked_document_ids=tuple(sorted(policy.blocked_document_ids)),
                    policy_blocked_source_revision_ids=tuple(sorted(policy.blocked_source_revision_ids)),
                    policy_blocked_entity_ids=tuple(sorted(policy.blocked_entity_ids)),
                )
                return answer, trace
    except Exception:
        # Error is not a missing-source/refusal result. No question/source text.
        bundle = pinned_bundle or service.capture()
        return _safe_error(bundle.snapshot.snapshot_id,
                           bundle.manifest.bundle_id, question), SaturnStageTrace(
                               technical_failure=True, snapshot_id=bundle.snapshot.snapshot_id,
                               bundle_id=bundle.manifest.bundle_id,
                               question_sha256=sha256(question.encode("utf-8")).hexdigest())


def evaluate(dataset_bytes, snapshot, *, profile: SaturnEvaluationProfile,
             code_revision=None, blind_status="NOT_RUN",
             experiment_id=None):
    """Real offline pipeline for every case, then independently score its output."""
    dataset = validate_gold(dataset_bytes, snapshot, split=profile.name)
    bundle = build_saturn_retrieval_bundle(snapshot)
    service = SaturnRetrievalService()
    service.publish(bundle)
    verifier = SaturnClaimVerificationService(provider=SaturnFakeClaimProvider())
    gate = SaturnQuestionGate()
    assembly = SaturnAnswerAssemblyService(verifier=verifier)
    outcomes = []
    for case in dataset.cases:
        # Only the question string crosses the application boundary.
        answer, trace = _run_question(service, assembly, gate, verifier,
                                      case.question, profile)
        outcomes.append(score_answer(case, answer, snapshot, trace))
    report = build_report(
        dataset, outcomes, code_revision=code_revision or _code_revision(),
        config_hash=config_hash(mode=profile.mode, top_k=profile.top_k),
        bundle=bundle, mode=profile.mode, top_k=profile.top_k,
        blind_status=blind_status, experiment_id=experiment_id)
    return report


def _calibration_snapshot(profile_name):
    if profile_name not in ("synthetic_calibration", "synthetic_blind"):
        raise ValueError("Real sample needs independently supplied real snapshot")
    # Blind must use a separately fixed snapshot, not merely this test fixture.
    return fixture_snapshot()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline Saturn grounded-answer evaluation")
    parser.add_argument("--profile", choices=("calibration", "blind", "real_sample"),
                        default="calibration")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--generate-calibration", action="store_true")
    parser.add_argument("--emit-open-json", action="store_true")
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--receipts-dir", type=Path, default=Path("evaluation/experiments"))
    args = parser.parse_args(argv)
    if args.profile == "real_sample":
        parser.error("Real sample requires a separately supplied trusted pinned snapshot loader")
    if args.generate_calibration and args.profile != "calibration":
        parser.error("Only open calibration data can be generated by coding session B")
    if args.emit_open_json and args.profile != "calibration":
        parser.error("Raw dataset/report output is allowed only for open synthetic calibration")
    if not args.generate_calibration and args.report is None:
        parser.error("--report is required")
    snapshot = _calibration_snapshot(
        "synthetic_blind" if args.profile == "blind" else "synthetic_calibration")
    if args.generate_calibration:
        contents = calibration_gold_bytes(snapshot)
        args.dataset.parent.mkdir(parents=True, exist_ok=True)
        with args.dataset.open("xb") as output:
            output.write(contents)
        if args.emit_open_json:
            print("SATURN_OPEN_DATASET_BEGIN")
            print(contents.decode("utf-8"), end="")
            print("SATURN_OPEN_DATASET_END")
        print("dataset_sha256=" + sha256(contents).hexdigest())
        return 0
    raw = args.dataset.read_bytes()
    split = "synthetic_calibration" if args.profile == "calibration" else "synthetic_blind"
    profile = SaturnEvaluationProfile(split)
    blind = None
    code_revision = _code_revision()
    if args.profile == "blind":
        if code_revision == "unavailable":
            parser.error("Exact Git SHA required before blind START")
        if args.freeze is None:
            parser.error("--freeze required for blind evaluation")
        freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
        validate_freeze(freeze, code_revision=code_revision, dataset_bytes=raw,
                        snapshot=snapshot, mode=profile.mode, top_k=profile.top_k)
        blind = BlindRun(freeze=freeze, receipts_dir=args.receipts_dir,
                         report_path=args.report)
        # Durable START before parsing ANY independent gold case label.
        blind.start()
    try:
        report = evaluate(
            raw, snapshot, profile=profile, code_revision=code_revision,
            blind_status="RUN" if blind else "NOT_RUN",
            experiment_id=blind.freeze["experiment_id"] if blind else None)
        data = report_bytes(report)
        if blind:
            if len(report["cases"]) != blind.freeze["expected_case_count"]:
                raise BlindIntegrityError("case_count_mismatch")
            blind.complete(data, dataset_bytes=raw, snapshot=snapshot)
        else:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_bytes(data)
        if args.emit_open_json:
            print("SATURN_OPEN_REPORT_BEGIN")
            print(data.decode("utf-8"), end="")
            print("SATURN_OPEN_REPORT_END")
        m = report["metrics"]
        print("evaluation_profile=" + profile.name)
        print("positive_complete=" + canonical_json(m["positive_complete_answer"]))
        print("status_accuracy=" + canonical_json(m["status_accuracy"]))
        print("false_refusal=" + canonical_json(m["false_refusal"]))
        print("unsupported_claims=" + str(m["unsupported_claims"]["count"]))
        print("failed_case_ids=" + canonical_json(report["failed_case_ids"]))
        print("independent_blind_evaluation=" + report["independent_blind_evaluation"])
        return 0
    except Exception as exc:
        if blind:
            blind.fail(exc.code if isinstance(exc, BlindIntegrityError)
                       else "evaluation_failed")
        raise


if __name__ == "__main__":
    sys.exit(main())
