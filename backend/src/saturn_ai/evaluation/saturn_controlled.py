"""Explicit controlled Stage 5E fault-injection measurements.

This is NOT a hidden/blind test or a proof that real contradictory source data
are correctly interpreted. Only source-authored OPEN calibration questions
are used. Fault classes are deliberately injected and labeled separately.
"""
from dataclasses import replace
from hashlib import sha256
import json
from unittest.mock import patch

from ..grounding.saturn_answer_assembly import SaturnAnswerAssemblyService
from ..grounding.saturn_claim_provider import SaturnFakeClaimProvider
from ..grounding.saturn_generation import SaturnClaimVerificationService
from ..grounding.saturn_sufficiency_gate import SaturnQuestionGate
from ..retrieval.saturn_channel import (
    SaturnOperationalPolicy, SaturnPolicyProvider,
    SaturnRetrievalService, build_saturn_retrieval_bundle,
)
from .saturn_answer_dataset import serialize_gold, validate_gold
from .saturn_answer_freeze import config_hash
from .saturn_answer_reporting import build_report, report_bytes
from .saturn_answer_scoring import score_answer
from .saturn_fixture import calibration_gold_bytes, fixture_snapshot
from .saturn_grounding import (
    SaturnEvaluationProfile, _run_question, _code_revision,
)

CONTROL_CASES = {
    "C01": "blocked_source_evidence_policy",
    "C02": "forced_retrieval_technical_failure",
    "C03": "synthetically_injected_gate_conflict",
}


def controlled_report(*, code_revision=None):
    snapshot = fixture_snapshot()
    source = json.loads(calibration_gold_bytes(snapshot))
    source["dataset_id"] = "saturn-grounding-controlled-review-v0.1"
    source["cases"] = [c for c in source["cases"]
                       if c["case_id"] in CONTROL_CASES]
    source["author"] = "Stage 5E source-authored controlled faults"
    source["reviewer"] = "NOT AN INDEPENDENT BLIND"
    dataset = validate_gold(serialize_gold(source), snapshot,
                            split="synthetic_calibration")
    bundle = build_saturn_retrieval_bundle(snapshot)
    profile = SaturnEvaluationProfile("synthetic_calibration")
    verifier = SaturnClaimVerificationService(provider=SaturnFakeClaimProvider())
    assembly = SaturnAnswerAssemblyService(verifier=verifier)
    gate = SaturnQuestionGate()

    ordinary = SaturnRetrievalService()
    ordinary.publish(bundle)
    result = {}
    for case in dataset.cases:
        if case.case_id == "C01":
            blocked = case.required[0].evidence_id
            service = SaturnRetrievalService(
                policy_provider=SaturnPolicyProvider(SaturnOperationalPolicy(
                    "controlled-revocation", blocked_evidence_ids=frozenset({blocked}))))
            service.publish(bundle)
            answer, trace = _run_question(service, assembly, gate,
                                          verifier, case.question, profile)
        elif case.case_id == "C02":
            with patch.object(SaturnRetrievalService, "_search_captured",
                              side_effect=RuntimeError("injected backend failure")):
                answer, trace = _run_question(ordinary, assembly, gate,
                                              verifier, case.question, profile)
        else:
            # The real v0.1 snapshot has no conflicting version of this fact;
            # this trace and answer simulate a conflict *without* corrupting
            # the trusted site fixture or altering production Stage 5B.
            _, observed = _run_question(ordinary, assembly, gate,
                                        verifier, case.question, profile)
            missing = next(c for c in json.loads(calibration_gold_bytes(snapshot))["cases"]
                           if c["case_id"] == "C18")
            negative_answer, _ = _run_question(ordinary, assembly, gate, verifier,
                                               missing["question"], profile)
            answer = replace(negative_answer, question_sha256=sha256(
                case.question.encode("utf-8")).hexdigest())
            trace = replace(observed, need_findings=tuple(
                replace(f, status="potential_conflict")
                for f in observed.need_findings))
        result[case.case_id] = score_answer(case, answer, snapshot, trace)
    outcomes = tuple(result[c.case_id] for c in dataset.cases)
    report = build_report(dataset, outcomes, code_revision=code_revision or _code_revision(),
                          config_hash=config_hash(mode="lexical", top_k=10),
                          bundle=bundle, blind_status="NOT_RUN")
    report["measurement_kind"] = "synthetic_controlled_fault_injection"
    report["injection_by_case_id"] = CONTROL_CASES
    report["evidence_conflict_is_simulated"] = True
    report["blind_or_real_sample"] = False
    report["production_readiness"] = False
    return report


if __name__ == "__main__":
    report = controlled_report()
    summary = {
        "measurement_kind": report["measurement_kind"],
        "code_revision": report["runtime"]["code_revision"],
        "dataset_sha256": report["dataset"]["sha256"],
        "metrics": report["metrics"],
        "injection_by_case_id": report["injection_by_case_id"],
        "failed_case_ids": report["failed_case_ids"],
        "independent_blind_evaluation": report["independent_blind_evaluation"],
    }
    print("SATURN_CONTROLLED_REPORT_BEGIN")
    print(report_bytes(report).decode("utf-8"), end="")
    print("SATURN_CONTROLLED_REPORT_END")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
