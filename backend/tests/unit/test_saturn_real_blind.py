"""Stage 5H freeze-only offline tests. No independent gold, no real blind.

The fixed source snapshot is a SYNTHETIC fixture and cannot be mistaken for
a real-site model result.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from saturn_ai.evaluation.saturn_answer_freeze import (
    BlindIntegrityError, canonical_digest,
)
from saturn_ai.evaluation.saturn_fixture import fixture_snapshot
from saturn_ai.grounding.saturn_local_provider import SaturnLocalModelConfig
from saturn_ai.real_blind import (
    REAL_BLIND_REVISION, RealBlindRun, validate_real_freeze,
    _THRESHOLDS, _model_config_details,
)
from saturn_ai.real_corpus_stand import RealStand
from saturn_ai.retrieval.saturn_channel import build_saturn_retrieval_bundle


CODE_SHA = "f" * 40
MODEL = SaturnLocalModelConfig(
    "http://127.0.0.1:11434/v1/chat/completions", "test-only",
    "a" * 64,
)


def fixture_freeze():
    snapshot = fixture_snapshot()
    bundle = build_saturn_retrieval_bundle(snapshot)
    manifest = {
        "source_repository": "UkWood/Saturn-Main-Site",
        "source_commit": snapshot.manifest.site_manifest.commit_sha,
        "source_tree": snapshot.manifest.site_manifest.tree_sha,
        "test_only": True,
    }
    stand = RealStand(snapshot, bundle, manifest)
    config = _model_config_details(MODEL)
    base = {
        "schema_version": 2, "profile_revision": REAL_BLIND_REVISION,
        "experiment_id": "TEST_ONLY_FROZEN_01",
        "code_revision": CODE_SHA,
        "dataset_sha256": "c" * 64,
        "dataset_id": "TEST_ONLY_NOT_REAL",
        "dataset_author": "Independent unit-test role",
        "dataset_reviewer": "Different unit-test role",
        "expected_case_ids": ["T" + str(i) for i in range(40)],
        "expected_case_count": 40,
        "source_repository": manifest["source_repository"],
        "source_commit": manifest["source_commit"],
        "source_tree": manifest["source_tree"],
        "source_manifest_sha256": canonical_digest(manifest),
        "snapshot_id": snapshot.snapshot_id,
        "corpus_hash": snapshot.manifest.corpus_hash,
        "bundle_id": bundle.manifest.bundle_id,
        "mode": "lexical", "top_k": 10,
        "provider": "SaturnLocalClaimProvider",
        "provider_config": config,
        "provider_config_sha256": canonical_digest(config),
        "model_weights_verification": "externally_verified_local_weights_sha256",
        "tokenizer_revision": "tokenizer-test-only",
        "prompt_revision": "prompt-test-only",
        "scorer_revision": "saturn-grounding-evaluator/0.1.2",
        "rubric_revision": "saturn-grounding-rubric/0.1.2",
        "thresholds": dict(_THRESHOLDS),
    }
    base["config_fingerprint"] = canonical_digest({
        "profile": REAL_BLIND_REVISION,
        "code_revision": CODE_SHA,
        "snapshot_id": snapshot.snapshot_id,
        "bundle_id": bundle.manifest.bundle_id,
        "provider_config_sha256": base["provider_config_sha256"],
        "tokenizer_revision": base["tokenizer_revision"],
        "prompt_revision": base["prompt_revision"],
        "scorer_revision": base["scorer_revision"],
        "rubric_revision": base["rubric_revision"],
        "thresholds": dict(_THRESHOLDS),
    })
    return stand, base


class IndependentRealFreezeContractTests(unittest.TestCase):
    def test_versioned_manifest_verifies_all_bindings(self):
        stand, freeze = fixture_freeze()
        self.assertEqual(validate_real_freeze(
            freeze, stand=stand, model=MODEL, code_revision=CODE_SHA), freeze)

    def test_mismatched_revision_or_model_prevents_start(self):
        stand, freeze = fixture_freeze()
        for field, value in (
            ("dataset_sha256", "invalid"),
            ("source_commit", "b" * 40),
            ("model_weights_verification", "unverified"),
            ("config_fingerprint", "0" * 64),
            ("expected_case_count", 39),
            ("dataset_author", "Coding Session B"),
        ):
            with self.subTest(field=field):
                altered = dict(freeze)
                altered[field] = value
                with self.assertRaises(BlindIntegrityError):
                    validate_real_freeze(
                        altered, stand=stand, model=MODEL, code_revision=CODE_SHA)
        with self.assertRaises(BlindIntegrityError):
            validate_real_freeze(
                freeze, stand=stand, model=MODEL, code_revision="a" * 40)

    def test_durable_start_is_non_repeatable_and_complete_requires_gold(self):
        stand, freeze = fixture_freeze()
        with TemporaryDirectory() as root:
            directory = Path(root)
            run = RealBlindRun(
                freeze=freeze, receipts_dir=directory / "receipts",
                report_path=directory / "report.json",
            )
            run.start()
            self.assertTrue(run.start_path.is_file())
            self.assertFalse(run.complete_path.exists())
            with self.assertRaises(BlindIntegrityError):
                RealBlindRun(
                    freeze=freeze, receipts_dir=directory / "receipts",
                    report_path=directory / "report.json").start()
            with self.assertRaises(BlindIntegrityError):
                run.complete(b"{}", dataset_bytes=b"not a real dataset",
                             snapshot=stand.snapshot)
            self.assertFalse(run.complete_path.exists())


if __name__ == "__main__":
    unittest.main()
