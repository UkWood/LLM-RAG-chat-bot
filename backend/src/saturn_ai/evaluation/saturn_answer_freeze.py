"""One-shot, fail-closed Saturn blind experiment freeze and durable receipts."""
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path

from ..ingestion.saturn_contracts import canonical_json

RUBRIC_REVISION = "saturn-grounding-rubric/0.1.0"
EVALUATOR_REVISION = "saturn-grounding-evaluator/0.1.0"


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


def freeze_manifest(*, experiment_id, code_revision, dataset_sha256, snapshot,
                    case_count, mode="lexical", top_k=10):
    if (not isinstance(experiment_id, str) or
            not 1 <= len(experiment_id) <= 100 or
            not all(c.isalnum() or c in "-_" for c in experiment_id) or
            type(case_count) is not int or not 1 <= case_count <= 300):
        _refuse("invalid_experiment")
    return {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "code_revision": code_revision,
        "snapshot_id": snapshot.snapshot_id,
        "corpus_hash": snapshot.manifest.corpus_hash,
        "dataset_sha256": dataset_sha256,
        "scorer_revision": EVALUATOR_REVISION,
        "rubric_revision": RUBRIC_REVISION,
        "provider": "SaturnFakeClaimProvider",
        "mode": mode, "top_k": top_k,
        "config_hash": config_hash(mode=mode, top_k=top_k),
        "expected_case_count": case_count,
        "split": "synthetic_blind",
    }


def validate_freeze(freeze, *, code_revision, dataset_bytes, snapshot,
                    mode, top_k):
    expected_keys = set(freeze_manifest(
        experiment_id="dummy", code_revision=code_revision,
        dataset_sha256=sha256(dataset_bytes).hexdigest(), snapshot=snapshot,
        case_count=1, mode=mode, top_k=top_k))
    if type(freeze) is not dict or set(freeze) != expected_keys:
        _refuse("invalid_freeze_schema")
    try:
        expected = freeze_manifest(
            experiment_id=freeze["experiment_id"],
            code_revision=code_revision,
            dataset_sha256=sha256(dataset_bytes).hexdigest(),
            snapshot=snapshot, case_count=freeze["expected_case_count"],
            mode=mode, top_k=top_k)
    except (TypeError, ValueError):
        _refuse("invalid_freeze_schema")
    if freeze != expected:
        _refuse("freeze_mismatch")
    return expected


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

    def complete(self, report_bytes):
        if not self.started:
            _refuse("missing_start")
        if self.report_path.exists():
            _refuse("report_already_exists")
        _write_once(self.report_path, json.loads(report_bytes.decode("utf-8")))
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
