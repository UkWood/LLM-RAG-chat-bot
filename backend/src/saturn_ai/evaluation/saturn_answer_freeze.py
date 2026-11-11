"""One-shot, fail-closed Saturn blind experiment freeze and durable receipts."""
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path

from ..ingestion.saturn_contracts import canonical_json

RUBRIC_REVISION = "saturn-grounding-rubric/0.1.1"
EVALUATOR_REVISION = "saturn-grounding-evaluator/0.1.1"


class BlindIntegrityError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__("Blind evaluation rejected: " + code)


def _refuse(code):
    raise BlindIntegrityError(code) from None


def canonical_digest(value):
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def config_hash(*, mode, top_k):
    return canonical_digest({
        "mode": mode, "top_k": top_k, "provider": "SaturnFakeClaimProvider",
        "evaluator_revision": EVALUATOR_REVISION, "rubric": RUBRIC_REVISION,
    })


def _exact_sha(value, size=40):
    return (type(value) is str and len(value) == size and
            all(c in "0123456789abcdef" for c in value))


def freeze_manifest(*, experiment_id, code_revision, dataset_sha256, snapshot,
                    case_count, case_ids=(), mode="lexical", top_k=10):
    if (type(experiment_id) is not str or
            not 1 <= len(experiment_id) <= 100 or
            not all(c.isascii() and (c.isalnum() or c in "-_")
                    for c in experiment_id) or
            not _exact_sha(code_revision) or
            not _exact_sha(dataset_sha256, 64) or
            type(case_count) is not int or not 1 <= case_count <= 300 or
            type(case_ids) not in (list, tuple) or
            len(case_ids) != case_count or
            any(type(x) is not str or not x or len(x) > 256
                for x in case_ids) or
            len(set(case_ids)) != case_count):
        _refuse("invalid_experiment")
    if (type(mode) is not str or mode != "lexical" or
            type(top_k) is not int or top_k != 10):
        _refuse("invalid_blind_config")
    from ..retrieval.saturn_channel import build_saturn_retrieval_bundle
    bundle_id = build_saturn_retrieval_bundle(snapshot).manifest.bundle_id
    return {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "code_revision": code_revision,
        "snapshot_id": snapshot.snapshot_id,
        "corpus_hash": snapshot.manifest.corpus_hash,
        "bundle_id": bundle_id,
        "dataset_sha256": dataset_sha256,
        "scorer_revision": EVALUATOR_REVISION,
        "rubric_revision": RUBRIC_REVISION,
        "provider": "SaturnFakeClaimProvider",
        "mode": mode, "top_k": top_k,
        "config_hash": config_hash(mode=mode, top_k=top_k),
        "expected_case_count": case_count,
        "expected_case_ids": list(case_ids),
        "split": "synthetic_blind",
    }


def validate_freeze(freeze, *, code_revision, dataset_bytes, snapshot,
                    mode, top_k):
    if not _exact_sha(code_revision):
        _refuse("exact_git_revision_unavailable")
    if type(dataset_bytes) is not bytes:
        _refuse("invalid_dataset_bytes")
    if type(freeze) is not dict:
        _refuse("invalid_freeze_schema")
    try:
        expected = freeze_manifest(
            experiment_id=freeze["experiment_id"],
            code_revision=code_revision,
            dataset_sha256=sha256(dataset_bytes).hexdigest(),
            snapshot=snapshot, case_count=freeze["expected_case_count"],
            case_ids=freeze["expected_case_ids"],
            mode=mode, top_k=top_k)
    except (TypeError, ValueError, KeyError, BlindIntegrityError):
        _refuse("invalid_freeze_schema")
    if set(freeze) != set(expected) or freeze != expected:
        _refuse("freeze_mismatch")
    return expected


