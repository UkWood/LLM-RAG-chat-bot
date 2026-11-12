"""CR-02..CR-05 controlled synthetic real-blind infrastructure regressions.

This is NOT an independent blind experiment: test fixtures, mock completions,
and local files are deliberately synthetic, never measured real model weights.
"""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import json
import unittest

from saturn_ai.evaluation.saturn_answer_dataset import (
    GoldValidationError, validate_gold,
)
from saturn_ai.evaluation.saturn_answer_freeze import (
    BlindIntegrityError, canonical_digest,
)
from saturn_ai.real_blind import (
    RealBlindRun, _validate_real_report, run_real_blind,
    validate_real_freeze,
)
from saturn_ai.real_blind_assurance import (
    real_dataset_contract, threshold_scorecard,
    validate_independent_attestation, validate_model_identity,
    check_local_artifact_bytes, verify_completed_report,
)
from unit.real_blind_testkit import (
    CODE, prepare_controlled, fake_empty_completion,
)


def check(env, **kwargs):
    return validate_real_freeze(
        env["freeze"], stand=env["stand"], model=env["model"],
        code_revision=CODE, attestation=env["attestation"],
        open_calibration_bytes=env["open_bytes"],
        model_file=env["model_file"],
        tokenizer_file=env["tokenizer_file"], **kwargs,
    )


def dataset(env, raw=None):
    return validate_gold(
        json.dumps(raw or env["gold"], sort_keys=True).encode("utf-8"),
        env["stand"].snapshot, split="real_sample")


def synthetic_outcomes():
    rows = []
    cases = []
    for i in range(40):
        positive = i < 24
        status = "answered" if positive else "needs_support"
        cases.append(SimpleNamespace(
            case_id=str(i), required=[
                SimpleNamespace(evidence_id="evidence-"+str(i), kind="field")
            ] if positive else [],
        ))
        rows.append(SimpleNamespace(
            case_id=str(i), expected_status=status, actual_status=status,
            fully_correct=True,
            technical_assertion_count=1 if positive else 0,
            source_unsupported_claim_count=0,
            citation_count=1 if positive else 0,
            valid_citation_count=1 if positive else 0,
            answer_assertion_count=1 if positive else 0,
            source_hit_at_5=True if positive else None,
            document_hit_at_5=None,
        ))
    return rows, cases


class RealFreezeAndDatasetTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.env = prepare_controlled(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def test_CR04_T01_model_and_source_freeze_full_preflight(self):
        self.assertEqual(check(self.env), self.env["freeze"])

    def test_CR04_T02_changed_model_id_digest_or_parameters_fail(self):
        env = self.env
        for field, value in (
            ("model_name", "swapped-model"), ("model_artifact_sha256", "0"*64),
            ("tokenizer_revision", "different-tokenizer"),
            ("prompt_template_sha256", "0"*64),
            ("generation_parameters", {"temperature": 1}),
        ):
            with self.subTest(field=field):
                changed = dict(env["freeze"])
                identity = dict(changed["model_identity"])
                identity[field] = value
                changed["model_identity"] = identity
                with self.assertRaises(BlindIntegrityError):
                    validate_real_freeze(
                        changed, stand=env["stand"], model=env["model"],
                        code_revision=CODE, attestation=env["attestation"],
                        open_calibration_bytes=env["open_bytes"],
                        model_file=env["model_file"],
                        tokenizer_file=env["tokenizer_file"])

    def test_CR04_T03_absent_independent_attestation_or_modified_receipt(self):
        env = self.env
        with self.assertRaises(BlindIntegrityError):
            validate_real_freeze(
                env["freeze"], stand=env["stand"], model=env["model"],
                code_revision=CODE, open_calibration_bytes=env["open_bytes"],
                model_file=env["model_file"], tokenizer_file=env["tokenizer_file"])
        tampered = dict(env["attestation"])
        tampered["reviewer"] = env["freeze"]["dataset_author"]
        with self.assertRaises(BlindIntegrityError):
            validate_independent_attestation(
                tampered, env["freeze"]["model_identity"],
                independent_author=env["freeze"]["dataset_author"])
        tampered["reviewer"] = "Different external reviewer"
        with self.assertRaises(BlindIntegrityError):
            validate_real_freeze(
                env["freeze"], stand=env["stand"], model=env["model"],
                code_revision=CODE, attestation=tampered,
                open_calibration_bytes=env["open_bytes"],
                model_file=env["model_file"], tokenizer_file=env["tokenizer_file"])

    def test_CR04_T04_changed_artifact_bytes_or_freeze_block_start(self):
        env = self.env
        env["model_file"].write_bytes(b"changed model bytes")
        with self.assertRaises(BlindIntegrityError):
            check(env)
        env["model_file"].write_bytes(b"synthetic testing bytes for a model, not weights")
        mutated = dict(env["freeze"])
        mutated["config_fingerprint"] = "0"*64
        with self.assertRaises(BlindIntegrityError):
            validate_real_freeze(
                mutated, stand=env["stand"], model=env["model"],
                code_revision=CODE, attestation=env["attestation"],
                open_calibration_bytes=env["open_bytes"],
                model_file=env["model_file"], tokenizer_file=env["tokenizer_file"])

    def test_CR03_T01_24_positive_16_supported_negative(self):
        env = self.env
        gold = dataset(env)
        real_dataset_contract(gold, open_calibration_bytes=env["open_bytes"])

    def test_CR03_T02_23_positive_17_negative_or_partial_rejected(self):
        env = self.env
        raw = json.loads(json.dumps(env["gold"]))
        raw["cases"][0]["expected_status"] = "needs_support"
        raw["cases"][0]["category"] = "missing_field"
        raw["cases"][0]["negative_reason"] = "A missing source field was requested."
        raw["cases"][0]["required"] = []
        with self.assertRaises(BlindIntegrityError):
            real_dataset_contract(dataset(env, raw),
                                  open_calibration_bytes=env["open_bytes"])
        raw = json.loads(json.dumps(env["gold"]))
        for item in raw["cases"][24:]:
            item["expected_status"] = "partial"
            item["category"] = "multi_need"
            item["required"] = [raw["cases"][0]["required"][0]]
        with self.assertRaises(BlindIntegrityError):
            real_dataset_contract(dataset(env, raw),
                                  open_calibration_bytes=env["open_bytes"])

    def test_CR03_T03_negative_reason_bad_category_and_open_duplicate(self):
        env = self.env
        raw = json.loads(json.dumps(env["gold"]))
        raw["cases"][24]["negative_reason"] = "x"
        with self.assertRaises(BlindIntegrityError):
            real_dataset_contract(dataset(env, raw),
                                  open_calibration_bytes=env["open_bytes"])
        raw = json.loads(json.dumps(env["gold"]))
        raw["cases"][24]["category"] = "arbitrary_label"
        with self.assertRaises(BlindIntegrityError):
            real_dataset_contract(dataset(env, raw),
                                  open_calibration_bytes=env["open_bytes"])
        raw = json.loads(json.dumps(env["gold"]))
        raw["cases"][24]["question"] = json.loads(
            env["open_bytes"])["cases"][0]["question"]
        with self.assertRaises(BlindIntegrityError):
            real_dataset_contract(dataset(env, raw),
                                  open_calibration_bytes=env["open_bytes"])

    def test_CR03_T04_invalid_pointer_duplicate_id_or_sha_rejected(self):
        env = self.env
        raw = json.loads(json.dumps(env["gold"]))
        raw["cases"][0]["required"][0]["evidence_id"] = "forged"
        with self.assertRaises(GoldValidationError):
            dataset(env, raw)
        raw = json.loads(json.dumps(env["gold"]))
        raw["cases"][1]["case_id"] = raw["cases"][0]["case_id"]
        with self.assertRaises(GoldValidationError):
            dataset(env, raw)
        mutated = dict(env["freeze"])
        mutated["dataset_sha256"] = "0"*64
        with self.assertRaises(BlindIntegrityError):
            validate_real_freeze(
                mutated, stand=env["stand"], model=env["model"],
                code_revision=CODE, attestation=env["attestation"],
                open_calibration_bytes=env["open_bytes"],
                model_file=env["model_file"], tokenizer_file=env["tokenizer_file"])


class ThresholdScorecardTests(unittest.TestCase):
    def setUp(self):
        with TemporaryDirectory() as temp:
            self.thresholds = prepare_controlled(temp)["freeze"]["thresholds"]
        self.rows, self.cases = synthetic_outcomes()

    def score(self, rows=None, cases=None):
        return threshold_scorecard(
            rows if rows is not None else self.rows,
            gold_cases=cases if cases is not None else self.cases,
            thresholds=self.thresholds)

    def test_CR02_T01_all_met(self):
        score = self.score()
        self.assertEqual(score["overall"], "MET")
        self.assertTrue(score["quality_target_met"])
        self.assertEqual(len(score["criteria"]), 6)

    def test_CR02_T02_positive_and_negative_failures(self):
        for idx in (0, 24):
            changed = list(self.rows)
            changed[idx] = SimpleNamespace(**vars(changed[idx]))
            changed[idx].fully_correct = False
            self.assertEqual(self.score(changed)["overall"], "NOT_MET")

    def test_CR02_T03_invalid_citation_or_unsupported_claim(self):
        changed = list(self.rows)
        changed[0] = SimpleNamespace(**vars(changed[0]))
        changed[0].valid_citation_count = 0
        self.assertEqual(self.score(changed)["criteria"]["invalid_citations"]["result"], "NOT_MET")
        changed = list(self.rows)
        changed[0] = SimpleNamespace(**vars(changed[0]))
        changed[0].source_unsupported_claim_count = 1
        self.assertEqual(self.score(changed)["criteria"]["unsupported_claims"]["result"], "NOT_MET")

    def test_CR02_T04_unmeasured_retrieval_not_successful(self):
        changed = list(self.rows)
        changed[0] = SimpleNamespace(**vars(changed[0]))
        changed[0].source_hit_at_5 = None
        self.assertEqual(self.score(changed)["criteria"]["required_retrieval_measured"]["result"], "NOT_MET")
        self.assertFalse(self.score(changed)["quality_target_met"])
        cases = [SimpleNamespace(case_id=str(i), required=[]) for i in range(40)]
        self.assertEqual(self.score(cases=cases)["criteria"]["required_retrieval_measured"]["result"], "NOT_APPLICABLE")
        self.assertFalse(self.score(cases=cases)["quality_target_met"])


class FullSyntheticBlindLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = TemporaryDirectory()
        cls.env = prepare_controlled(cls.directory.name)
        cls.receipts_dir = Path(cls.directory.name) / "receipts"
        cls.report_path = Path(cls.directory.name) / "report.json"
        with patch("saturn_ai.grounding.saturn_local_provider._post_loopback",
                   side_effect=fake_empty_completion):
            cls.report = run_real_blind(
                stand=cls.env["stand"], model=cls.env["model"],
                freeze=cls.env["freeze"], dataset_path=cls.env["blind_path"],
                report_path=cls.report_path, receipts_dir=cls.receipts_dir,
                attestation=cls.env["attestation"],
                open_calibration_bytes=cls.env["open_bytes"],
                model_file=cls.env["model_file"],
                tokenizer_file=cls.env["tokenizer_file"], code_revision=CODE,
            )
        cls.complete_path = next(cls.receipts_dir.glob("*.COMPLETE.json"))

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_CR05_T01_full_synthetic_40_case_lifecycle(self):
        self.assertEqual(self.report["metrics"]["case_count"], 40)
        self.assertEqual(self.report["independent_blind_evaluation"], "RUN")
        self.assertEqual(self.report["production_readiness"], False)
        self.assertFalse(self.report["quality_target_met"])
        self.assertTrue(next(self.receipts_dir.glob("*.START.json")).is_file())
        self.assertTrue(self.complete_path.is_file())
        self.assertTrue(verify_completed_report(
            report_path=self.report_path, complete_path=self.complete_path,
            expected_freeze_sha256=canonical_digest(self.env["freeze"])))

    def test_CR05_T02_T03_no_repeat_START_or_COMPLETE(self):
        run = RealBlindRun(
            freeze=self.env["freeze"], receipts_dir=self.receipts_dir,
            report_path=self.report_path)
        with self.assertRaises(BlindIntegrityError):
            run.start()
        run.started = True
        with self.assertRaises(BlindIntegrityError):
            run.complete(
                self.report_path.read_bytes(),
                dataset_bytes=self.env["blind_bytes"],
                snapshot=self.env["stand"].snapshot,
                open_calibration_bytes=self.env["open_bytes"])

    def test_CR05_T05_T06_T07_T09_modified_outcome_citations_totals_or_case_missing(self):
        ds = dataset(self.env)
        for mutation in ("outcome", "citation", "summary", "missing_case"):
            with self.subTest(mutation=mutation):
                report = json.loads(self.report_path.read_bytes())
                if mutation == "outcome":
                    report["cases"][0]["actual_status"] = "answered"
                elif mutation == "citation":
                    report["cases"][0]["valid_citation_count"] += 1
                elif mutation == "summary":
                    report["metrics"]["case_count"] = 39
                else:
                    report["cases"].pop()
                with self.assertRaises(BlindIntegrityError):
                    _validate_real_report(report, self.env["freeze"], ds)

    def test_CR05_T08_persisted_report_tampering_detected(self):
        original = self.report_path.read_bytes()
        try:
            self.report_path.write_bytes(original + b" ")
            with self.assertRaises(BlindIntegrityError):
                verify_completed_report(
                    report_path=self.report_path,
                    complete_path=self.complete_path,
                    expected_freeze_sha256=canonical_digest(self.env["freeze"]))
        finally:
            self.report_path.write_bytes(original)

    def test_CR05_T10_attacker_changes_runtime_model_or_threshold_summary(self):
        ds = dataset(self.env)
        for field in ("runtime", "threshold_scorecard", "quality_target_met"):
            report = json.loads(self.report_path.read_bytes())
            if field == "runtime":
                report["runtime"]["code_revision"] = "0" * 40
            elif field == "threshold_scorecard":
                report["threshold_scorecard"]["overall"] = "MET"
            else:
                report["quality_target_met"] = True
            with self.subTest(field=field), self.assertRaises(BlindIntegrityError):
                _validate_real_report(report, self.env["freeze"], ds)

    def test_CR05_T04_T13_T14_bad_dataset_hash_leaves_FAILED_and_prevents_reuse(self):
        with TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.json"
            receipts = Path(tmp) / "receipts"
            wrong = Path(tmp) / "wrong-dataset.json"
            wrong.write_bytes(b"{\"invalid\":true}")
            with self.assertRaises(BlindIntegrityError):
                run_real_blind(
                    stand=self.env["stand"], model=self.env["model"],
                    freeze=self.env["freeze"], dataset_path=wrong,
                    report_path=report, receipts_dir=receipts,
                    attestation=self.env["attestation"],
                    open_calibration_bytes=self.env["open_bytes"],
                    model_file=self.env["model_file"],
                    tokenizer_file=self.env["tokenizer_file"],
                    code_revision=CODE,
                )
            self.assertTrue(next(receipts.glob("*.START.json")).exists())
            self.assertTrue(next(receipts.glob("*.FAILED.json")).exists())
            with self.assertRaises(BlindIntegrityError):
                RealBlindRun(
                    freeze=self.env["freeze"], receipts_dir=receipts,
                    report_path=report).start()

    def test_CR05_T11_T12_technical_failures_and_unmeasured_retrieval_do_not_pass(self):
        outcomes = self.report["cases"]
        self.assertEqual(len(outcomes), 40)
        # All negative technical errors must be counted as failed, not correct
        # needs_support, and no unmeasured eligible positive can score PASS.
        ds = dataset(self.env)
        scored = threshold_scorecard(
            [SimpleNamespace(**x) for x in outcomes],
            gold_cases=ds.cases, thresholds=self.env["freeze"]["thresholds"])
        self.assertEqual(scored["overall"], "NOT_MET")
        self.assertFalse(scored["quality_target_met"])


if __name__ == "__main__":
    unittest.main()
