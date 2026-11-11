"""Stage 5G API contract checks on SYNTHETIC fixtures only.

These tests do not constitute actual Saturn-site calibration or model metrics.
"""
import json
import unittest

from saturn_ai.evaluation.saturn_fixture import (
    calibration_gold_bytes, fixture_snapshot,
)
from saturn_ai.grounding.saturn_claim_provider import SaturnFakeClaimProvider
from saturn_ai.real_corpus_evaluation import evaluate_open_real_gold
from saturn_ai.real_corpus_stand import RealStand
from saturn_ai.retrieval.saturn_channel import build_saturn_retrieval_bundle
from saturn_ai.evaluation.saturn_answer_dataset import GoldValidationError


def fixture_open_dataset(snapshot):
    obj = json.loads(calibration_gold_bytes(snapshot))
    obj["dataset_id"] = "synthetic-test-only-real-profile-contract"
    obj["author"] = "Synthetic test fixture"
    obj["reviewer"] = "Synthetic test contract review only"
    obj["split"] = "real_sample"
    for case in obj["cases"]:
        case["split"] = "real_sample"
    return json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")


class RealOpenCalibrationContractTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = fixture_snapshot()
        self.stand = RealStand(
            self.snapshot, build_saturn_retrieval_bundle(self.snapshot),
            {"source_repository": "TEST_FIXTURE_ONLY",
             "source_commit": "a" * 40, "source_tree": "c" * 40},
        )

    def test_fake_profile_reuses_independent_scorer_without_blind_claim(self):
        data = fixture_open_dataset(self.snapshot)
        report = evaluate_open_real_gold(
            data, self.stand, draft_provider=SaturnFakeClaimProvider(),
            code_revision="f" * 40)
        self.assertEqual(report["profile"], "real_open_calibration_fake")
        self.assertEqual(report["independent_blind_evaluation"], "NOT_RUN")
        self.assertFalse(report["production_readiness"])
        self.assertEqual(report["provider_identity"]["provider_type"], "fake")
        self.assertEqual(report["performance"]["inference_status"], "FAKE_ONLY")
        self.assertEqual(report["metrics"]["case_count"], 28)
        self.assertEqual(report["metrics"]["fully_correct_all"]["denominator"], 28)

    def test_wrong_snapshot_gold_is_rejected_before_runtime(self):
        data = json.loads(fixture_open_dataset(self.snapshot))
        data["snapshot_id"] = "0" * 64
        with self.assertRaises(GoldValidationError):
            evaluate_open_real_gold(
                json.dumps(data).encode("utf-8"), self.stand,
                draft_provider=SaturnFakeClaimProvider(),
                code_revision="f" * 40)


if __name__ == "__main__":
    unittest.main()
