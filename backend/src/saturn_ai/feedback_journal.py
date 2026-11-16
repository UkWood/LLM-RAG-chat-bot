"""Stage 5J append-only, database-free Markdown feedback journal.

No HTTP or model dependencies. Front matter is a restricted JSON-scalar dialect
of YAML: one JSON value per key. Markdown bodies are inert fenced text, not
trusted rendered HTML. The metadata is authoritative for exact round trips.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import uuid

SCHEMA_VERSION = 1
CHANNELS = frozenset(("lab", "production"))
STATUSES = frozenset(("answered", "partial", "clarification", "needs_support", "error"))
_ID = re.compile(r"^[0-9a-f]{32}$")
_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
# Reject rather than log a question/answer which appears to contain credentials.
# This is deliberately narrow: operators must also avoid entering secrets.
_SECRET = re.compile(
    r"(?i)(?:authorization\s*[:=]|proxy-authorization\s*[:=]|"
    r"-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----|"
    r"(?:password|passwd|secret|api[_-]?key|access[_-]?token|"
    r"ssh[_-]?(?:password|key|passphrase))\s*[:=])"
)
MAX_QUESTION = 4000
MAX_ANSWER = 12000
MAX_COMMENT = 8000
MAX_RECORD_BYTES = 512_000


class JournalError(RuntimeError):
    """Public code-only error; never expose paths or original contents."""


class JournalWriteError(JournalError):
    pass


@dataclass(frozen=True)
class RequestRef:
    request_id: str
    channel: str
    received_at_utc: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _valid_text(value, *, label: str, limit: int, nonempty=False) -> str:
    if type(value) is not str or len(value) > limit or "\x00" in value:
        raise ValueError("invalid_" + label)
    if nonempty and not value.strip():
        raise ValueError("invalid_" + label)
    if _SECRET.search(value):
        raise ValueError("sensitive_content_rejected")
    return value


def _fenced(value: str) -> str:
    # Fence is longer than any consecutive run of tildes in user text.
    runs = [len(m.group()) for m in re.finditer(r"~+", value)]
    fence = "~" * max(4, max(runs, default=0) + 1)
    return fence + "text\n" + value + "\n" + fence + "\n"


def _document(record: dict, body: tuple[tuple[str, str], ...]) -> bytes:
    lines = ["---"]
    for key, value in record.items():
        if not _KEY.fullmatch(key):
            raise ValueError("invalid_metadata_key")
        lines.append(key + ": " + json.dumps(value, ensure_ascii=True,
                                             separators=(",", ":"), sort_keys=True))
    lines.append("---")
    for heading, value in body:
        lines.extend(("", "## " + heading, "", _fenced(value)))
    raw = ("\n".join(lines) + "\n").encode("utf-8")
    if len(raw) > MAX_RECORD_BYTES:
        raise ValueError("record_too_large")
    return raw


def _parse_document(raw: bytes) -> dict:
    if len(raw) > MAX_RECORD_BYTES:
        raise JournalError("record_too_large")
    try:
        txt = raw.decode("utf-8")
        prefix, rest = txt.split("---\n", 1)
        meta, _body = rest.split("\n---\n", 1)
        if prefix:
            raise ValueError
        result = {}
        for line in meta.split("\n"):
            key, sep, value = line.partition(": ")
            if not sep or not _KEY.fullmatch(key) or key in result:
                raise ValueError
            result[key] = json.loads(value)
        if result.get("schema_version") != SCHEMA_VERSION:
            raise ValueError
        return result
    except (UnicodeError, ValueError, TypeError):
        raise JournalError("malformed_record") from None


def _csv_safe(value: object) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    # Spreadsheet apps may interpret a cell starting with whitespace + formula
    # sigils. Prefix the WHOLE cell with apostrophe, including CR/LF/tab cases.
    if text.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")) or (
        text and text[0] in "\t\r\n"
    ):
        return "'" + text
    return text


class MarkdownFeedbackJournal:
    """Standalone filesystem component; append-only even across process restarts.

    Each request is durable before inference begins. A missing answer.md means
    interrupted processing, not an implicit success. Review state is derived from
    the latest immutable review event, never stored as a mutable status file.
    """

    def __init__(self, root: Path | str, *,
                 production_retention_days: int | None = None,
                 production_deletion_policy: str = "manual"):
        root = Path(root).expanduser()
        if not root.is_absolute():
            raise ValueError("journal_root_must_be_absolute")
        repo = Path(__file__).resolve().parents[3]
        absolute = root.resolve()
        if absolute == repo or repo in absolute.parents:
            raise ValueError("journal_root_inside_git_worktree")
        if (production_retention_days is not None and
                (type(production_retention_days) is not int or
                 not 1 <= production_retention_days <= 36500)):
            raise ValueError("invalid_production_retention")
        if production_deletion_policy not in ("manual", "explicit_future_job"):
            raise ValueError("invalid_production_deletion_policy")
        self.root = absolute
        self.production_retention_days = production_retention_days
        self.production_deletion_policy = production_deletion_policy
        # No cleanup job, especially not for laboratory observations.
        try:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
            for channel in CHANNELS:
                (self.root / channel).mkdir(mode=0o700, exist_ok=True)
        except OSError:
            raise JournalWriteError("journal_directory_unavailable") from None
        for base in (self.root, self.root / "lab", self.root / "production"):
            if base.is_symlink():
                raise ValueError("journal_symlink_forbidden")

    def _checked(self, path: Path) -> Path:
        if not path.is_relative_to(self.root):
            raise ValueError("unsafe_journal_path")
        # Disallow all symlinks, including intermediate components. Identity is
        # still checked after resolution for defense in depth.
        current = path
        while current != self.root:
            if current.is_symlink():
                raise JournalError("journal_symlink_forbidden")
            current = current.parent
        if not path.resolve().is_relative_to(self.root):
            raise JournalError("journal_path_escape")
        return path

    @staticmethod
    def _channel(channel: str) -> str:
        if channel not in CHANNELS or type(channel) is not str:
            raise ValueError("invalid_channel")
        return channel

    @staticmethod
    def _id(value: str) -> str:
        if type(value) is not str or not _ID.fullmatch(value):
            raise ValueError("invalid_request_id")
        return value

    def _atomic_new(self, path: Path, data: bytes):
        path = self._checked(path)
        temp = path.with_name("." + uuid.uuid4().hex + ".tmp")
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            flags |= getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(temp, flags, 0o600)
            try:
                with os.fdopen(fd, "wb") as file:
                    file.write(data)
                    file.flush()
                    os.fsync(file.fileno())
                # Atomic hard link fails with EEXIST; never replace a file.
                os.link(temp, path, follow_symlinks=False)
                folder = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(folder)
                finally:
                    os.close(folder)
            finally:
                temp.unlink(missing_ok=True)
        except OSError:
            temp.unlink(missing_ok=True)
            raise JournalWriteError("journal_write_failed") from None

    def start_request(self, question: str, *, channel: str,
                      run_id: str) -> RequestRef:
        channel = self._channel(channel)
        question = _valid_text(question, label="question", limit=MAX_QUESTION,
                               nonempty=True)
        run_id = _valid_text(run_id, label="run_id", limit=120, nonempty=True)
        if any(ord(c) < 32 or ord(c) > 126 for c in run_id):
            raise ValueError("invalid_run_id")
        now = _utc_now()
        date = now[:10].replace("-", "/")
        request_id = uuid.uuid4().hex
        directory = self._checked(self.root / channel / date / request_id)
        metadata = dict(schema_version=SCHEMA_VERSION, record_type="request",
                        request_id=request_id, channel=channel,
                        received_at_utc=now, run_id=run_id,
                        question=question)
        try:
            directory.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            self._checked(directory.parent)
            directory.mkdir(mode=0o700, exist_ok=False)
        except OSError:
            raise JournalWriteError("request_directory_failed") from None
        self._atomic_new(directory / "request.md",
                         _document(metadata, (("Оригинальный вопрос", question),)))
        return RequestRef(request_id, channel, now)

    def _entry_dir(self, request_id: str, channel: str) -> Path:
        request_id = self._id(request_id)
        channel = self._channel(channel)
        found = list((self.root / channel).glob("*/*/*/" + request_id))
        if len(found) != 1:
            raise JournalError("request_not_found_or_ambiguous")
        directory = self._checked(found[0])
        if not (directory / "request.md").is_file():
            raise JournalError("request_file_missing")
        return directory

    def finish_request(self, ref: RequestRef, *, outcome: dict,
                       duration_ms: float, code_revision: str,
                       model_id: str, model_sha256: str,
                       error_code: str | None = None) -> None:
        if not isinstance(ref, RequestRef):
            raise ValueError("invalid_request_reference")
        directory = self._entry_dir(ref.request_id, ref.channel)
        request = self._read(directory / "request.md")
        if (request["channel"] != ref.channel or
                request["received_at_utc"] != ref.received_at_utc or
                request["request_id"] != ref.request_id):
            raise JournalError("request_reference_mismatch")
        answer = outcome.get("answer")
        if type(answer) is not dict or answer.get("status") not in STATUSES:
            raise ValueError("invalid_answer_contract")
        text = _valid_text(answer.get("answer_text"), label="answer",
                           limit=MAX_ANSWER)
        citations = answer.get("citations", [])
        diagnostics = answer.get("diagnostics", [])
        if not isinstance(citations, (tuple, list)) or not isinstance(diagnostics, (tuple, list)):
            raise ValueError("invalid_answer_evidence")
        if type(duration_ms) not in (float, int) or not 0 <= duration_ms <= 86_400_000:
            raise ValueError("invalid_duration")
        if error_code is not None and not re.fullmatch(r"[A-Za-z0-9_]{1,100}", error_code):
            raise ValueError("invalid_error_code")
        record = dict(
            schema_version=SCHEMA_VERSION, record_type="answer",
            request_id=ref.request_id, channel=ref.channel,
            finished_at_utc=_utc_now(), duration_ms=round(duration_ms, 3),
            status=answer["status"], reason_code=answer.get("reason_code"),
            snapshot_id=answer.get("snapshot_id"), bundle_id=answer.get("bundle_id"),
            code_revision=code_revision, policy_revision=answer.get("policy_revision"),
            model_id=model_id, declared_model_sha256=model_sha256,
            model_digest_server_verified=False, citations=citations,
            diagnostics=diagnostics, unresolved_need_ids=answer.get("unresolved_need_ids", []),
            answer_text=text, technical_error=error_code,
            stage_trace=outcome.get("stage_trace", {}),
            local_inference=outcome.get("local_inference"),
        )
        # Check all structured fields as well as the human-facing response.
        if _SECRET.search(json.dumps(record, ensure_ascii=False)):
            raise ValueError("sensitive_content_rejected")
        self._atomic_new(directory / "answer.md", _document(record, (("Ответ консультанта", text),)))

    def save_review(self, request_id: str, *, expert: str,
                    comment: str, channel: str = "lab") -> dict:
        if self._channel(channel) != "lab":
            raise ValueError("production_review_forbidden")
        expert = _valid_text(expert, label="expert", limit=80, nonempty=True)
        comment = _valid_text(comment, label="comment", limit=MAX_COMMENT)
        directory = self._entry_dir(request_id, channel)
        if not (directory / "answer.md").is_file():
            raise JournalError("answer_not_ready")
        decision = "commented" if comment.strip() else "accepted"
        review_id = uuid.uuid4().hex
        event = dict(schema_version=SCHEMA_VERSION, record_type="review",
                     review_event_id=review_id, request_id=request_id,
                     channel=channel, reviewed_at_utc=_utc_now(),
                     expert=expert, decision=decision, comment=comment)
        reviews = self._checked(directory / "reviews")
        try:
            reviews.mkdir(mode=0o700, exist_ok=True)
        except OSError:
            raise JournalWriteError("reviews_directory_failed") from None
        self._atomic_new(reviews / (review_id + ".md"),
                         _document(event, (("Комментарий эксперта", comment),)))
        return event

    def _read(self, path: Path) -> dict:
        self._checked(path)
        try:
            return _parse_document(path.read_bytes())
        except OSError:
            raise JournalError("journal_read_failed") from None

    def get_entry(self, request_id: str, *, channel: str = "lab") -> dict:
        directory = self._entry_dir(request_id, channel)
        request = self._read(directory / "request.md")
        answer_file = directory / "answer.md"
        answer = self._read(answer_file) if answer_file.is_file() else None
        reviews = []
        if channel == "lab":
            for path in (directory / "reviews").glob("*.md"):
                event = self._read(path)
                if (event.get("request_id") != request_id or
                        event.get("record_type") != "review" or
                        event.get("review_event_id") != path.stem or
                        event.get("decision") not in ("accepted", "commented")):
                    raise JournalError("invalid_review_record")
                reviews.append(event)
        reviews.sort(key=lambda item: (item["reviewed_at_utc"], item["review_event_id"]))
        return dict(request=request, answer=answer, reviews=reviews,
                    review_status=(reviews[-1]["decision"] if reviews else "unreviewed"))

    def list_entries(self, *, channel: str = "lab",
                     status: str | None = None, limit: int = 100) -> list[dict]:
        channel = self._channel(channel)
        if status is not None and status not in ("accepted", "commented", "unreviewed"):
            raise ValueError("invalid_review_filter")
        if type(limit) is not int or not 1 <= limit <= 10000:
            raise ValueError("invalid_limit")
        paths = list((self.root / channel).glob("*/*/*/*/request.md"))
        entries = []
        for path in paths:
            item = self.get_entry(path.parent.name, channel=channel)
            if status is None or item["review_status"] == status:
                entries.append(item)
        entries.sort(key=lambda x: (x["request"]["received_at_utc"],
                                    x["request"]["request_id"]), reverse=True)
        return entries[:limit]

    def export_json(self, *, channel: str = "lab",
                    status: str | None = None) -> str:
        return json.dumps(self.list_entries(channel=channel, status=status, limit=10000),
                          ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    def export_csv(self, *, channel: str = "lab",
                   status: str | None = None) -> str:
        out = io.StringIO(newline="")
        writer = csv.writer(out, lineterminator="\r\n")
        fields = ("request_id", "received_at_utc", "channel", "question",
                  "run_id", "finished_at_utc", "duration_ms", "answer_status",
                  "reason_code", "answer_text", "snapshot_id", "bundle_id",
                  "code_revision", "policy_revision", "model_id",
                  "declared_model_sha256", "citations", "diagnostics",
                  "review_status", "reviews")
        writer.writerow(fields)
        for item in self.list_entries(channel=channel, status=status, limit=10000):
            r, a = item["request"], item["answer"] or {}
            row = (r["request_id"], r["received_at_utc"], r["channel"],
                   r["question"], r["run_id"], a.get("finished_at_utc", ""),
                   a.get("duration_ms", ""), a.get("status", "interrupted"),
                   a.get("reason_code", ""), a.get("answer_text", ""),
                   a.get("snapshot_id", ""), a.get("bundle_id", ""),
                   a.get("code_revision", ""), a.get("policy_revision", ""),
                   a.get("model_id", ""), a.get("declared_model_sha256", ""),
                   a.get("citations", []), a.get("diagnostics", []),
                   item["review_status"], item["reviews"])
            writer.writerow([_csv_safe(value) for value in row])
        return out.getvalue()
