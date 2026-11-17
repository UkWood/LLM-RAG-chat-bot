"""Explicit research CLI and owner-only append-only Stage 5K Markdown/JSON journal.

Separate from Stage 5J answer.md and production RAG. Offline mode validates
the fixed research contract WITHOUT claiming source search or local Qwen calls.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import sys
from time import perf_counter
import uuid

from .feedback_journal import _outside_all_git_worktrees, _private_entry, _raw_path_checked
from .stage5k_contract import (
    D_PREREQUISITE_REVISION, DATASET_SHA256, ENDPOINT, ExperimentError, MODEL_ID,
    MODEL_SHA256, design_freeze, load_seeds, canonical, sha_text,
)
from .stage5k_comparator import (
    D_NOT_RUN, NOT_MEASURED, EphemeralDIndex, LocalIntentPlanner,
    ResearchComparator, verify_stand,
)

BRANCH_SCOPE = "Stage5K-A-R"


class ResearchJournal:
    """One new immutable run; strict local permissions and no overwrite."""

    def __init__(self, root: Path):
        if sys.platform != "linux" or not hasattr(os, "O_NOFOLLOW"):
            raise ExperimentError("secure_linux_fs_required")
        path = Path(root).expanduser()
        _raw_path_checked(path)
        _outside_all_git_worktrees(path)
        if path.exists():
            _private_entry(path, require_directory=True)
        else:
            try:
                path.mkdir(mode=0o700, parents=True, exist_ok=False)
            except OSError:
                raise ExperimentError("journal_root_unavailable") from None
        _private_entry(path, require_directory=True)
        self.root = path
        self.run_id = uuid.uuid4().hex
        self.run_root = self.root / ("run-" + self.run_id)
        self._make_dir(self.run_root)

    def _make_dir(self, path: Path):
        if not path.is_relative_to(self.root):
            raise ExperimentError("journal_path_escape")
        current = self.root
        for part in path.relative_to(self.root).parts:
            current = current / part
            if current.is_symlink():
                raise ExperimentError("journal_symlink_forbidden")
            if current.exists():
                _private_entry(current, require_directory=True)
            else:
                try:
                    current.mkdir(mode=0o700)
                except OSError:
                    raise ExperimentError("journal_dir_unavailable") from None
                _private_entry(current, require_directory=True)

    def write(self, relative: str, raw: bytes) -> None:
        if len(raw) > 2_000_000 or not relative or not re.fullmatch(
                r"[A-Za-z0-9_/.-]{1,180}", relative):
            raise ExperimentError("journal_record_size_or_path")
        path = self.run_root / relative
        if not path.is_relative_to(self.run_root) or ".." in Path(relative).parts:
            raise ExperimentError("journal_path_escape")
        self._make_dir(path.parent)
        if path.is_symlink() or path.exists():
            raise ExperimentError("journal_record_exists")
        temp = path.with_name("." + uuid.uuid4().hex + ".tmp")
        try:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                if stat.S_IMODE(os.fstat(fd).st_mode) != 0o600:
                    raise ExperimentError("journal_fs_mode_unsupported")
                with os.fdopen(fd, "wb") as handle:
                    fd = -1
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.link(temp, path, follow_symlinks=False)
                folder = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    os.fsync(folder)
                finally:
                    os.close(folder)
            finally:
                if fd >= 0:
                    os.close(fd)
        except OSError:
            raise ExperimentError("journal_write_failed") from None
        finally:
            temp.unlink(missing_ok=True)

    @staticmethod
    def _render_markdown(value: dict) -> bytes:
        # Render deterministic sidecar. Tilde fence cannot be ended by data.
        body = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
        max_run = max((len(m.group()) for m in re.finditer(r"~+", body)),
                      default=0)
        fence = "~" * max(4, max_run + 1)
        return ("# Stage 5K research observation\n\n" + fence + "json\n"
                + body + "\n" + fence + "\n").encode("utf-8")

    def record(self, name: str, value: dict, *, markdown: bool = True) -> None:
        # Sidecar first, canonical JSON LAST as an atomic per-arm commit marker.
        # A crash between them remains detectably INCOMPLETE on restart.
        raw = (canonical(value) + "\n").encode("utf-8")
        if markdown:
            self.write(name + ".md", self._render_markdown(value))
        self.write(name + ".json", raw)

    @classmethod
    def inspect_run(cls, root: Path, run_id: str) -> dict:
        """Read-only restart reconstruction. NEVER resumes/retries inference."""
        if not re.fullmatch(r"[0-9a-f]{32}", run_id):
            raise ExperimentError("invalid_run_id")
        path = Path(root).expanduser()
        _raw_path_checked(path)
        _outside_all_git_worktrees(path)
        _private_entry(path, require_directory=True)
        run_root = path / ("run-" + run_id)
        _private_entry(run_root, require_directory=True)

        def read_record(prefix):
            j = run_root / (prefix + ".json")
            m = run_root / (prefix + ".md")
            if not j.exists() and not m.exists():
                return None, "missing"
            if not j.exists() or not m.exists():
                return None, "partial"
            for folder in (j.parent,):
                _private_entry(folder, require_directory=True)
            _private_entry(j, require_directory=False)
            _private_entry(m, require_directory=False)
            try:
                from .stage5k_contract import strict_json
                obj = strict_json(j.read_bytes(), maximum=2_000_000)
                if type(obj) is not dict or m.read_bytes() != cls._render_markdown(obj):
                    return None, "corrupt"
                return obj, "committed"
            except (OSError, ValueError, ExperimentError, UnicodeError):
                return None, "corrupt"

        run, run_state = read_record("run")
        if (run_state != "committed" or run.get("run_id") != run_id or
                run.get("dataset_sha256") != DATASET_SHA256 or
                run.get("status") != "INCOMPLETE"):
            raise ExperimentError("journal_run_manifest_invalid")
        pairs = run.get("expected_pairs")
        if type(pairs) is not list or not 1 <= len(pairs) <= 240:
            raise ExperimentError("journal_expected_pairs_invalid")
        expected = {}
        for item in pairs:
            if (type(item) is not dict or set(item) != {
                    "case_id", "variant", "question_sha256"} or
                    not re.fullmatch(r"KQ[0-9]{2}", str(item["case_id"])) or
                    item["variant"] not in ("A", "B", "C", "D") or
                    not re.fullmatch(r"[0-9a-f]{64}", str(item["question_sha256"]))):
                raise ExperimentError("journal_expected_pairs_invalid")
            key = (item["case_id"], item["variant"])
            if key in expected:
                raise ExperimentError("journal_duplicate_expected_pair")
            expected[key] = item["question_sha256"]
        completed, partial, missing, corrupt = [], [], [], []
        for (case_id, variant), digest in expected.items():
            record, state = read_record("cases/" + case_id + "/" + variant)
            key = {"case_id": case_id, "variant": variant}
            if state == "missing":
                missing.append(key)
            elif state == "partial":
                partial.append(key)
            elif state != "committed" or (
                    record.get("case_id") != case_id or
                    record.get("variant") != variant or
                    record.get("question_sha256") != digest or
                    type(record.get("question")) is not str or
                    sha_text(record["question"]) != digest):
                corrupt.append(key)
            else:
                completed.append(key)

        existing = {
            (p.parent.name, p.stem)
            for ext in ("*.json", "*.md")
            for p in (run_root / "cases").glob("*/" + ext)
        }
        unexpected = [
            {"case_id": key[0], "variant": key[1]}
            for key in sorted(existing - set(expected))
        ]
        summary, summary_state = read_record("summary")
        whole = not (missing or partial or corrupt or unexpected)
        correct_summary = (
            summary_state == "committed" and
            summary.get("status") == "COMPLETE" and
            summary.get("run_id") == run_id and
            summary.get("dataset_sha256") == DATASET_SHA256 and
            summary.get("expected_case_arm_count") == len(expected) and
            summary.get("completed_case_arm_count") == len(expected)
        )
        return {
            "run_id": run_id,
            "status": ("COMPLETE" if whole and correct_summary
                       else "INCOMPLETE"),
            "expected_case_arm_count": len(expected),
            "completed_case_arm_count": len(completed),
            "missing_pairs": missing, "partial_pairs": partial,
            "corrupt_pairs": corrupt, "unexpected_pairs": unexpected,
            "summary_state": summary_state,
            "reason": ("all_pairs_and_summary_verified" if whole and correct_summary
                       else "incomplete_or_unverified_records"),
            "automatic_resume": False,
        }


def _read_license(path: Path | None):
    if path is None:
        return None
    try:
        raw = path.read_bytes()
    except OSError:
        raise ExperimentError("d_review_file_unavailable") from None
    if len(raw) > 16000:
        raise ExperimentError("d_review_too_large")
    from .stage5k_contract import strict_json
    return strict_json(raw, maximum=16000)


def _d_review_is_approved(review) -> bool:
    keys = {"approval_status", "reviewer", "license", "source_url",
            "model_sha256", "tokenizer_sha256"}
    if type(review) is not dict or set(review) != keys:
        return False
    if review.get("approval_status") != "APPROVED":
        return False
    if any(type(review.get(k)) is not str or not review[k].strip()
           or len(review[k]) > 1000
           for k in ("reviewer", "license", "source_url")):
        return False
    from urllib.parse import urlsplit
    try:
        url = urlsplit(review["source_url"])
        if (url.scheme != "https" or not url.hostname or
                url.username is not None or url.password is not None or
                url.query or url.fragment):
            return False
    except ValueError:
        return False
    return all(type(review.get(k)) is str and
               re.fullmatch(r"[0-9a-f]{64}", review[k])
               for k in ("model_sha256", "tokenizer_sha256"))


def _d_artifact_identity(directory: Path, review: dict) -> str:
    """Read-only, bounded preflight; never download or fix model artifacts."""
    import hashlib
    from .stage5k_contract import strict_json
    try:
        raw = (directory / "manifest.json").read_bytes()
        if len(raw) > 16000:
            return "encoder_contract_invalid"
        manifest = strict_json(raw, maximum=16000)
    except (OSError, ExperimentError):
        return "encoder_contract_invalid"
    if type(manifest) is not dict or any(
            type(manifest.get(k)) is not str or
            not re.fullmatch(r"[0-9a-f]{64}", manifest[k])
            for k in ("model_sha256", "tokenizer_sha256")):
        return "encoder_contract_invalid"
    for filename, field, maximum in (
            ("model.onnx", "model_sha256", 2_000_000_000),
            ("tokenizer.json", "tokenizer_sha256", 20_000_000)):
        if manifest[field] != review[field]:
            return "encoder_identity_mismatch"
        try:
            p = directory / filename
            if p.is_symlink() or not p.is_file() or p.stat().st_size > maximum:
                return "encoder_identity_mismatch"
            digest = hashlib.sha256()
            size = 0
            with p.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    size += len(chunk)
                    if size > maximum:
                        return "encoder_identity_mismatch"
                    digest.update(chunk)
            if digest.hexdigest() != manifest[field]:
                return "encoder_identity_mismatch"
        except OSError:
            return "encoder_identity_mismatch"
    return "identity_verified"


def _prepare_d(stand, *, encoder_dir, license_review, allow_onnx):
    """Fail-closed, safe reason codes. No fabricated semantic D results."""
    if not allow_onnx or encoder_dir is None:
        return None, D_NOT_RUN, "encoder_not_provided"
    if license_review is None:
        return None, D_NOT_RUN, "license_not_approved"
    try:
        review = _read_license(license_review)
    except (ExperimentError, OSError):
        return None, D_NOT_RUN, "license_not_approved"
    if not _d_review_is_approved(review):
        return None, D_NOT_RUN, "license_not_approved"
    identity = _d_artifact_identity(Path(encoder_dir), review)
    if identity != "identity_verified":
        return None, D_NOT_RUN, identity
    try:
        from .retrieval.embeddings import LocalONNXEncoder
        encoder = LocalONNXEncoder(Path(encoder_dir))
        if (type(encoder) is not LocalONNXEncoder or
                encoder.identity.get("model_sha256") != review["model_sha256"]
                or encoder.identity.get("tokenizer_sha256") != review["tokenizer_sha256"]):
            return None, D_NOT_RUN, "encoder_contract_invalid"
    except (ValueError, TypeError, ImportError, OSError):
        return None, D_NOT_RUN, "encoder_contract_invalid"
    try:
        index = EphemeralDIndex(stand, encoder, review)
    except (ExperimentError, ValueError, TypeError, RuntimeError, OSError):
        return None, D_NOT_RUN, "index_build_failed"
    return index, "D_READY_IN_MEMORY", "identity_and_license_verified"


def _iter_offline_arms(cases, variants):
    """Offline contract-only records; not a fake retrieval benchmark."""
    for case in cases:
        for variant in variants:
            yield {
                "case_id": case["case_id"], "question": case["question"],
                "question_sha256": sha_text(case["question"]),
                "dataset_sha256": DATASET_SHA256, "variant": variant,
                "status": (D_NOT_RUN if variant == "D"
                           else "NOT_RUN_OFFLINE_STAND_NOT_PREPARED"),
                "d_prerequisite_reason": (
                    "encoder_not_provided" if variant == "D" else None),
                "evidence_recall": NOT_MEASURED,
                "intent_accuracy": NOT_MEASURED,
                "final_answer_accuracy": NOT_MEASURED,
                "model_calls": None,
                "reason": "offline_does_not_prepare_a_real_source_snapshot",
            }


def _offline_summary(results):
    return {
        "design_freeze": design_freeze(),
        "quality_gate": "QUALITY_NOT_MEASURED_UNREVIEWED_DATASET",
        "E4B": {"status": NOT_MEASURED, "D": D_NOT_RUN},
        "E5B": {"status": NOT_MEASURED},
        "real_model_inference": False,
        "results": list(results),
    }


def _offline_report(cases, variants):
    """Backwards-compatible unit-test API; live CLI uses streaming iterator."""
    return _offline_summary(tuple(_iter_offline_arms(cases, variants)))


def execute_incrementally(journal: ResearchJournal, cases: tuple,
                          variants: tuple, arm_stream, summarize, *,
                          mode: str, d_status: str = D_NOT_RUN,
                          d_reason: str = "encoder_not_provided") -> dict:
    """Append each completed case/arm before evaluating the next one.

    No continuation, rollback, overwrite or inference retry on interruption.
    All completeness assertions are reconstructed FROM durable files.
    """
    expected = [{
        "case_id": case["case_id"], "variant": variant,
        "question_sha256": sha_text(case["question"]),
    } for case in cases for variant in variants]
    if (not expected or len(expected) > 240 or
            len({(p["case_id"], p["variant"]) for p in expected}) != len(expected)):
        raise ExperimentError("invalid_expected_pairs")
    expected_map = {
        (item["case_id"], item["variant"]): item["question_sha256"]
        for item in expected
    }
    journal.record("run", {
        "run_id": journal.run_id,
        "status": "INCOMPLETE",
        "recovery_policy": "READ_ONLY_INSPECTION_NO_AUTOMATIC_RETRY",
        "mode": mode, "variants": list(variants),
        "dataset_sha256": DATASET_SHA256,
        "design_freeze": design_freeze(),
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_scope": "stage5f-pinned-10-markdown-4-pdf",
        "gold_status": "UNREVIEWED",
        "runtime": ("OFFLINE_NOT_RUN" if mode == "offline"
                    else "REAL_SOURCE_PREPARED"),
        "expected_pairs": expected,
        "expected_case_arm_count": len(expected),
        "D_prerequisite_status": d_status,
        "D_prerequisite_reason": d_reason,
    })
    seen = set()
    committed = []
    for row in arm_stream:
        if type(row) is not dict:
            raise ExperimentError("invalid_case_arm_record")
        key = (row.get("case_id"), row.get("variant"))
        if (key not in expected_map or key in seen or
                row.get("question_sha256") != expected_map[key] or
                type(row.get("question")) is not str or
                sha_text(row["question"]) != expected_map[key]):
            raise ExperimentError("unexpected_case_arm_or_question_drift")
        # Atomic JSON marker is created only after its Markdown sidecar.
        journal.record("cases/" + key[0] + "/" + key[1], row)
        seen.add(key)
        committed.append(row)
    if seen != set(expected_map):
        raise ExperimentError("incomplete_paired_comparison")
    checkpoint = ResearchJournal.inspect_run(journal.root, journal.run_id)
    if (checkpoint["completed_case_arm_count"] != len(expected) or
            checkpoint["missing_pairs"] or checkpoint["partial_pairs"] or
            checkpoint["corrupt_pairs"] or checkpoint["unexpected_pairs"] or
            checkpoint["summary_state"] != "missing"):
        raise ExperimentError("journal_incomplete_or_inconsistent")
    result = summarize(tuple(committed))
    if (type(result) is not dict or
            result.get("quality_gate") != "QUALITY_NOT_MEASURED_UNREVIEWED_DATASET"):
        raise ExperimentError("summary_quality_gate_invalid")
    summary = {key: value for key, value in result.items()
               if key != "results"}
    summary.update({
        "status": "COMPLETE",
        "run_id": journal.run_id,
        "dataset_sha256": DATASET_SHA256,
        "expected_case_arm_count": len(expected),
        "completed_case_arm_count": checkpoint["completed_case_arm_count"],
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "completion_verified_from_files": True,
        "D_prerequisite_status": d_status,
        "D_prerequisite_reason": d_reason,
    })
    # Completion is not declared before every JSON+Markdown pair is durable.
    journal.record("summary", summary)
    final = ResearchJournal.inspect_run(journal.root, journal.run_id)
    if final["status"] != "COMPLETE":
        raise ExperimentError("summary_completion_integrity_failed")
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage 5K isolated research; no production answers")
    parser.add_argument("--variant", choices=("A", "B", "C", "D", "all"), default="all")
    parser.add_argument("--mode", choices=("offline", "local"))
    parser.add_argument("--questions", type=Path,
                        help="Exact original 60-case JSON; or pinned bundled copy")
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--inspect-run",
                        help="Read-only inspection of an existing run UUID; no inference")
    parser.add_argument("--allow-real-network", action="store_true")
    parser.add_argument("--allow-development-pdf-worker", action="store_true")
    parser.add_argument("--allow-local-inference", action="store_true")
    parser.add_argument("--allow-d-onnx", action="store_true")
    parser.add_argument("--d-encoder-dir", type=Path)
    parser.add_argument("--d-license-review", type=Path)
    args = parser.parse_args(argv)
    variants = ("A", "B", "C", "D") if args.variant == "all" else (args.variant,)
    try:
        if args.inspect_run is not None:
            if (args.mode is not None or args.allow_real_network or
                    args.allow_development_pdf_worker or args.allow_local_inference or
                    args.allow_d_onnx or args.d_encoder_dir or args.d_license_review):
                raise ExperimentError("inspect_run_must_not_start_sources")
            inspection = ResearchJournal.inspect_run(
                args.output_root, args.inspect_run)
            print(canonical(inspection))
            return 0 if inspection["status"] == "COMPLETE" else 3
        if args.mode is None:
            raise ExperimentError("execution_mode_required")
        cases = load_seeds(args.questions)
        if args.mode == "local":
            if not (args.allow_real_network and args.allow_development_pdf_worker):
                raise ExperimentError("real_source_opt_ins_required")
            if any(v in ("B", "C") for v in variants) and not args.allow_local_inference:
                raise ExperimentError("local_llm_opt_in_required")
            from .ingestion.github_snapshot_provider import GitHubSnapshotProvider
            from .real_corpus_stand import prepare_real_stand
            stand = prepare_real_stand(
                provider=GitHubSnapshotProvider.from_env(),
                enable_development_pdf_worker=True,
            )
            verify_stand(stand)
        else:
            if (args.allow_real_network or args.allow_local_inference
                    or args.allow_development_pdf_worker or args.allow_d_onnx):
                raise ExperimentError("offline_mode_opt_in_conflict")
            stand = None
        journal = ResearchJournal(args.output_root)
        if stand is None:
            d_status, d_reason = D_NOT_RUN, "encoder_not_provided"
            stream = _iter_offline_arms(cases, variants)
            summarize = _offline_summary
        else:
            d_index, d_status, d_reason = _prepare_d(
                stand, encoder_dir=args.d_encoder_dir,
                license_review=args.d_license_review,
                allow_onnx=args.allow_d_onnx,
            )
            planner = LocalIntentPlanner() if any(
                v in ("B", "C") for v in variants) else None
            comparator = ResearchComparator(
                stand, planner=planner, d_index=d_index,
                d_preparation_reason=d_reason,
            )
            stream = comparator.iter_arms(cases, variants)
            summarize = lambda completed: comparator.summarize_results(
                cases, variants, completed)
        summary = execute_incrementally(
            journal, cases, variants, stream, summarize, mode=args.mode,
            d_status=d_status, d_reason=d_reason)
        print(canonical({
            "status": summary["status"], "journal_root": str(journal.run_root),
            "case_arm_count": summary["completed_case_arm_count"],
            "quality": "NOT_MEASURED",
            "D": summary["D_prerequisite_status"],
            "D_reason": summary["D_prerequisite_reason"],
        }))
        return 0
    except (ExperimentError, ValueError, OSError) as exc:
        # Do not echo raw question, exception text, credentials or full paths.
        code = str(exc) if type(exc) is ExperimentError else type(exc).__name__
        print("STAGE5K_FAILED: " + code[:120], file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
