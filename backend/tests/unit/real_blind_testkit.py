"""Controlled synthetic source fixture and 40-case blind assurance test kit.

No output of this module is an independent blind experiment. Test gold is
synthetically authored in test code, never a real-source technical gold.
"""
from hashlib import sha256
from pathlib import Path
import json

from saturn_ai.evaluation.saturn_fixture import (
    fixture_snapshot, calibration_gold_bytes,
)
from saturn_ai.evaluation.saturn_answer_freeze import (
    EVALUATOR_REVISION, RUBRIC_REVISION, canonical_digest,
)
from saturn_ai.grounding.saturn_local_provider import (
    SaturnLocalModelConfig, LOCAL_PROVIDER_REVISION, _SYSTEM,
)
from saturn_ai.real_blind import (
    REAL_BLIND_REVISION, _THRESHOLDS, _model_config_details,
)
from saturn_ai.real_blind_assurance import source_question_key
from saturn_ai.real_corpus_stand import RealStand
from saturn_ai.retrieval.saturn_channel import build_saturn_retrieval_bundle


CODE = "f" * 40


def write_artifacts(directory):
    model_file = Path(directory) / "fake-model-only.bin"
    tokenizer_file = Path(directory) / "fake-tokenizer-only.json"
    model_file.write_bytes(b"synthetic testing bytes for a model, not weights")
    tokenizer_file.write_bytes(b"synthetic testing tokenizer bytes")
    return model_file, tokenizer_file