def _unique_json(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            _refuse("duplicate_report_key")
        value[key] = item
    return value


def _parse_report(payload):
    if type(payload) is not bytes or not 0 < len(payload) <= 4_000_000:
        _refuse("invalid_report_bytes")
    try:
        return json.loads(payload.decode("utf-8"),
                          object_pairs_hook=_unique_json,
                          parse_constant=lambda _: _refuse("nonfinite_report"))
    except BlindIntegrityError:
        raise
    except (ValueError, UnicodeError, TypeError):
        _refuse("invalid_report_json")


def _validate_result_case(row, gold):
    from .saturn_answer_scoring import SaturnEvaluationOutcome
    from ..grounding.saturn_answer_contracts import ANSWER_STATUSES
    if type(row) is not dict or set(row) != set(SaturnEvaluationOutcome.__dataclass_fields__):
        _refuse("invalid_report_case_schema")
    try:
        out = SaturnEvaluationOutcome(**row)
    except (TypeError, ValueError):
        _refuse("invalid_report_case_schema")
    if (out.case_id != gold.case_id or
            out.category != gold.category or
            out.split != gold.split or
            out.expected_status != gold.expected_status or
            out.expected_status not in ANSWER_STATUSES or
            out.actual_status not in ANSWER_STATUSES or
            type(out.status_correct) is not bool or
            out.status_correct != (out.actual_status == out.expected_status) or
            type(out.fully_correct) is not bool or
            type(out.required_fact_count) is not int or
            out.required_fact_count != len(gold.required) or
            type(out.supported_fact_count) is not int or
            not 0 <= out.supported_fact_count <= out.required_fact_count or
            type(out.missing_requirement_count) is not int or
            out.missing_requirement_count != (out.required_fact_count -
                                             out.supported_fact_count) or
            type(out.technical_assertion_count) is not int or
            out.technical_assertion_count < 0 or
            type(out.unsupported_claim_count) is not int or
            type(out.source_unsupported_claim_count) is not int or
            out.unsupported_claim_count != out.source_unsupported_claim_count or
            not 0 <= out.unsupported_claim_count <= out.technical_assertion_count or
            type(out.off_question_claim_count) is not int or
            out.off_question_claim_count < 0 or
            type(out.extra_answer_text_count) is not int or
            out.extra_answer_text_count not in (0, 1) or
            type(out.citation_count) is not int or
            type(out.valid_citation_count) is not int or
            not 0 <= out.valid_citation_count <= out.citation_count or
            out.citation_valid not in (None, True, False) or
            out.citation_valid !=
            (out.valid_citation_count == out.citation_count
             if out.citation_count else None) or
            type(out.failure_codes) is not list or
            len(set(out.failure_codes)) != len(out.failure_codes) or
            not all(type(x) is str and 0 < len(x) <= 128 for x in out.failure_codes) or
            type(out.policy_restriction) is not bool or
            type(out.evidence_conflict) is not bool or
            out.policy_restriction != ("policy_restriction" in out.failure_codes) or
            out.evidence_conflict != ("evidence_conflict" in out.failure_codes) or
            out.fully_correct and (not out.status_correct or out.failure_codes or
                 out.missing_requirement_count or out.unsupported_claim_count or
                 out.off_question_claim_count or out.extra_answer_text_count or
                 out.actual_status == "error" or out.citation_valid is False) or
            type(out.answer_assertion_count) is not int or
            not 0 <= out.off_question_claim_count <= out.answer_assertion_count or
            out.answer_assertion_count < out.technical_assertion_count or
            out.evidence_recall_denominator != len({x.evidence_id for x in gold.required if x.evidence_id}) or
            type(out.evidence_recall_numerator) is not int or
            not 0 <= out.evidence_recall_numerator <= out.evidence_recall_denominator or
            (out.source_hit_at_5 is not None) != any(x.evidence_id for x in gold.required) or
            (out.document_hit_at_5 is not None) != any(x.kind == "document" for x in gold.required)):
        _refuse("inconsistent_report_case")
    return out


def _validate_report(report, freeze, dataset):
    from .saturn_answer_reporting import breakdown, calculate_metrics
    from .saturn_answer_scoring import SaturnEvaluationOutcome
    expected_keys = {
        "report_kind", "schema_version", "experiment_id", "profile",
        "runtime", "snapshot", "dataset", "configuration", "metrics",
        "breakdown", "cases", "failed_case_ids", "quality_target_met",
        "independent_blind_evaluation", "production_readiness",
    }
    if (type(report) is not dict or set(report) != expected_keys or
            report.get("report_kind") != "saturn_grounding_evaluation" or
            type(report.get("schema_version")) is not int or
            report["schema_version"] != 1 or
            report.get("experiment_id") != freeze["experiment_id"] or
            report.get("profile") != freeze["split"] or
            report.get("independent_blind_evaluation") != "RUN" or
            report.get("production_readiness") is not False or
            report.get("quality_target_met") is not None):
        _refuse("invalid_report_schema")
    runtime, snap, declared_data, config = (
        report.get("runtime"), report.get("snapshot"), report.get("dataset"),
        report.get("configuration"))
    if (type(runtime) is not dict or type(snap) is not dict or
            type(declared_data) is not dict or type(config) is not dict or
            set(runtime) != {"provider", "mode", "top_k", "code_revision",
                             "scorer_revision", "rubric_revision"} or
            set(snap) != {"snapshot_id", "corpus_hash", "bundle_id"} or
            set(declared_data) != {"id", "sha256", "schema_version",
                                   "case_count", "author", "reviewer"} or
            set(config) != {"hash"} or
            runtime.get("code_revision") != freeze["code_revision"] or
            runtime.get("provider") != freeze["provider"] or
            runtime.get("mode") != freeze["mode"] or
            runtime.get("top_k") != freeze["top_k"] or
            runtime.get("scorer_revision") != freeze["scorer_revision"] or
            runtime.get("rubric_revision") != freeze["rubric_revision"] or
            config.get("hash") != freeze["config_hash"] or
            snap.get("snapshot_id") != freeze["snapshot_id"] or
            snap.get("corpus_hash") != freeze["corpus_hash"] or
            snap.get("bundle_id") != freeze["bundle_id"] or
            declared_data.get("sha256") != freeze["dataset_sha256"] or
            declared_data.get("id") != dataset.dataset_id or
            declared_data.get("schema_version") != dataset.schema_version or
            declared_data.get("author") != dataset.author or
            declared_data.get("reviewer") != dataset.reviewer or
            declared_data.get("case_count") != freeze["expected_case_count"]):
        _refuse("report_provenance_mismatch")
    items = report.get("cases")
    if (type(items) is not list or len(items) != freeze["expected_case_count"] or
            type(report.get("failed_case_ids")) is not list):
        _refuse("report_case_count_mismatch")
    gold = {x.case_id: x for x in dataset.cases}
    if (len(gold) != len(dataset.cases) or
            set(gold) != set(freeze["expected_case_ids"]) or
            len({x.get("case_id") for x in items if type(x) is dict}) != len(items)):
        _refuse("report_case_identity_mismatch")
    if {x.get("case_id") for x in items if type(x) is dict} != set(gold):
        _refuse("report_case_identity_mismatch")
    outcomes = tuple(_validate_result_case(item, gold[item["case_id"]])
                     for item in items)
    if (report.get("failed_case_ids") !=
            [item.case_id for item in outcomes if not item.fully_correct] or
            report.get("metrics") != calculate_metrics(outcomes) or
            report.get("breakdown") != breakdown(outcomes)):
        _refuse("report_metric_inconsistency")



def _write_once(path: Path, data: dict):
    payload = (canonical_json(data) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        # Even a failed write is evidence of an attempted run; do not delete.
        raise
    return path


class BlindRun:
    """Created before parsing BLIND labels; never reuses a started experiment."""

    def __init__(self, *, freeze, receipts_dir, report_path):
        self.freeze = freeze
        self.dir = Path(receipts_dir)
        self.report_path = Path(report_path)
        self.run_id = sha256(freeze["experiment_id"].encode("utf-8")).hexdigest()
        self.start_path = self.dir / (self.run_id + ".START.json")
        self.failed_path = self.dir / (self.run_id + ".FAILED.json")
        self.complete_path = self.dir / (self.run_id + ".COMPLETE.json")
        self.started = False

    def start(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        if (self.report_path.exists() or self.complete_path.exists() or
                self.failed_path.exists() or self.start_path.exists()):
            _refuse("experiment_already_used")
        try:
            _write_once(self.start_path, {
                "status": "START", "experiment_id": self.freeze["experiment_id"],
                "freeze_hash": canonical_digest(self.freeze),
                "dataset_sha256": self.freeze["dataset_sha256"],
                "code_revision": self.freeze["code_revision"],
                "snapshot_id": self.freeze["snapshot_id"],
            })
        except FileExistsError:
            _refuse("experiment_already_used")
        self.started = True

    def complete(self, report_bytes, *, dataset=None):
        """Re-verify the entire report *at completion*, not only at CLI.

        Dataset is independently gold-validated AFTER the one-shot START;
        freeze binds its exact bytes and case IDs.
        """
        if not self.started or not self.start_path.is_file():
            _refuse("missing_start")
        if (self.report_path.exists() or self.complete_path.exists() or
                self.failed_path.exists()):
            _refuse("report_already_exists")
        if dataset is None or dataset.sha256 != self.freeze["dataset_sha256"]:
            _refuse("dataset_binding_missing")
        if (dataset.split != "synthetic_blind" or
                dataset.snapshot_id != self.freeze["snapshot_id"] or
                dataset.corpus_hash != self.freeze["corpus_hash"]):
            _refuse("dataset_provenance_mismatch")
        # START is durable identity evidence, not merely a Boolean flag.
        start = _parse_report(self.start_path.read_bytes())
        if (type(start) is not dict or set(start) != {
                "status", "experiment_id", "freeze_hash", "dataset_sha256",
                "code_revision", "snapshot_id"} or
                start.get("status") != "START" or
                start.get("experiment_id") != self.freeze["experiment_id"] or
                start.get("freeze_hash") != canonical_digest(self.freeze) or
                start.get("dataset_sha256") != dataset.sha256 or
                start.get("code_revision") != self.freeze["code_revision"] or
                start.get("snapshot_id") != self.freeze["snapshot_id"]):
            _refuse("start_receipt_integrity_mismatch")
        report = _parse_report(report_bytes)
        _validate_report(report, self.freeze, dataset)
        # Preserve original exclusive-create and durable receipt guarantees.
        try:
            _write_once(self.report_path, report)
        except FileExistsError:
            _refuse("report_already_exists")
        _write_once(self.complete_path, {
            "status": "COMPLETE", "experiment_id": self.freeze["experiment_id"],
            "report_sha256": sha256(report_bytes).hexdigest(),
            "freeze_hash": canonical_digest(self.freeze),
        })

    def fail(self, reason_code):
        if self.started:
            try:
                _write_once(self.failed_path, {
                    "status": "FAILED", "experiment_id": self.freeze["experiment_id"],
                    "reason_code": reason_code,
                    "freeze_hash": canonical_digest(self.freeze),
                })
            except FileExistsError:
                pass
