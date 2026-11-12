"""Real-blind assurance: fixed dataset composition, model evidence, scorecard.

Distinct from original Stage 5E scorer. It never changes the source-backed
claim/citation verdict and never claims a test fixture is a real blind result.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import re
from pathlib import Path

from .evaluation.saturn_answer_dataset import validate_gold
from .evaluation.saturn_answer_freeze import BlindIntegrityError, canonical_digest
from .grounding.saturn_local_provider import (
    SaturnLocalModelConfig, LOCAL_PROVIDER_REVISION, _SYSTEM,
)

PROFILE_VERSION = "saturn-real-assurance/0.1.0"
ALLOWED_CATEGORIES = {
    "field": "answered", "numeric": "answered", "array": "answered",
    "nested": "answered", "multi_need": "answered", "relation": "answered",
    "document_lookup": "answered",
    "missing_field": "needs_support", "missing_relation": "needs_support",
    "missing_document": "needs_support", "unknown_entity": "needs_support",
    "unanswerable": "needs_support", "pdf_quote_only": "needs_support",
    "ambiguity": "clarification", "conflict": "clarification",
    "unsupported_grammar": "clarification", "injection": "clarification",
    "unsupported_suffix": "clarification",
}
POSITIVE = frozenset({"answered"})
NEGATIVE = frozenset({"needs_support", "clarification"})
_MODEL_FIELDS = frozenset({
    "model_name", "model_revision", "model_artifact_sha256", "quantization",
    "tokenizer_name", "tokenizer_revision", "tokenizer_sha256",
    "prompt_template_sha256", "provider_adapter_revision",
    "generation_parameters", "context_window", "runtime_name",
    "runtime_version", "runtime_configuration_sha256",
    "hardware_runtime_identity", "verification_level",
})
_ATTESTATION_FIELDS = frozenset({
    "reviewer", "reviewer_role", "reviewed_at_utc",
    "model_identity_sha256", "model_bytes_sha256", "tokenizer_bytes_sha256",
    "prompt_bytes_sha256", "verification_level", "review_decision",
    "verification_procedure", "runtime_attestation",
})
_SHA64 = re.compile(r"^[0-9a-f]{64}$")


def refuse(code):
    raise BlindIntegrityError(code) from None


def _text(x, maximum=1024):
    return type(x) is str and 0 < len(x) <= maximum and bool(x.strip()) and "\x00" not in x


def _sha(x):
    return type(x) is str and bool(_SHA64.fullmatch(x))


def source_question_key(value):
    # Mechanical duplicate checking cannot prove semantic independence;
    # actual blind gold still requires independent technical review.
    return " ".join(value.casefold().split()).rstrip("?! .")


def real_dataset_contract(dataset, *, open_calibration_bytes: bytes):
    """Strict blind composition; never uses Stage 5B as a gold oracle."""
    if type(open_calibration_bytes) is not bytes or not open_calibration_bytes:
        refuse("open_calibration_required")
    if len(dataset.cases) != 40:
        refuse("real_blind_case_count")
    positive = sum(c.expected_status == "answered" for c in dataset.cases)
    negative = sum(c.expected_status in NEGATIVE for c in dataset.cases)
    if (positive != 24 or negative != 16 or
            positive + negative != len(dataset.cases)):
        refuse("real_blind_composition")
    if len({c.case_id for c in dataset.cases}) != 40:
        refuse("real_blind_duplicate_case")
    for case in dataset.cases:
        if (ALLOWED_CATEGORIES.get(case.category) != case.expected_status or
                (case.expected_status in NEGATIVE and
                 (not _text(case.negative_reason, 1200) or
                  len(case.negative_reason.strip()) < 15)) or
                (case.expected_status == "answered" and
                 (not case.required or case.negative_reason is not None)) or
                (case.expected_status == "needs_support" and
                 any(r.kind in ("field", "relation", "document")
                     for r in case.required)) or
                (case.category == "conflict" and len(case.required) < 2)):
            refuse("real_blind_category_or_gold")
    # Gold is already independently source-bound by Stage 5E validate_gold.
    # Also reject exact or whitespace/punctuation/case-equivalent open questions.
    from .evaluation.saturn_answer_dataset import GoldValidationError
    try:
        import json
        raw = json.loads(open_calibration_bytes.decode("utf-8"))
        if (type(raw) is not dict or type(raw.get("cases")) is not list or
                raw.get("split") not in ("real_sample", "synthetic_calibration")):
            refuse("invalid_open_dataset")
        open_questions = [row["question"] for row in raw["cases"]]
        if any(type(q) is not str for q in open_questions):
            refuse("invalid_open_dataset")
    except (UnicodeError, ValueError, TypeError, KeyError):
        refuse("invalid_open_dataset")
    overlap = {source_question_key(c.question) for c in dataset.cases} & {
        source_question_key(q) for q in open_questions}
    if overlap:
        refuse("blind_open_question_duplicate")
    if len({source_question_key(c.question) for c in dataset.cases}) != 40:
        refuse("blind_mechanical_duplicate")


def expected_generation_parameters(model):
    return {"temperature": 0, "max_tokens": model.max_completion_tokens,
            "stream": False, "response_format": "json_object"}


def validate_model_identity(identity, model: SaturnLocalModelConfig):
    """Source-visible fields and adapter prompt are checked; installed runtime
    facts (weights/tokenizer/hardware) require independent artifact evidence.
    """
    if type(identity) is not dict or set(identity) != _MODEL_FIELDS:
        refuse("model_identity_schema")
    if (identity["model_name"] != model.model_id or
            identity["model_artifact_sha256"] != model.declared_model_sha256 or
            identity["prompt_template_sha256"] != sha256(_SYSTEM.encode("utf-8")).hexdigest() or
            identity["provider_adapter_revision"] != LOCAL_PROVIDER_REVISION or
            identity["generation_parameters"] != expected_generation_parameters(model) or
            identity["verification_level"] != "EXTERNALLY_VERIFIED"):
        refuse("model_identity_mismatch")
    for field in ("model_revision", "quantization", "tokenizer_name",
                  "tokenizer_revision", "runtime_name", "runtime_version",
                  "hardware_runtime_identity"):
        if not _text(identity[field], 512):
            refuse("model_identity_incomplete")
    if not _sha(identity["tokenizer_sha256"]) or not _sha(
            identity["runtime_configuration_sha256"]):
        refuse("model_identity_incomplete")
    if type(identity["context_window"]) is not int or not 256 <= identity["context_window"] <= 262144:
        refuse("model_context_window_invalid")
    return canonical_digest(identity)


def validate_independent_attestation(attestation, identity, *,
                                     independent_author: str):
    """Externally reviewed document + measured file digests; NOT remote-runtime attestation."""
    if type(attestation) is not dict or set(attestation) != _ATTESTATION_FIELDS:
        refuse("independent_attestation_schema")
    if (attestation["verification_level"] != "EXTERNALLY_VERIFIED" or
            attestation["runtime_attestation"] is not False or
            attestation["review_decision"] != "ACCEPTED" or
            attestation["model_identity_sha256"] != canonical_digest(identity) or
            attestation["model_bytes_sha256"] != identity["model_artifact_sha256"] or
            attestation["tokenizer_bytes_sha256"] != identity["tokenizer_sha256"] or
            attestation["prompt_bytes_sha256"] != identity["prompt_template_sha256"]):
        refuse("independent_attestation_mismatch")
    if (not _text(attestation["reviewer"], 256)
            or not _text(attestation["reviewer_role"], 256)
            or not _text(attestation["reviewed_at_utc"], 64)
            or not _text(attestation["verification_procedure"], 2048)
            or len(attestation["verification_procedure"].strip()) < 40
            or attestation["reviewer"] == independent_author
            or "coding session b" in attestation["reviewer"].casefold()):
        refuse("independent_attestation_missing")
    return canonical_digest(attestation)


def sha256_file(path: Path) -> str:
    """Actual local artifact bytes, streamed; no trusted caller digest alone."""
    h = sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def check_local_artifact_bytes(identity, *, model_file: Path,
                               tokenizer_file: Path):
    if (sha256_file(model_file) != identity["model_artifact_sha256"] or
            sha256_file(tokenizer_file) != identity["tokenizer_sha256"]):
        refuse("model_artifact_bytes_mismatch")
    # Does not prove which weights the OpenAI-compatible server loaded.
    return "EXTERNALLY_VERIFIED"


def threshold_scorecard(outcomes, *, gold_cases, thresholds):
    """Independent deterministic threshold calculator; no changes to scorer.

    No observation is treated as a zero-error success. Return NOT_APPLICABLE
    with reason, and make aggregate quality NOT_MET whenever any gate is NA.
    """
    rows = tuple(outcomes)
    cases = tuple(gold_cases)
    if len(rows) != len(cases):
        refuse("scorecard_case_count")
    if {r.case_id for r in rows} != {c.case_id for c in cases}:
        refuse("scorecard_case_identity")
    positive = [x for x in rows if x.expected_status == "answered"]
    negative = [x for x in rows if x.expected_status in NEGATIVE]
    def entry(name, numerator, denominator, required, *, mode="eq",
              missing_reason="no_applicable_measurement"):
        if denominator == 0:
            status, actual, reason = "NOT_APPLICABLE", None, missing_reason
        else:
            actual = numerator
            status = "MET" if (actual == required if mode == "eq" else actual <= required) else "NOT_MET"
            reason = None
        return {
            "criterion": name, "numerator": numerator, "denominator": denominator,
            "required": required, "actual": actual,
            "result": status, "not_applicable_reason": reason,
        }
    expected_p = thresholds["positive_fully_correct"]
    expected_n = thresholds["negative_fully_correct"]
    technical = sum(x.technical_assertion_count for x in rows)
    citations = sum(x.citation_count for x in rows)
    source_refs = {c.case_id: c for c in cases if any(r.evidence_id for r in c.required)}
    document_refs = {c.case_id: c for c in cases if any(r.kind == "document" for r in c.required)}
    retrieval_unmeasured = sum(
        (row.case_id in source_refs and row.source_hit_at_5 is None) or
        (row.case_id in document_refs and row.document_hit_at_5 is None)
        for row in rows
    )
    retrieval_eligible = len(set(source_refs) | set(document_refs))
    criteria = {
        "positive_fully_correct": entry("positive_fully_correct",
             sum(x.fully_correct for x in positive), len(positive), expected_p[0]),
        "negative_fully_correct": entry("negative_fully_correct",
             sum(x.fully_correct for x in negative), len(negative), expected_n[0]),
        "unsupported_claims": entry("unsupported_claims",
             sum(x.source_unsupported_claim_count for x in rows),
             technical, thresholds["unsupported_claims"]),
        "invalid_citations": entry("invalid_citations",
             sum(x.citation_count - x.valid_citation_count for x in rows),
             citations, thresholds["invalid_citations"]),
        "false_positive_missing_facts": entry("false_positive_missing_facts",
             sum(x.actual_status in ("answered", "partial") or
                 x.answer_assertion_count > 0 for x in negative),
             len(negative), thresholds["false_positive_missing_facts"]),
        "required_retrieval_measured": entry("required_retrieval_measured",
             retrieval_eligible - retrieval_unmeasured, retrieval_eligible,
             retrieval_eligible),
    }
    overall_met = all(v["result"] == "MET" for v in criteria.values())
    return {"revision": PROFILE_VERSION, "criteria": criteria,
            "overall": "MET" if overall_met else "NOT_MET",
            "quality_target_met": overall_met}


def verify_completed_report(*, report_path: Path, complete_path: Path,
                            expected_freeze_sha256: str):
    """Post-run local readback against receipt; never trust caller report hash."""
    import json
    try:
        report = Path(report_path).read_bytes()
        receipt = json.loads(Path(complete_path).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        refuse("complete_receipt_unavailable")
    if (type(receipt) is not dict or set(receipt) != {
            "status", "experiment_id", "report_sha256", "freeze_hash"} or
            receipt["status"] != "COMPLETE" or
            receipt["freeze_hash"] != expected_freeze_sha256 or
            receipt["report_sha256"] != sha256(report).hexdigest()):
        refuse("persisted_report_integrity")
    return True
