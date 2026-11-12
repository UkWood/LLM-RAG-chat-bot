"""Stage 5H real-source blind: separate v0.1 freeze and durable one-shot run.

This module never manufactures blind questions/gold. Its input MUST be a
separately authored and reviewed dataset, supplied only after code/model/config
freeze. The original Stage 5E synthetic blind machinery is not modified.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import argparse
import json
import re
import sys

from .evaluation.saturn_answer_dataset import validate_gold, GoldValidationError
from .evaluation.saturn_answer_freeze import (
    BlindRun, BlindIntegrityError, RUBRIC_REVISION, EVALUATOR_REVISION,
    _write_once, _parse_report, _validate_result_case, canonical_digest,
)
from .evaluation.saturn_answer_reporting import (
    build_report, breakdown, calculate_metrics, report_bytes,
)
from .evaluation.saturn_answer_scoring import score_answer
from .evaluation.saturn_grounding import (
    SaturnEvaluationProfile, _run_question, _code_revision,
)
from .grounding.saturn_answer_assembly import SaturnAnswerAssemblyService
from .grounding.saturn_generation import SaturnClaimVerificationService
from .grounding.saturn_local_provider import (
    SaturnLocalClaimProvider, SaturnLocalModelConfig, LOCAL_PROVIDER_REVISION,
)
from .grounding.saturn_sufficiency_gate import SaturnQuestionGate
from .ingestion.github_snapshot_provider import GitHubSnapshotProvider
from .ingestion.saturn_contracts import canonical_json
from .real_corpus_stand import prepare_real_stand
from .retrieval.saturn_channel import SaturnRetrievalService
from .real_blind_assurance import (
    real_dataset_contract, threshold_scorecard, validate_model_identity,
    validate_independent_attestation, check_local_artifact_bytes,
    verify_completed_report,
)


REAL_BLIND_REVISION = "saturn-independent-real-blind/0.1.0"
REAL_BLIND_PROFILE = "real_source_blind_local_v0.1"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_THRESHOLDS = {
    "positive_fully_correct": [24, 24],
    "negative_fully_correct": [16, 16],
    "unsupported_claims": 0,
    "invalid_citations": 0,
    "false_positive_missing_facts": 0,
}


def _fail(code):
    raise BlindIntegrityError(code) from None


def _model_config_details(model: SaturnLocalModelConfig):
    return {
        "endpoint": model.endpoint, "model_id": model.model_id,
        "declared_model_sha256": model.declared_model_sha256,
        "provider_revision": LOCAL_PROVIDER_REVISION,
        "timeout_seconds": model.timeout_seconds,
        "max_completion_tokens": model.max_completion_tokens,
    }


def _identity(freeze, *, code_revision, snapshot, bundle, model):
    if not isinstance(freeze, dict):
        _fail("real_freeze_schema")
    if not isinstance(model, SaturnLocalModelConfig):
        _fail("local_model_missing")
    if not _SHA40.fullmatch(code_revision):
        _fail("code_revision_unavailable")
    expected = {
        "schema_version", "profile_revision", "experiment_id",
        "code_revision", "dataset_sha256", "dataset_id",
        "dataset_author", "dataset_reviewer", "expected_case_ids",
        "expected_case_count", "source_repository", "source_commit",
        "source_tree", "source_manifest_sha256", "snapshot_id", "corpus_hash",
        "bundle_id", "mode", "top_k", "provider",
        "provider_config", "provider_config_sha256", "model_weights_verification",
        "tokenizer_revision", "prompt_revision", "scorer_revision",
        "rubric_revision", "thresholds", "config_fingerprint",
        "model_identity", "model_identity_sha256",
        "independent_attestation_sha256", "open_calibration_sha256",
    }
    if set(freeze) != expected:
        _fail("real_freeze_schema")
    if (freeze["schema_version"] != 2 or
            freeze["profile_revision"] != REAL_BLIND_REVISION or
            freeze["provider"] != "SaturnLocalClaimProvider" or
            freeze["scorer_revision"] != EVALUATOR_REVISION or
            freeze["rubric_revision"] != RUBRIC_REVISION or
            freeze["mode"] != "lexical" or freeze["top_k"] != 10 or
            freeze["thresholds"] != _THRESHOLDS or
            freeze["code_revision"] != code_revision or
            freeze["snapshot_id"] != snapshot.snapshot_id or
            freeze["corpus_hash"] != snapshot.manifest.corpus_hash or
            freeze["bundle_id"] != bundle.manifest.bundle_id or
            freeze["provider_config"] != _model_config_details(model) or
            freeze["provider_config_sha256"] != canonical_digest(
                _model_config_details(model))):
        _fail("real_freeze_mismatch")
    if (freeze["model_identity_sha256"] !=
            validate_model_identity(freeze["model_identity"], model) or
            freeze["tokenizer_revision"] !=
            freeze["model_identity"]["tokenizer_revision"] or
            freeze["prompt_revision"] !=
            freeze["model_identity"]["prompt_template_sha256"] or
            not _SHA64.fullmatch(freeze["independent_attestation_sha256"]) or
            not _SHA64.fullmatch(freeze["open_calibration_sha256"])):
        _fail("real_freeze_model_identity")
    if (type(freeze["experiment_id"]) is not str
            or not 1 <= len(freeze["experiment_id"]) <= 100
            or any(not (c.isascii() and (c.isalnum() or c in "_-"))
                   for c in freeze["experiment_id"])
            or type(freeze["expected_case_count"]) is not int
            or freeze["expected_case_count"] != 40
            or type(freeze["expected_case_ids"]) is not list
            or len(freeze["expected_case_ids"]) != 40
            or len(set(freeze["expected_case_ids"])) != 40
            or any(type(x) is not str or not 1 <= len(x) <= 128
                   for x in freeze["expected_case_ids"])
            or type(freeze["dataset_id"]) is not str
            or not freeze["dataset_id"].strip()
            or any(type(freeze[k]) is not str or not freeze[k].strip()
                   for k in ("dataset_author", "dataset_reviewer",
                             "tokenizer_revision", "prompt_revision"))
            or freeze["dataset_author"] == freeze["dataset_reviewer"]
            or "Coding Session B" in freeze["dataset_author"]
            or "coding session b" in freeze["dataset_author"].lower()
            or not _SHA64.fullmatch(freeze["dataset_sha256"])
            or freeze["model_weights_verification"] !=
                "externally_verified_local_weights_sha256"):
        _fail("real_freeze_authorship_or_identity")
    if (freeze["source_repository"] != "UkWood/Saturn-Main-Site"
            or not _SHA40.fullmatch(freeze["source_commit"])
            or not _SHA40.fullmatch(freeze["source_tree"])
            or not _SHA64.fullmatch(freeze["source_manifest_sha256"])
            or not _SHA64.fullmatch(freeze["config_fingerprint"])):
        _fail("real_freeze_source_binding")
    computed = canonical_digest({
        "profile": REAL_BLIND_REVISION,
        "code_revision": code_revision,
        "snapshot_id": snapshot.snapshot_id,
        "bundle_id": bundle.manifest.bundle_id,
        "provider_config_sha256": freeze["provider_config_sha256"],
        "tokenizer_revision": freeze["tokenizer_revision"],
        "prompt_revision": freeze["prompt_revision"],
        "scorer_revision": EVALUATOR_REVISION,
        "rubric_revision": RUBRIC_REVISION,
        "thresholds": _THRESHOLDS,
        "model_identity_sha256": freeze["model_identity_sha256"],
        "independent_attestation_sha256": freeze["independent_attestation_sha256"],
        "open_calibration_sha256": freeze["open_calibration_sha256"],
    })
    if freeze["config_fingerprint"] != computed:
        _fail("real_freeze_config_fingerprint")
    return freeze


def validate_real_freeze(freeze, *, stand, model, code_revision=None,
                         attestation=None, open_calibration_bytes=None,
                         model_file=None, tokenizer_file=None):
    """Pre-START check: source, open calibration, independent attestation,
    and actual local artifact hashes; NEVER opens independent blind gold.
    """
    if code_revision is None:
        code_revision = _code_revision()
    _identity(freeze, code_revision=code_revision, snapshot=stand.snapshot,
              bundle=stand.bundle, model=model)
    manifest = stand.manifest
    if (freeze["source_repository"] != manifest["source_repository"] or
            freeze["source_commit"] != manifest["source_commit"] or
            freeze["source_tree"] != manifest["source_tree"] or
            freeze["source_manifest_sha256"] != canonical_digest(manifest)):
        _fail("real_freeze_manifest_mismatch")
    if (type(open_calibration_bytes) is not bytes or
            sha256(open_calibration_bytes).hexdigest() !=
            freeze["open_calibration_sha256"]):
        _fail("open_calibration_hash_mismatch")
    if (validate_independent_attestation(
            attestation, freeze["model_identity"],
            independent_author=freeze["dataset_author"]) !=
            freeze["independent_attestation_sha256"]):
        _fail("independent_attestation_hash_mismatch")
    if model_file is None or tokenizer_file is None:
        _fail("measured_local_artifacts_required")
    check_local_artifact_bytes(
        freeze["model_identity"], model_file=model_file,
        tokenizer_file=tokenizer_file)
    return freeze


def _validate_real_report(report, freeze, dataset):
    """Recompute every outcome and denominator from original gold, not summary."""
    report_keys = {
        "report_kind", "experiment_id", "schema_version", "profile",
        "runtime", "snapshot", "dataset", "configuration", "metrics",
        "breakdown", "cases", "failed_case_ids", "quality_target_met",
        "independent_blind_evaluation", "production_readiness",
        "threshold_scorecard",
    }
    if (type(report) is not dict or set(report) != report_keys or
            report["report_kind"] != "saturn_grounding_evaluation" or
            report["schema_version"] != 1 or
            report["experiment_id"] != freeze["experiment_id"] or
            report["profile"] != REAL_BLIND_PROFILE or
            report["independent_blind_evaluation"] != "RUN" or
            type(report["quality_target_met"]) is not bool or
            report["production_readiness"] is not False):
        _fail("real_report_schema")
    runtime = report["runtime"]
    snapshot = report["snapshot"]
    ds = report["dataset"]
    config = report["configuration"]
    if (type(runtime) is not dict or set(runtime) != {
                "provider", "mode", "top_k", "code_revision", "scorer_revision",
                "rubric_revision"} or
            type(snapshot) is not dict or
            set(snapshot) != {"snapshot_id", "corpus_hash", "bundle_id"} or
            type(ds) is not dict or set(ds) != {
                "id", "sha256", "schema_version", "case_count", "author", "reviewer"} or
            type(config) is not dict or set(config) != {"hash"} or
            runtime != {
                "provider": "SaturnLocalClaimProvider",
                "mode": "lexical", "top_k": 10,
                "code_revision": freeze["code_revision"],
                "scorer_revision": EVALUATOR_REVISION,
                "rubric_revision": RUBRIC_REVISION} or
            snapshot != {
                "snapshot_id": freeze["snapshot_id"],
                "corpus_hash": freeze["corpus_hash"],
                "bundle_id": freeze["bundle_id"]} or
            ds != {
                "id": dataset.dataset_id, "sha256": dataset.sha256,
                "schema_version": dataset.schema_version,
                "case_count": len(dataset.cases),
                "author": dataset.author, "reviewer": dataset.reviewer} or
            config != {"hash": freeze["config_fingerprint"]}):
        _fail("real_report_provenance")
    if (type(report["cases"]) is not list or
            len(report["cases"]) != freeze["expected_case_count"] or
            type(report["failed_case_ids"]) is not list):
        _fail("real_report_cases")
    gold = {x.case_id: x for x in dataset.cases}
    if (set(gold) != set(freeze["expected_case_ids"])
            or len(gold) != len(dataset.cases)
            or any(type(x) is not dict or type(x.get("case_id")) is not str
                   for x in report["cases"])
            or {x["case_id"] for x in report["cases"]} != set(gold)
            or len({x["case_id"] for x in report["cases"]}) != len(report["cases"])):
        _fail("real_report_case_identity")
    outcomes = tuple(_validate_result_case(x, gold[x["case_id"]])
                     for x in report["cases"])
    if (report["metrics"] != calculate_metrics(outcomes) or
            report["breakdown"] != breakdown(outcomes) or
            report["failed_case_ids"] != [x.case_id for x in outcomes
                                         if not x.fully_correct]):
        _fail("real_report_metrics")
    computed_scorecard = threshold_scorecard(
        outcomes, gold_cases=dataset.cases, thresholds=freeze["thresholds"])
    if (report["threshold_scorecard"] != computed_scorecard or
            report["quality_target_met"] !=
            computed_scorecard["quality_target_met"]):
        _fail("real_report_threshold_integrity")


class RealBlindRun(BlindRun):
    """Reuses original durable START / fail; versioned real-only completion."""

    def complete(self, report_data, *, dataset_bytes=None, snapshot=None,
                 open_calibration_bytes=None):
        if not self.started or not self.start_path.is_file():
            _fail("missing_start")
        if any(path.exists() for path in (
                self.report_path, self.failed_path, self.complete_path)):
            _fail("report_already_exists")
        if (type(dataset_bytes) is not bytes or snapshot is None or
                sha256(dataset_bytes).hexdigest() != self.freeze["dataset_sha256"] or
                snapshot.snapshot_id != self.freeze["snapshot_id"] or
                snapshot.manifest.corpus_hash != self.freeze["corpus_hash"]):
            _fail("real_dataset_binding")
        start = _parse_report(self.start_path.read_bytes())
        if (type(start) is not dict or set(start) != {
                "status", "experiment_id", "freeze_hash", "dataset_sha256",
                "code_revision", "snapshot_id"} or
                start != {
                    "status": "START",
                    "experiment_id": self.freeze["experiment_id"],
                    "freeze_hash": canonical_digest(self.freeze),
                    "dataset_sha256": self.freeze["dataset_sha256"],
                    "code_revision": self.freeze["code_revision"],
                    "snapshot_id": self.freeze["snapshot_id"]}):
            _fail("real_start_receipt_mismatch")
        try:
            dataset = validate_gold(dataset_bytes, snapshot, split="real_sample")
        except (GoldValidationError, ValueError, TypeError):
            _fail("real_gold_provenance")
        real_dataset_contract(
            dataset, open_calibration_bytes=open_calibration_bytes)
        if (dataset.dataset_id != self.freeze["dataset_id"]
                or dataset.author != self.freeze["dataset_author"]
                or dataset.reviewer != self.freeze["dataset_reviewer"]
                or [c.case_id for c in dataset.cases] !=
                   self.freeze["expected_case_ids"]):
            _fail("real_dataset_independence")
        report = _parse_report(report_data)
        _validate_real_report(report, self.freeze, dataset)
        try:
            _write_once(self.report_path, report)
        except FileExistsError:
            _fail("report_already_exists")
        persisted_sha = sha256(self.report_path.read_bytes()).hexdigest()
        _write_once(self.complete_path, {
            "status": "COMPLETE", "experiment_id": self.freeze["experiment_id"],
            "report_sha256": persisted_sha,
            "freeze_hash": canonical_digest(self.freeze),
        })
        verify_completed_report(
            report_path=self.report_path, complete_path=self.complete_path,
            expected_freeze_sha256=canonical_digest(self.freeze))


def run_real_blind(*, stand, model, freeze, dataset_path, report_path,
                   receipts_dir, attestation, open_calibration_bytes,
                   model_file, tokenizer_file, code_revision=None):
    """One-shot experiment: START first, dataset bytes/gold ONLY afterwards."""
    if code_revision is None:
        code_revision = _code_revision()
    validate_real_freeze(
        freeze, stand=stand, model=model, code_revision=code_revision,
        attestation=attestation, open_calibration_bytes=open_calibration_bytes,
        model_file=model_file, tokenizer_file=tokenizer_file)
    blind = RealBlindRun(
        freeze=freeze, receipts_dir=receipts_dir, report_path=report_path)
    blind.start()
    try:
        dataset_bytes = Path(dataset_path).read_bytes()  # AFTER durable START
        if sha256(dataset_bytes).hexdigest() != freeze["dataset_sha256"]:
            _fail("real_dataset_sha_mismatch")
        dataset = validate_gold(dataset_bytes, stand.snapshot, split="real_sample")
        real_dataset_contract(
            dataset, open_calibration_bytes=open_calibration_bytes)
        if (dataset.dataset_id != freeze["dataset_id"] or
                dataset.author != freeze["dataset_author"] or
                dataset.reviewer != freeze["dataset_reviewer"] or
                [case.case_id for case in dataset.cases] != freeze["expected_case_ids"] or
                len(dataset.cases) != 40 or
                sum(case.expected_status == "answered"
                    for case in dataset.cases) != 24):
            _fail("real_dataset_independence")
        provider = SaturnLocalClaimProvider(model)
        service = SaturnRetrievalService()
        service.publish(stand.bundle)
        verifier = SaturnClaimVerificationService(provider=provider)
        assembly = SaturnAnswerAssemblyService(verifier=verifier)
        gate = SaturnQuestionGate()
        profile = SaturnEvaluationProfile("real_sample")
        outcomes = []
        for case in dataset.cases:
            # Runtime gets only question. Never gold, labels or expected claims.
            answer, trace = _run_question(service, assembly, gate, verifier,
                                          case.question, profile)
            outcomes.append(score_answer(case, answer, stand.snapshot, trace))
        report = build_report(
            dataset, outcomes, code_revision=code_revision,
            config_hash=freeze["config_fingerprint"],
            bundle=stand.bundle, provider="SaturnLocalClaimProvider",
            mode="lexical", top_k=10, blind_status="RUN",
            evaluation_profile=REAL_BLIND_PROFILE,
            experiment_id=freeze["experiment_id"],
        )
        scorecard = threshold_scorecard(
            outcomes, gold_cases=dataset.cases, thresholds=freeze["thresholds"])
        report["threshold_scorecard"] = scorecard
        report["quality_target_met"] = scorecard["quality_target_met"]
        blind.complete(report_bytes(report), dataset_bytes=dataset_bytes,
                       snapshot=stand.snapshot,
                       open_calibration_bytes=open_calibration_bytes)
        return report
    except Exception as exc:
        blind.fail(exc.code if isinstance(exc, BlindIntegrityError)
                   else "real_blind_evaluation_failed")
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="One-shot independent real blind")
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--independent-gold", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--receipts-dir", type=Path, required=True)
    parser.add_argument("--allow-real-network", action="store_true")
    parser.add_argument("--allow-development-pdf-worker", action="store_true")
    parser.add_argument("--allow-local-inference", action="store_true")
    parser.add_argument("--local-endpoint", required=True)
    parser.add_argument("--local-model-id", required=True)
    parser.add_argument("--local-model-sha256", required=True)
    parser.add_argument("--independent-attestation", type=Path, required=True)
    parser.add_argument("--open-calibration-gold", type=Path, required=True)
    parser.add_argument("--model-artifact-file", type=Path, required=True)
    parser.add_argument("--tokenizer-artifact-file", type=Path, required=True)
    args = parser.parse_args(argv)
    if not all((args.allow_real_network, args.allow_development_pdf_worker,
                args.allow_local_inference)):
        parser.error("All experimental opt-in flags are mandatory")
    model = SaturnLocalModelConfig(
        args.local_endpoint, args.local_model_id, args.local_model_sha256)
    # Prepare and validate real evidence WITHOUT reading independent gold.
    stand = prepare_real_stand(
        provider=GitHubSnapshotProvider.from_env(),
        enable_development_pdf_worker=True)
    freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    report = run_real_blind(
        stand=stand, model=model, freeze=freeze,
        dataset_path=args.independent_gold,
        report_path=args.report, receipts_dir=args.receipts_dir,
        attestation=json.loads(args.independent_attestation.read_text(encoding="utf-8")),
        open_calibration_bytes=args.open_calibration_gold.read_bytes(),
        model_file=args.model_artifact_file,
        tokenizer_file=args.tokenizer_artifact_file,
    )
    print(canonical_json({
        "experiment_id": freeze["experiment_id"],
        "report_sha256": sha256(args.report.read_bytes()).hexdigest(),
        "independent_blind_evaluation": "RUN",
        "metrics": report["metrics"],
        "threshold_scorecard": report["threshold_scorecard"],
        "quality_target_met": report["quality_target_met"],
        "failed_case_ids": report["failed_case_ids"],
        "production_readiness": False,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
