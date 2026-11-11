"""Bounded, deterministic, privacy-preserving Stage 5E reports and metrics."""
from collections import defaultdict
from dataclasses import asdict
import json

from ..ingestion.saturn_contracts import canonical_json
from .saturn_answer_freeze import EVALUATOR_REVISION, RUBRIC_REVISION


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
    source_applicable = [x for x in items
                         if x.evidence_recall_denominator > 0 or
                         x.source_hit_at_5 is not None]
    # Cases with required source evidence but unavailable retrieval have
    # numerator/denominator 0 at the case level; distinguish them by the
    # original authored requirements using the source channel and the
    # already-recorded required_fact_count, never treat them as false hits.
    source_unmeasured = [x for x in items if
                         x.source_hit_at_5 is None and
                         x.source_channel in ("site", "pdf", "mixed") and
                         x.required_fact_count > 0]
    doc_unmeasured = [x for x in items if
                      x.document_hit_at_5 is None and
                      x.source_channel in ("document_metadata", "mixed") and
                      x.required_fact_count > 0]
    quote_eligible = sum(x.quote_requirement_count for x in items)
    quote_verified = sum(x.verified_quote_count for x in items)
    fail = [x for x in positive if x.actual_status in
            ("needs_support", "clarification", "partial")]
    issued_assertions = sum(x.technical_assertion_count for x in items)
    unsupported = sum(x.source_unsupported_claim_count for x in items)
    off_question = sum(x.off_question_claim_count for x in items)
    extra_text = sum(x.extra_answer_text_count for x in items)
    answer_assertions = sum(x.answer_assertion_count for x in items)
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
            "count": unsupported, "ratio": _metric(unsupported, issued_assertions),
        },
        "source_unsupported_claims": {
            "count": unsupported, "ratio": _metric(unsupported, issued_assertions),
        },
        "off_question_source_backed_claims": {
            "count": off_question, "ratio": _metric(off_question, answer_assertions),
        },
        "extra_unsupported_answer_text": {
            "count": extra_text, "case_rate": _metric(extra_text, len(items)),
        },
        "policy_restriction": _metric(
            sum(x.policy_restriction for x in items), len(items)),
        "evidence_conflict": _metric(
            sum(x.evidence_conflict for x in items), len(items)),

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
        "source_hit_at_5_not_measured_cases": len(source_unmeasured),
        "document_hit_at_5_not_measured_cases": len(doc_unmeasured),
        "source_hit_at_5_measured_cases": len(source),
        "document_hit_at_5_measured_cases": len(document),
        "extractive_quote_integrity": _metric(quote_verified, quote_eligible),
        "engineering_requirement_recall": _metric(
            sum(x.supported_fact_count - x.verified_quote_count for x in items),
            sum(x.required_fact_count - x.quote_requirement_count for x in items)),
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
            ("source_channel", x.source_channel),
            ("category", x.category),
            ("status_group", {"answered": "positive",
                              "partial": "partial",
                              "clarification": "clarification",
                              "needs_support": "negative",
                              "error": "technical"}.get(
                                  x.expected_status, "unknown")),
            ("requirement_count", str(x.required_fact_count)),
        )
        for axis, value in keys:
            groups[(axis, value)].append(x)
    return {axis: {
        value: calculate_metrics(items)
        for (a, value), items in sorted(groups.items()) if a == axis
    } for axis in ("profile", "source_channel", "category", "status_group", "requirement_count")}


def build_report(dataset, outcomes, *, code_revision, config_hash, bundle,
                 provider="SaturnFakeClaimProvider", mode="lexical", top_k=10,
                 blind_status="NOT_RUN", evaluation_profile=None,
                 experiment_id=None):
    outcomes = tuple(outcomes)
    if len(outcomes) != len(dataset.cases) or len({x.case_id for x in outcomes}) != len(outcomes):
        raise ValueError("Evaluation outcome coverage mismatch")
    if any(x.split != dataset.split for x in outcomes):
        raise ValueError("Mixed evaluation profiles")
    if {x.case_id for x in outcomes} != {x.case_id for x in dataset.cases}:
        raise ValueError("Missing evaluation case")
    report = {
        "report_kind": "saturn_grounding_evaluation",
        "experiment_id": experiment_id,
        "schema_version": 1,
        "profile": evaluation_profile or dataset.split,
        "runtime": {
            "provider": provider, "mode": mode, "top_k": top_k,
            "code_revision": code_revision,
            "scorer_revision": EVALUATOR_REVISION,
            "rubric_revision": RUBRIC_REVISION,
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
        # Product thresholds and independent authorship require Session A approval.
        # An unreviewed/short dataset cannot pass merely because every case passes.
        "quality_target_met": None,
        "independent_blind_evaluation": blind_status,
        "production_readiness": False,
    }
    return report


def report_bytes(report):
    return (canonical_json(report) + "\n").encode("utf-8")
