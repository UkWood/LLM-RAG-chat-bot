"""CR-01 independent regression: one real 5C provider invocation per scored answer.

All cases use SYNTHETIC Saturn fixture. They cannot evidence local LLM quality.
"""
from hashlib import sha256
from unittest.mock import patch
import unittest

from saturn_ai.evaluation.saturn_fixture import fixture_snapshot
from saturn_ai.evaluation.saturn_grounding import SaturnEvaluationProfile, _run_question
from saturn_ai.grounding.saturn_answer_assembly import SaturnAnswerAssemblyService
from saturn_ai.grounding.saturn_claim_provider import SaturnFakeClaimProvider
from saturn_ai.grounding.saturn_generation import SaturnClaimVerificationService
from saturn_ai.grounding.saturn_sufficiency_gate import SaturnQuestionGate
from saturn_ai.retrieval.saturn_channel import (
    SaturnRetrievalService, build_saturn_retrieval_bundle,
)


QUESTION = "Device X: interface?"


def harness(snapshot=None):
    snapshot = snapshot or fixture_snapshot()
    service = SaturnRetrievalService()
    service.publish(build_saturn_retrieval_bundle(snapshot))
    verifier = SaturnClaimVerificationService(provider=SaturnFakeClaimProvider())
    return service, verifier, SaturnAnswerAssemblyService(verifier=verifier)


class SingleGenerationTraceTests(unittest.TestCase):
    def test_CR01_T01_T02_T03_stateful_provider_trace_matches_final_answer(self):
        service, verifier, assembly = harness()
        original = SaturnFakeClaimProvider.generate
        invoked = []

        def stateful(provider, request):
            invoked.append(request.question_sha256)
            return original(provider, request) if len(invoked) == 1 else ()

        with patch.object(SaturnFakeClaimProvider, "generate", stateful):
            answer, trace = _run_question(
                service, assembly, SaturnQuestionGate(), verifier,
                QUESTION, SaturnEvaluationProfile("synthetic_calibration"))
        self.assertEqual(len(invoked), 1)
        self.assertEqual(answer.status, "answered")
        self.assertEqual(
            {s.evidence_id for s in answer.statements if s.evidence_id},
            set(trace.verified_evidence_ids),
        )
        self.assertEqual(
            {s.need_id for s in answer.statements if s.evidence_id},
            set(trace.verified_need_ids),
        )
        self.assertFalse(trace.technical_failure)

    def test_CR01_T04_provider_failure_is_technical_error(self):
        service, verifier, assembly = harness()
        calls = []
        def unavailable(provider, request):
            calls.append(1)
            raise RuntimeError("synthetic_only")
        with patch.object(SaturnFakeClaimProvider, "generate", unavailable):
            answer, trace = _run_question(
                service, assembly, SaturnQuestionGate(), verifier,
                QUESTION, SaturnEvaluationProfile("synthetic_calibration"))
        self.assertEqual(len(calls), 1)
        self.assertEqual(answer.status, "error")
        self.assertEqual(answer.citations, ())
        self.assertEqual(trace.verified_evidence_ids, ())

    def test_CR01_T05_exact_snapshot_bundle_and_question_identity(self):
        service, verifier, assembly = harness()
        answer, trace = _run_question(
            service, assembly, SaturnQuestionGate(), verifier,
            QUESTION, SaturnEvaluationProfile("synthetic_calibration"))
        self.assertEqual(answer.snapshot_id, trace.snapshot_id)
        self.assertEqual(answer.bundle_id, trace.bundle_id)
        self.assertEqual(answer.question_sha256, trace.question_sha256)
        self.assertEqual(answer.question_sha256,
                         sha256(QUESTION.encode("utf-8")).hexdigest())

    def test_CR01_T06_publish_during_generation_keeps_pinned_snapshot(self):
        original = fixture_snapshot()
        changed = fixture_snapshot(site_commit="b" * 40)
        service, verifier, assembly = harness(original)
        old_bundle = service.capture()
        new_bundle = build_saturn_retrieval_bundle(changed)
        provider_original = SaturnFakeClaimProvider.generate
        calls = []

        def publish_during_generate(provider, request):
            calls.append(1)
            service.publish(new_bundle)
            return provider_original(provider, request)

        with patch.object(SaturnFakeClaimProvider, "generate", publish_during_generate):
            answer, trace = _run_question(
                service, assembly, SaturnQuestionGate(), verifier,
                QUESTION, SaturnEvaluationProfile("synthetic_calibration"))
        self.assertEqual(len(calls), 1)
        self.assertEqual(answer.status, "answered")
        self.assertEqual(answer.snapshot_id, old_bundle.snapshot.snapshot_id)
        self.assertEqual(trace.snapshot_id, old_bundle.snapshot.snapshot_id)
        self.assertNotEqual(service.capture().snapshot.snapshot_id, answer.snapshot_id)


if __name__ == "__main__":
    unittest.main()
