"""Bounded, deterministic, privacy-preserving Stage 5E reports and metrics."""
from collections import defaultdict
from dataclasses import asdict
import json

from ..ingestion.saturn_contracts import canonical_json


def _rate(num, den):
    return None if not den else num / den


def _metric(num, den):
    return {"numerator": num, "denominator": den, "rate": _rate(num, den)}


def calculate_metrics(outcomes):
    items = tuple(outcomes)
    positive = [x for x in items if x.expected_status == "answered"]
    support = [x for x in items if x.expected_status == "needs_support"]
    clarification = [x for x in items if x.expected_status == "clarification"]
    negatives = support + clarification
    cited = [x for x in items if x.citation_valid is not None]
    source = [x for x in items if x.source_hit_at_5 is not None]
    document = [x for x in items if x.document_hit_at_5 is not None]
    fail = [x for x in positive if x.actual_status in
            ("needs_support", "clarification", "partial")]
    issued_assertions = sum(x.technical_assertion_count for x in items)
    unsupported = sum(x.unsupported_claim_count for x in items)
    return {
        "case_count": len(items),
        "positive_complete_answer": _metric(
            sum(x.fully_correct for x in positive), len(positive)),
        "negative_correctness": _metric(
            sum(x.fully_correct for x in negatives), len(negatives)),
        "needs_support_correctness": _metric(
            sum(x.fully_correct for x in support), len(support)),
        "clarification_correctness": _metric(
            sum(x.fully_correct for x in clarification), len(clarification)),
        "status_accuracy": _metric(sum(x.status_correct for x in items), len(items)),
        "requirement_recall": _metric(
            sum(x.supported_fact_count for x in items),
            sum(x.required_fact_count for x in items)),
        "unsupported_claims": {
            "count": unsupported,
            "ratio": _metric(unsupported, issued_assertions),
        },
        "citation_validity": _metric(
            sum(x.valid_citation_count for x in items),
            sum(x.citation_count for x in items)),
        "citation_applicable_cases": len(cited),
        "citation_not_applicable_cases": len(items) - len(cited),
        "false_refusal": _metric(len(fail), len(positive)),
        "false_refusal_by_status": {
            name: sum(x.actual_status == name for x in fail)
            for name in ("needs_support", "clarification", "partial")
        },
        "technical_error": _metric(
            sum(x.actual_status == "error" or
                "technical_failure" in x.failure_codes for x in items), len(items)),
        "source_hit_at_5": _metric(
            sum(x.source_hit_at_5 is True for x in source), len(source)),
        "document_hit_at_5": _metric(
            sum(x.document_hit_at_5 is True for x in document), len(document)),
        "evidence_recall": _metric(
            sum(x.evidence_recall_numerator for x in items),
            sum(x.evidence_recall_denominator for x in items)),
        "fully_correct_all": _metric(sum(x.fully_correct for x in items), len(items)),
    }


def breakdown(outcomes):
    """Never pool different profiles. Every slice states its own denominators."""
    groups = defaultdict(list)
    for x in outcomes:
        keys = (
            ("profile", x.split),
            ("category", x.category),
            ("status_group", "positive" if x.expected_status == "answered"
             else "negative_or_ambiguous"),
            ("requirement_count", str(x.required_fact_count)),
        )
        for axis, value in keys:
            groups[(axis, value)].append(x)
    return {axis: {
        value: calculate_metrics(items)
        for (a, value), items in sorted(groups.items()) if a == axis
    } for axis in ("profile", "category", "status_group", "requirement_count")}


def build_report(dataset, outcomes, *, code_revision, config_hash, bundle,
                 provider="SaturnFakeClaimProvider", mode="lexical", top_k=10,
                 blind_status="NOT_RUN", evaluation_profile=None):
    outcomes = tuple(outcomes)
    if len(outcomes) != len(dataset.cases) or len({x.case_id for x in outcomes}) != len(outcomes):
        raise ValueError("Evaluation outcome coverage mismatch")
    if any(x.split != dataset.split for x in outcomes):
        raise ValueError("Mixed evaluation profiles")
    if {x.case_id for x in outcomes} != {x.case_id for x in dataset.cases}:
        raise ValueError("Missing evaluation case")
    report = {
        "report_kind": "saturn_grounding_evaluation",
        "schema_version": 1,
        "profile": evaluation_profile or dataset.split,
        "runtime": {
            "provider": provider, "mode": mode, "top_k": top_k,
            "code_revision": code_revision,
        },
        "snapshot": {
            "snapshot_id": dataset.snapshot_id,
            "corpus_hash": dataset.corpus_hash,
            "bundle_id": bundle.manifest.bundle_id,
        },
        "dataset": {
            "id": dataset.dataset_id, "sha256": dataset.sha256,
            "schema_version": dataset.schema_version, "case_count": len(dataset.cases),
            "author": dataset.author, "reviewer": dataset.reviewer,
        },
        "configuration": {"hash": config_hash},
        "metrics": calculate_metrics(outcomes),
        "breakdown": breakdown(outcomes),
        "cases": [asdict(x) for x in outcomes],
        "failed_case_ids": [x.case_id for x in outcomes if not x.fully_correct],
        # Synthetic score cannot be turned into independent product acceptance.
        "quality_target_met": None if dataset.split != "synthetic_blind"
                              else all(x.fully_correct for x in outcomes),
        "independent_blind_evaluation": blind_status,
        "production_readiness": False,
    }
    return report


def report_bytes(report):
    return (canonical_json(report) + "\n").encode("utf-8")
