"""CR-06 real open-calibration acceptance on synthetic *source-backed* fixtures.

Production validator and Stage 5E gold are exercised unchanged. These tests
simulate trusted reviewers on synthetic input and DO NOT establish real model
quality or certify any human review.
"""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest

from saturn_ai.evaluation.saturn_answer_dataset import validate_gold, serialize_gold
from saturn_ai.evaluation.saturn_fixture import calibration_gold_bytes
from saturn_ai.evaluation.saturn_answer_freeze import BlindIntegrityError, canonical_digest
from saturn_ai.real_blind import run_real_blind, validate_real_freeze
from saturn_ai.real_blind_assurance import (
    validate_open_real_calibration, real_dataset_contract,
)
from unit.real_blind_testkit import CODE, prepare_controlled


def mutated_bytes(env, edit):
    source = json.loads(env["open_bytes"])
    edit(source)
    return serialize_gold(source)


def review_for(env, data):
    content = json.loads(data)
    review = dict(env["open_review"])
    review.update({
        "dataset_sha256": sha256(data).hexdigest(),
        "dataset_id": content["dataset_id"],
        "snapshot_id": content["snapshot_id"],
        "corpus_hash": content["corpus_hash"],
        "case_count": len(content["cases"]),
        "reviewed_case_ids": [c["case_id"] for c in content["cases"]],
        "author": content["author"], "reviewer": content["reviewer"],
    })
    return review


class StrictOpenCalibrationPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.env = prepare_controlled(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def validate(self, data=None, review=None, digest=None):
        env = self.env
        data = env["open_bytes"] if data is None else data
        return validate_open_real_calibration(
            data, env["stand"].snapshot,
            expected_sha256=sha256(data).hexdigest() if digest is None else digest,
            review=review_for(env, data) if review is None else review,
            source_manifest_sha256=env["freeze"]["source_manifest_sha256"])

    def test_CR06_T01_valid_source_backed_real_sample_and_review_accepted(self):
        result = self.validate()
        self.assertEqual(result.split, "real_sample")
        self.assertEqual(len(result.cases), 28)
        self.assertTrue(any(c.required for c in result.cases))
        self.assertEqual(result.snapshot_id, self.env["stand"].snapshot.snapshot_id)
        self.assertEqual(result.sha256, self.env["freeze"]["open_calibration_sha256"])

    def test_CR06_T02_historical_synthetic_calibration_rejected(self):
        synthetic = calibration_gold_bytes(self.env["stand"].snapshot)
        with self.assertRaises(BlindIntegrityError):
            self.validate(synthetic)

    def test_CR06_T03_empty_cases_rejected(self):
        data = mutated_bytes(self.env, lambda raw: raw.update(cases=[]))
        with self.assertRaises(BlindIntegrityError):
            self.validate(data)

    def test_CR06_T04_T05_snapshot_and_corpus_binding(self):
        for key in ("snapshot_id", "corpus_hash"):
            with self.subTest(key=key):
                data = mutated_bytes(self.env, lambda raw: raw.update({key: "0"*64}))
                with self.assertRaises(BlindIntegrityError):
                    self.validate(data)

    def test_CR06_T06_forged_source_pointer_rejected(self):
        data = mutated_bytes(self.env, lambda raw:
            raw["cases"][0]["required"][0].update(evidence_id="forged-pointer"))
        with self.assertRaises(BlindIntegrityError):
            self.validate(data)

    def test_CR06_T07_mismatched_frozen_sha_rejected(self):
        with self.assertRaises(BlindIntegrityError):
            self.validate(digest="0"*64)

    def test_CR06_T08_24_cases_outside_calibration_window(self):
        data = mutated_bytes(self.env, lambda raw: raw.update(cases=raw["cases"][:24]))
        with self.assertRaises(BlindIntegrityError):
            self.validate(data)

    def test_CR06_T09_candidate_and_test_only_labels_rejected(self):
        transforms = (
            lambda raw: raw.update(dataset_id="candidate-only-source-draft"),
            lambda raw: raw["cases"][0].update(tags=["controlled_synthetic_fixture"]),
        )
        for transform in transforms:
            with self.subTest(transform=transform):
                data = mutated_bytes(self.env, transform)
                with self.assertRaises(BlindIntegrityError):
                    self.validate(data)

    def test_CR06_T10_open_and_blind_duplicate_detected(self):
        env = self.env
        source = json.loads(env["gold"])
        source["cases"][0]["question"] = json.loads(env["open_bytes"])["cases"][0]["question"]
        blind = validate_gold(serialize_gold(source), env["stand"].snapshot,
                              split="real_sample")
        with self.assertRaisesRegex(BlindIntegrityError, "blind_open_question_duplicate"):
            real_dataset_contract(blind, open_dataset=self.validate())

    def test_CR06_T11_invalid_open_preflight_never_reads_blind_gold(self):
        env = self.env
        path = Path(self.tmp.name) / "never-read-gold.json"
        path.write_bytes(env["blind_bytes"])
        original_read = Path.read_bytes
        observed = []
        def watch_read(p):
            if p == path:
                observed.append("blind-read-before-start")
                raise AssertionError("blind gold must not be read before START")
            return original_read(p)
        bad_open = mutated_bytes(env, lambda raw: raw.update(split="synthetic_calibration"))
        with patch.object(Path, "read_bytes", watch_read):
            with self.assertRaises(BlindIntegrityError):
                run_real_blind(
                    stand=env["stand"], model=env["model"],
                    freeze=env["freeze"], dataset_path=path,
                    report_path=Path(self.tmp.name)/"report.json",
                    receipts_dir=Path(self.tmp.name)/"receipts",
                    attestation=env["attestation"],
                    open_calibration_bytes=bad_open,
                    open_calibration_review=env["open_review"],
                    model_file=env["model_file"], tokenizer_file=env["tokenizer_file"],
                    code_revision=CODE)
        self.assertEqual(observed, [])
        self.assertFalse((Path(self.tmp.name)/"receipts").exists())

    def test_CR06_T13_frozen_expert_review_identity_cannot_change(self):
        env = self.env
        original = validate_real_freeze(
            env["freeze"], stand=env["stand"], model=env["model"],
            code_revision=CODE, attestation=env["attestation"],
            open_calibration_bytes=env["open_bytes"],
            open_calibration_review=env["open_review"],
            model_file=env["model_file"], tokenizer_file=env["tokenizer_file"])
        self.assertEqual(original, env["freeze"])
        forged = dict(env["open_review"])
        forged["reviewer_role"] = "changed after freeze"
        with self.assertRaises(BlindIntegrityError):
            validate_real_freeze(
                env["freeze"], stand=env["stand"], model=env["model"],
                code_revision=CODE, attestation=env["attestation"],
                open_calibration_bytes=env["open_bytes"],
                open_calibration_review=forged,
                model_file=env["model_file"], tokenizer_file=env["tokenizer_file"])

    def test_CR06_T14_reviewer_approval_and_full_case_review_required(self):
        env = self.env
        with self.assertRaises(BlindIntegrityError):
            self.validate(review={})
        forged = dict(env["open_review"])
        forged["reviewed_case_ids"] = forged["reviewed_case_ids"][:-1]
        with self.assertRaises(BlindIntegrityError):
            self.validate(review=forged)
        forged = dict(env["open_review"])
        forged["decision"] = "PENDING"
        with self.assertRaises(BlindIntegrityError):
            self.validate(review=forged)


if __name__ == "__main__":
    unittest.main()