def prepare_controlled(directory):
    """Create independent-like synthetic contract data, never real evidence."""
    snap = fixture_snapshot()
    bundle = build_saturn_retrieval_bundle(snap)
    manifest = {
        "source_repository": "UkWood/Saturn-Main-Site",
        "source_commit": snap.manifest.site_manifest.commit_sha,
        "source_tree": snap.manifest.site_manifest.tree_sha,
        "synthetic_fixture_only": True,
    }
    stand = RealStand(snap, bundle, manifest)
    model_file, tokenizer_file = write_artifacts(directory)
    model_digest = sha256(model_file.read_bytes()).hexdigest()
    tokenizer_digest = sha256(tokenizer_file.read_bytes()).hexdigest()
    model = SaturnLocalModelConfig(
        "http://127.0.0.1:11434/v1/chat/completions",
        "synthetic-model-test-only", model_digest,
    )
    prompt_sha = sha256(_SYSTEM.encode("utf-8")).hexdigest()
    identity = {
        "model_name": model.model_id,
        "model_revision": "synthetic-fixture-revision",
        "model_artifact_sha256": model_digest,
        "quantization": "synthetic-test-only",
        "tokenizer_name": "synthetic-tokenizer",
        "tokenizer_revision": "synthetic-tokenizer-revision",
        "tokenizer_sha256": tokenizer_digest,
        "prompt_template_sha256": prompt_sha,
        "provider_adapter_revision": LOCAL_PROVIDER_REVISION,
        "generation_parameters": {
            "temperature": 0, "max_tokens": model.max_completion_tokens,
            "stream": False, "response_format": "json_object",
        },
        "context_window": 4096,
        "runtime_name": "synthetic-no-runtime",
        "runtime_version": "synthetic",
        "runtime_configuration_sha256": "b" * 64,
        "hardware_runtime_identity": "synthetic fixture only, no inference",
        "verification_level": "EXTERNALLY_VERIFIED",
    }
    attestation = {
        "reviewer": "Separate synthetic harness reviewer",
        "reviewer_role": "Test fixture author",
        "reviewed_at_utc": "2026-11-12T00:00:00Z",
        "model_identity_sha256": canonical_digest(identity),
        "model_bytes_sha256": model_digest,
        "tokenizer_bytes_sha256": tokenizer_digest,
        "prompt_bytes_sha256": prompt_sha,
        "verification_level": "EXTERNALLY_VERIFIED",
        "review_decision": "ACCEPTED",
        "verification_procedure":
            "SYNTHETIC UNIT TEST: compare exact local test-file SHA-256, "
            "declared fake tokenizer and prompt digest without contacting any model.",
        "runtime_attestation": False,
    }
    # SYNTHETIC source-backed unit fixture, transformed into the real_sample
    # contract so Stage 5E validates its real_sample pointers without altering
    # historical synthetic calibration artifacts. NEVER report as real data.
    open_payload = json.loads(calibration_gold_bytes(snap))
    open_payload["dataset_id"] = "controlled-open-source-review-v1"
    open_payload["author"] = "Test-source engineering drafter"
    open_payload["reviewer"] = "Separate test-source reviewer"
    open_payload["split"] = "real_sample"
    for case in open_payload["cases"]:
        case["split"] = "real_sample"
        case["tags"] = [case["category"]]
        # Stage 5E's historical C16 owner compatibility is specifically
        # keyed to the original dataset ID. New gold must state owner itself.
        if case["case_id"] == "C16":
            owners = [e.entity_id for e in snap.entities if e.title == "Device X"]
            assert len(owners) == 1
            case["required"][0]["owner_entity_id"] = owners[0]
    from saturn_ai.evaluation.saturn_answer_dataset import serialize_gold
    open_bytes = serialize_gold(open_payload)
    existing_questions = {
        source_question_key(c["question"])
        for c in open_payload["cases"]
    }
    # The fictional reviewer/attestation are only for isolated contract tests.
    # The real CLI requires independently signed-off source-based gold.
    open_review = {
        "schema_version": 1, "decision": "APPROVED_REAL_OPEN_CALIBRATION",
        "dataset_sha256": sha256(open_bytes).hexdigest(),
        "dataset_id": open_payload["dataset_id"],
        "snapshot_id": snap.snapshot_id,
        "corpus_hash": snap.manifest.corpus_hash,
        "source_manifest_sha256": canonical_digest(manifest),
        "case_count": len(open_payload["cases"]),
        "reviewed_case_ids": [case["case_id"] for case in open_payload["cases"]],
        "author": open_payload["author"], "reviewer": open_payload["reviewer"],
        "reviewer_role": "Independent fictional reviewer for a unit test",
        "reviewed_at_utc": "2026-11-12T00:00:00Z",
        "verification_procedure": (
            "UNIT TEST ONLY: checked synthetic source pointer identities "
            "against the in-memory test snapshot, no Saturn expert involved."
        ),
    }
    entities = {x.entity_id: x for x in snap.entities}
    pointer_by_fact = {
        p.canonical_id: p.evidence_id for p in snap.evidence_pointers
        if p.canonical_kind == "SiteFact"
    }
    facts = sorted(
        (f for f in snap.facts if f.fact_id in pointer_by_fact),
        key=lambda x: (entities[x.entity_id].title, x.field_path))
    assert len(facts) >= 24, "synthetic test fixture must offer 24 distinct fields"
    gold_cases = []
    for i, f in enumerate(facts[:24], 1):
        title = entities[f.entity_id].title
        question = f"{title}: {f.field_path}?"
        if source_question_key(question) in existing_questions:
            question = f"{title}: {f.field_path}? synthetic-run-{i}"
        gold_cases.append({
            "case_id": f"R{i:02d}", "question": question,
            "category": ("array" if "[" in f.field_path else
                         "nested" if "." in f.field_path else "field"),
            "split": "real_sample", "expected_status": "answered",
            "required": [{
                "requirement_id": "r1", "kind": "field",
                "canonical_id": f.fact_id, "source_revision_id": f.source_revision_id,
                "evidence_id": pointer_by_fact[f.fact_id],
            }],
            "negative_reason": None, "tags": ["controlled_synthetic_fixture"],
        })
    for i in range(16):
        gold_cases.append({
            "case_id": f"R{i+25:02d}",
            "question": f"Device X: synthetic_missing_field_{i}?",
            "category": "missing_field", "split": "real_sample",
            "expected_status": "needs_support",
            "required": [],
            "negative_reason":
                "This exact synthetic field is not declared in the source fixture.",
            "tags": ["controlled_synthetic_fixture"],
        })
    gold = {
        "schema_version": 1,
        "dataset_id": "synthetic-only-real-blind-contract-test",
        "snapshot_id": snap.snapshot_id,
        "corpus_hash": snap.manifest.corpus_hash,
        "split": "real_sample",
        "author": "Separate synthetic test author",
        "reviewer": "Different synthetic test reviewer",
        "cases": gold_cases,
    }
    blind_bytes = (json.dumps(
        gold, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ) + "\n").encode("utf-8")
    freeze = {
        "schema_version": 2,
        "profile_revision": REAL_BLIND_REVISION,
        "experiment_id": "SYNTHETIC_TEST_01",
        "code_revision": CODE,
        "dataset_sha256": sha256(blind_bytes).hexdigest(),
        "dataset_id": gold["dataset_id"],
        "dataset_author": gold["author"], "dataset_reviewer": gold["reviewer"],
        "expected_case_ids": [c["case_id"] for c in gold_cases],
        "expected_case_count": 40,
        "source_repository": manifest["source_repository"],
        "source_commit": manifest["source_commit"],
        "source_tree": manifest["source_tree"],
        "source_manifest_sha256": canonical_digest(manifest),
        "snapshot_id": snap.snapshot_id, "corpus_hash": snap.manifest.corpus_hash,
        "bundle_id": bundle.manifest.bundle_id,
        "mode": "lexical", "top_k": 10, "provider": "SaturnLocalClaimProvider",
        "provider_config": _model_config_details(model),
        "provider_config_sha256": canonical_digest(_model_config_details(model)),
        "model_weights_verification": "externally_verified_local_weights_sha256",
        "tokenizer_revision": identity["tokenizer_revision"],
        "prompt_revision": prompt_sha,
        "scorer_revision": EVALUATOR_REVISION,
        "rubric_revision": RUBRIC_REVISION,
        "thresholds": dict(_THRESHOLDS),
        "model_identity": identity,
        "model_identity_sha256": canonical_digest(identity),
        "independent_attestation_sha256": canonical_digest(attestation),
        "open_calibration_sha256": sha256(open_bytes).hexdigest(),
        "open_calibration_review_sha256": canonical_digest(open_review),
    }
    freeze["config_fingerprint"] = canonical_digest({
        "profile": REAL_BLIND_REVISION, "code_revision": CODE,
        "snapshot_id": snap.snapshot_id, "bundle_id": bundle.manifest.bundle_id,
        "provider_config_sha256": freeze["provider_config_sha256"],
        "tokenizer_revision": freeze["tokenizer_revision"],
        "prompt_revision": freeze["prompt_revision"],
        "scorer_revision": EVALUATOR_REVISION,
        "rubric_revision": RUBRIC_REVISION, "thresholds": _THRESHOLDS,
        "model_identity_sha256": freeze["model_identity_sha256"],
        "independent_attestation_sha256": freeze["independent_attestation_sha256"],
        "open_calibration_sha256": freeze["open_calibration_sha256"],
        "open_calibration_review_sha256": freeze["open_calibration_review_sha256"],
    })
    blind_path = Path(directory) / "synthetic-blind-gold.json"
    blind_path.write_bytes(blind_bytes)
    return {
        "stand": stand, "model": model, "freeze": freeze,
        "attestation": attestation, "open_bytes": open_bytes,
        "open_review": open_review,
        "blind_bytes": blind_bytes, "gold": gold, "blind_path": blind_path,
        "model_file": model_file, "tokenizer_file": tokenizer_file,
    }


def fake_empty_completion(config, payload):
    """No real model involved; all claims intentionally absent."""
    return json.dumps({
        "model": config.model_id,
        "choices": [{
            "finish_reason": "stop",
            "message": {"content": json.dumps({"claims": []})},
        }],
    }).encode("utf-8")
