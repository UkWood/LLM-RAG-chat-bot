"""Stage 5G open real-source calibration driver.

Uses the independent Stage 5E gold validation/scorer and the existing RAG
runtime, never a copied scorer. A dataset must be manually authored from the
actual source revisions; none is generated from LLM outputs. This is NOT blind.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from statistics import median
from time import perf_counter
import argparse
import json
import sys

from .evaluation.saturn_answer_dataset import validate_gold
from .evaluation.saturn_answer_reporting import build_report, report_bytes
from .evaluation.saturn_answer_scoring import score_answer
from .evaluation.saturn_grounding import (
    SaturnEvaluationProfile, _code_revision, _run_question,
)
from .grounding.saturn_answer_assembly import SaturnAnswerAssemblyService
from .grounding.saturn_claim_provider import SaturnFakeClaimProvider
from .grounding.saturn_generation import SaturnClaimVerificationService
from .grounding.saturn_local_provider import (
    LOCAL_PROVIDER_REVISION, SaturnLocalClaimProvider, SaturnLocalModelConfig,
)
from .grounding.saturn_sufficiency_gate import SaturnQuestionGate
from .ingestion.github_snapshot_provider import GitHubSnapshotProvider
from .ingestion.saturn_contracts import canonical_json
from .real_corpus_stand import prepare_real_stand
from .retrieval.saturn_channel import SaturnRetrievalService


def _percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    # Nearest-rank, declared for small pilot datasets.
    from math import ceil
    return ordered[max(0, ceil(p * len(ordered)) - 1)]


def evaluate_open_real_gold(dataset_bytes, stand, *, draft_provider,
                            code_revision=None):
    """Runtime sees each original question only, scorer receives pinned gold."""
    if type(draft_provider) not in (SaturnFakeClaimProvider, SaturnLocalClaimProvider):
        raise TypeError("unsupported_open_calibration_provider")
    dataset = validate_gold(dataset_bytes, stand.snapshot, split="real_sample")
    service = SaturnRetrievalService()
    service.publish(stand.bundle)
    verifier = SaturnClaimVerificationService(provider=draft_provider)
    assembly = SaturnAnswerAssemblyService(verifier=verifier)
    gate = SaturnQuestionGate()
    profile = SaturnEvaluationProfile("real_sample")
    outcomes = []
    elapsed_ms = []
    for case in dataset.cases:
        start = perf_counter()
        answer, trace = _run_question(
            service, assembly, gate, verifier, case.question, profile)
        elapsed_ms.append(round((perf_counter() - start) * 1000, 3))
        outcomes.append(score_answer(case, answer, stand.snapshot, trace))
    local = type(draft_provider) is SaturnLocalClaimProvider
    provider_details = {
        "provider_type": "local_llm" if local else "fake",
        "provider_class": type(draft_provider).__name__,
        "provider_revision": LOCAL_PROVIDER_REVISION if local else "stage5e-fake",
        "model_id": draft_provider.config.model_id if local else None,
        "declared_model_sha256": (
            draft_provider.config.declared_model_sha256 if local else None),
        "model_digest_server_verified": False if local else None,
    }
    config_sha = sha256(canonical_json({
        "profile": "real_open_calibration/0.1.0", "provider": provider_details,
        "mode": profile.mode, "top_k": profile.top_k,
        "snapshot_id": stand.snapshot.snapshot_id,
        "bundle_id": stand.bundle.manifest.bundle_id,
    }).encode("utf-8")).hexdigest()
    report = build_report(
        dataset, outcomes, code_revision=code_revision or _code_revision(),
        config_hash=config_sha, bundle=stand.bundle,
        provider=type(draft_provider).__name__,
        mode=profile.mode, top_k=profile.top_k,
        blind_status="NOT_RUN",
        evaluation_profile="real_open_calibration_local" if local
            else "real_open_calibration_fake",
    )
    model_latencies = draft_provider.latencies_ms if local else []
    report["real_source_profile_version"] = "real-open-calibration/0.1.0"
    report["source_repository"] = stand.manifest["source_repository"]
    report["source_commit"] = stand.manifest["source_commit"]
    report["source_tree"] = stand.manifest["source_tree"]
    report["source_manifest_sha256"] = sha256(
        canonical_json(stand.manifest).encode("utf-8")).hexdigest()
    report["provider_identity"] = provider_details
    report["performance"] = {
        "case_count": len(elapsed_ms),
        "end_to_end_ms_p50": _percentile(elapsed_ms, .5),
        "end_to_end_ms_p95": _percentile(elapsed_ms, .95),
        "model_inference_ms_p50": _percentile(model_latencies, .5),
        "model_inference_ms_p95": _percentile(model_latencies, .95),
        "successful_local_requests": (
            draft_provider.successful_requests if local else 0),
        "inference_status": (
            ("INVOKED" if draft_provider.successful_requests else "NOT_CONFIRMED")
            if local else "FAKE_ONLY"),
        "token_usage_last_request": draft_provider.last_usage if local else None,
        "percentile_method": "nearest-rank",
    }
    # A real-source open dataset is neither independently blind nor evidence
    # of model quality unless real local inference actually happened.
    report["quality_target_met"] = None
    report["independent_blind_evaluation"] = "NOT_RUN"
    report["production_readiness"] = False
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Opt-in OPEN real source calibration; NEVER independent blind")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--allow-real-network", action="store_true")
    parser.add_argument("--allow-development-pdf-worker", action="store_true")
    parser.add_argument("--provider", choices=("fake", "local_llm"), default="fake")
    parser.add_argument("--allow-local-inference", action="store_true")
    parser.add_argument("--local-endpoint")
    parser.add_argument("--local-model-id")
    parser.add_argument("--local-model-sha256")
    args = parser.parse_args(argv)
    if not args.allow_real_network or not args.allow_development_pdf_worker:
        parser.error("Source network and development PDF worker require explicit opt-in")
    if args.provider == "local_llm" and (
            not args.allow_local_inference or not args.local_endpoint
            or not args.local_model_id or not args.local_model_sha256):
        parser.error("Local inference must be explicitly configured and opted in")
    if args.provider == "fake":
        draft = SaturnFakeClaimProvider()
    else:
        draft = SaturnLocalClaimProvider(SaturnLocalModelConfig(
            args.local_endpoint, args.local_model_id, args.local_model_sha256))
    stand = prepare_real_stand(
        provider=GitHubSnapshotProvider.from_env(),
        enable_development_pdf_worker=True)
    # Dataset is never generated or modified; gold is loaded only for scoring.
    dataset_bytes = args.dataset.read_bytes()
    report = evaluate_open_real_gold(dataset_bytes, stand, draft_provider=draft)
    data = report_bytes(report)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("xb") as output:
        output.write(data)
    print(canonical_json({
        "profile": report["profile"],
        "dataset_sha256": sha256(dataset_bytes).hexdigest(),
        "source_commit": report["source_commit"],
        "code_revision": report["runtime"]["code_revision"],
        "metrics": report["metrics"],
        "performance": report["performance"],
        "independent_blind_evaluation": "NOT_RUN",
        "report_sha256": sha256(data).hexdigest(),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
