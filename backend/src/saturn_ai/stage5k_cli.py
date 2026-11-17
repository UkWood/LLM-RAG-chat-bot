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
                    sha_text(record.get("question", "")) != digest):
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


def _prepare_d(stand, *, encoder_dir, license_review, allow_onnx):
    if not allow_onnx or encoder_dir is None or license_review is None:
        return None, D_NOT_RUN
    try:
        review = _read_license(license_review)
        from .retrieval.embeddings import LocalONNXEncoder
        encoder = LocalONNXEncoder(Path(encoder_dir))
        index = EphemeralDIndex(stand, encoder, review)
        return index, "D_READY_IN_MEMORY"
    except (ExperimentError, ValueError, OSError, ImportError):
        return None, D_NOT_RUN


def _offline_report(cases, variants):
    """Not a comparison; avoid silently replacing real stand with a fake."""
    records = []
    for case in cases:
        for variant in variants:
            records.append({
                "case_id": case["case_id"], "question": case["question"],
                "question_sha256": sha_text(case["question"]),
                "dataset_sha256": DATASET_SHA256, "variant": variant,
                "status": (D_NOT_RUN if variant == "D"
                           else "NOT_RUN_OFFLINE_STAND_NOT_PREPARED"),
                "evidence_recall": NOT_MEASURED,
                "intent_accuracy": NOT_MEASURED,
                "final_answer_accuracy": NOT_MEASURED,
                "model_calls": None,
                "reason": "offline_does_not_prepare_a_real_source_snapshot",
            })
    return {"design_freeze": design_freeze(), "quality_gate":
            "QUALITY_NOT_MEASURED_UNREVIEWED_DATASET",
            "E4B": {"status": NOT_MEASURED, "D": D_NOT_RUN},
            "E5B": {"status": NOT_MEASURED},
            "real_model_inference": False, "results": records}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage 5K isolated research; no production answers")
    parser.add_argument("--variant", choices=("A", "B", "C", "D", "all"), default="all")
    parser.add_argument("--mode", choices=("offline", "local"), required=True)
    parser.add_argument("--questions", type=Path,
                        help="Original 60-case JSON; if omitted, use exact bundled compressed copy")
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--allow-real-network", action="store_true")
    parser.add_argument("--allow-development-pdf-worker", action="store_true")
    parser.add_argument("--allow-local-inference", action="store_true")
    parser.add_argument("--allow-d-onnx", action="store_true")
    parser.add_argument("--d-encoder-dir", type=Path)
    parser.add_argument("--d-license-review", type=Path)
    args = parser.parse_args(argv)
    variants = ("A", "B", "C", "D") if args.variant == "all" else (args.variant,)
    try:
        cases = load_seeds(args.questions)
        # Fail fast on offline/source safety before writing any observation.
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
        journal.record("run", {
            "run_id": journal.run_id,
            "mode": args.mode, "variants": variants,
            "dataset_sha256": DATASET_SHA256,
            "design_freeze": design_freeze(),
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_scope": "stage5f-pinned-10-markdown-4-pdf",
            "gold_status": "UNREVIEWED",
            "runtime": "OFFLINE_NOT_RUN" if stand is None else "REAL_SOURCE_PREPARED",
        })
        if stand is None:
            result = _offline_report(cases, variants)
        else:
            d_index, d_status = _prepare_d(
                stand, encoder_dir=args.d_encoder_dir,
                license_review=args.d_license_review,
                allow_onnx=args.allow_d_onnx,
            )
            planner = LocalIntentPlanner() if any(v in ("B", "C") for v in variants) else None
            comparator = ResearchComparator(
                stand, planner=planner, d_index=d_index,
            )
            result = comparator.run(cases, variants)
            result["D_prerequisite_status"] = d_status
        for row in result["results"]:
            journal.record("cases/" + row["case_id"] + "/" + row["variant"], row)
        # This is an append-only report, never a gold/scored dataset.
        summary = {key: value for key, value in result.items() if key != "results"}
        summary["case_arm_count"] = len(result["results"])
        summary["expected_case_arm_count"] = len(cases) * len(variants)
        summary["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        journal.record("summary", summary)
        print(canonical({
            "status": "REPORT_WRITTEN", "journal_root": str(journal.run_root),
            "case_arm_count": len(result["results"]),
            "quality": "NOT_MEASURED",
            "D": result.get("D_prerequisite_status", D_NOT_RUN),
        }))
        return 0
    except (ExperimentError, ValueError, OSError) as exc:
        # Prevent leaking full paths, question content or model responses.
        code = str(exc) if type(exc) is ExperimentError else type(exc).__name__
        print("STAGE5K_FAILED: " + code[:120], file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
