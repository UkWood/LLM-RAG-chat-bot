"""Stage 5J offline tests: no source/network/model downloads and no DB."""
from concurrent.futures import ThreadPoolExecutor
import csv
from io import StringIO
import http.client
import json
import os
from pathlib import Path
import subprocess
import socket
import tempfile
from threading import Thread
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from saturn_ai.feedback_journal import (
    JournalError, JournalWriteError, MarkdownFeedbackJournal, RequestRef,
    _csv_safe,
)
from saturn_ai.feedback_lab import (
    EXACT_MODEL_ENDPOINT, FeedbackLabHTTPServer, FeedbackLabService,
)
from saturn_ai.grounding.saturn_local_provider import SaturnLocalModelConfig


RUN = "a" * 32
SHA = "b" * 40
MODEL_SHA = "c" * 64


def outcome(question=""):
    return {
        "answer": {
            "status": "answered",
            "answer_text": "Реальный текст ответа\n<unsafe> & ~~~~ " + question,
            "snapshot_id": "snapshot-real-test",
            "bundle_id": "bundle-test",
            "policy_revision": "final-policy-test",
            "reason_code": None,
            "citations": [
                {"citation_id": "C1", "title": "Документ",
                 "canonical_url": "https://example.org/doc.pdf",
                 "source_type": "pdf", "physical_page": 7,
                 "pdf_bytes_sha256": "d" * 64,
                 "pdf_parser_version": "test/1"},
            ],
            "diagnostics": [["verified", 1]],
            "unresolved_need_ids": [],
        },
        "stage_trace": {"pipeline": "accepted"},
        "local_inference": {"model_id": "Qwen3-4B", "successful_inference_requests": 1},
    }


def finish(journal, ref, *, response=None):
    journal.finish_request(
        ref, outcome=response if response is not None else outcome(),
        duration_ms=12.345, code_revision=SHA,
        model_id="Qwen3-4B", model_sha256=MODEL_SHA)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "journal"
        self.journal = MarkdownFeedbackJournal(
            self.root, production_retention_days=30,
            production_deletion_policy="explicit_future_job")

    def start(self, question="Вопрос?", channel="lab"):
        return self.journal.start_request(question, channel=channel, run_id=RUN)

    def test_question_answer_markdown_and_provenance(self):
        ref = self.start()
        finish(self.journal, ref)
        entry = self.journal.get_entry(ref.request_id)
        self.assertEqual(entry["request"]["question"], "Вопрос?")
        self.assertEqual(entry["request"]["request_id"], ref.request_id)
        self.assertEqual(entry["answer"]["answer_text"], outcome()["answer"]["answer_text"])
        self.assertEqual(entry["answer"]["citations"][0]["physical_page"], 7)
        self.assertEqual(entry["answer"]["snapshot_id"], "snapshot-real-test")
        self.assertEqual(entry["answer"]["code_revision"], SHA)
        self.assertEqual(entry["answer"]["policy_revision"], "final-policy-test")
        self.assertEqual(entry["answer"]["declared_model_sha256"], MODEL_SHA)
        files = list(self.root.glob("lab/*/*/*/*/*.md"))
        self.assertEqual(sorted(x.name for x in files), ["answer.md", "request.md"])
        for file in files:
            self.assertTrue(file.read_bytes().startswith(b"---\n"))
        self.assertTrue(entry["request"]["received_at_utc"].endswith("Z"))
        self.assertTrue(entry["answer"]["finished_at_utc"].endswith("Z"))
        self.assertFalse(list(self.root.rglob("*.db")))

    def test_technical_error_is_persisted_without_positive_review(self):
        ref = self.start()
        broken = outcome()
        broken["answer"].update(status="error", reason_code="local_provider_unavailable",
                                answer_text="Не удалось выполнить проверку.", citations=[])
        finish(self.journal, ref, response=broken)
        value = self.journal.get_entry(ref.request_id)
        self.assertEqual(value["answer"]["status"], "error")
        self.assertEqual(value["answer"]["reason_code"], "local_provider_unavailable")
        self.assertEqual(value["review_status"], "unreviewed")

    def test_interruption_leaves_request_without_answer(self):
        ref = self.start()
        entry = self.journal.get_entry(ref.request_id)
        self.assertIsNone(entry["answer"])
        self.assertEqual(entry["review_status"], "unreviewed")
        self.assertIn("request.md", [p.name for p in self.root.rglob("request.md")])

    def test_explicit_acceptance_comment_and_immutable_history(self):
        ref = self.start()
        finish(self.journal, ref)
        self.assertEqual(self.journal.get_entry(ref.request_id)["review_status"], "unreviewed")
        first = self.journal.save_review(ref.request_id, expert="Инженер", comment="")
        self.assertEqual(first["decision"], "accepted")
        second = self.journal.save_review(ref.request_id, expert="Инженер",
                                          comment="Не ошибка,\nно добавьте ссылку.")
        self.assertEqual(second["decision"], "commented")
        self.assertNotEqual(first["review_event_id"], second["review_event_id"])
        reviews = self.journal.get_entry(ref.request_id)["reviews"]
        self.assertEqual(len(reviews), 2)
        self.assertEqual({x["decision"] for x in reviews}, {"accepted", "commented"})
        self.assertEqual(self.journal.get_entry(ref.request_id)["review_status"], "commented")
        again = self.journal.save_review(ref.request_id, expert="Другой", comment="  ")
        self.assertEqual(again["decision"], "accepted")
        self.assertEqual(len(self.journal.get_entry(ref.request_id)["reviews"]), 3)

    def test_concurrency_distinct_ids_and_immutable_files(self):
        def worker(i):
            ref = self.start("Вопрос %d" % i)
            finish(self.journal, ref)
            return ref.request_id
        with ThreadPoolExecutor(max_workers=12) as pool:
            ids = list(pool.map(worker, range(45)))
        self.assertEqual(len(set(ids)), 45)
        self.assertEqual(len(self.journal.list_entries()), 45)
        self.assertEqual(len(list(self.root.rglob("answer.md"))), 45)

    def test_restart_restores_from_markdown_only_and_filter(self):
        a = self.start("Положительный?")
        b = self.start("С замечанием?")
        c = self.start("Без оценки?")
        for ref in (a, b, c):
            finish(self.journal, ref)
        self.journal.save_review(a.request_id, expert="E1", comment="")
        self.journal.save_review(b.request_id, expert="E2", comment="Вопрос по ссылке")
        recovered = MarkdownFeedbackJournal(self.root)
        self.assertEqual(len(recovered.list_entries()), 3)
        for status in ("accepted", "commented", "unreviewed"):
            self.assertEqual(len(recovered.list_entries(status=status)), 1)
        self.assertEqual(recovered.get_entry(b.request_id)["reviews"][0]["comment"],
                         "Вопрос по ссылке")

    def test_markdown_unicode_html_and_fence_injection_roundtrip(self):
        string = '---\n# <script>alert(1)</script>\n~~~\n~~~~\n"\n\\\nЖ 你好 🚀'
        ref = self.start(string)
        result = outcome(string)
        finish(self.journal, ref, response=result)
        entry = self.journal.get_entry(ref.request_id)
        self.assertEqual(entry["request"]["question"], string)
        self.assertEqual(entry["answer"]["answer_text"], result["answer"]["answer_text"])
        self.assertIn('~~~~~text', next(self.root.rglob("request.md")).read_text())

    def test_write_failure_and_duplicate_answer_not_silent(self):
        ref = self.start()
        with patch.object(self.journal, "_atomic_new",
                          side_effect=JournalWriteError("journal_write_failed")):
            with self.assertRaises(JournalWriteError):
                finish(self.journal, ref)
        self.assertIsNone(self.journal.get_entry(ref.request_id)["answer"])
        finish(self.journal, ref)
        with self.assertRaises(JournalWriteError):
            finish(self.journal, ref)
        self.assertEqual(self.journal.get_entry(ref.request_id)["answer"]["status"],
                         "answered")

    def test_production_has_no_review_and_no_visitor_metadata(self):
        ref = self.start("Реальный вопрос", channel="production")
        finish(self.journal, ref)
        entry = self.journal.get_entry(ref.request_id, channel="production")
        self.assertEqual(entry["review_status"], "unreviewed")
        self.assertEqual(entry["request"]["channel"], "production")
        self.assertFalse(list(self.root.glob("production/**/reviews")))
        raw = next(self.root.glob("production/**/request.md")).read_text()
        for keyword in ("user_agent:", "ip_address:", "cookie:", "authorization:"):
            self.assertNotIn(keyword, raw)
        with self.assertRaises(ValueError):
            self.journal.save_review(ref.request_id, channel="production",
                                     expert="E1", comment="")

    def test_csv_json_exact_source_values_and_formula_guard(self):
        question = " \t=HYPERLINK(\"http://evil\", \"x\")"
        ref = self.start(question)
        result = outcome()
        result["answer"]["answer_text"] = "@SUM(A1:A2)"
        finish(self.journal, ref, response=result)
        review = self.journal.save_review(ref.request_id, expert="E",
                                          comment="+CMD|'/C calc'")
        exported = json.loads(self.journal.export_json())
        self.assertEqual(exported[0]["request"]["question"], question)
        self.assertEqual(exported[0]["answer"]["answer_text"], "@SUM(A1:A2)")
        self.assertEqual(exported[0]["reviews"][0]["comment"], review["comment"])
        csv_rows = list(csv.DictReader(StringIO(self.journal.export_csv())))
        self.assertEqual(len(csv_rows), 1)
        self.assertEqual(csv_rows[0]["question"], "'" + question)
        self.assertEqual(csv_rows[0]["answer_text"], "'@SUM(A1:A2)")
        self.assertEqual(json.loads(csv_rows[0]["reviews"])[0]["comment"], review["comment"])
        self.assertEqual(_csv_safe("\t=1"), "'\t=1")
        self.assertEqual(_csv_safe("-12"), "'-12")


    def test_cr01_new_and_existing_safe_directory_linux(self):
        """Fresh owner-only 0700 tree and pre-existing safe tree both start."""
        fresh = Path(self.temp.name) / "new-secure-journal"
        j = MarkdownFeedbackJournal(fresh)
        for item in (fresh, fresh / "lab", fresh / "production"):
            self.assertEqual(item.stat().st_mode & 0o777, 0o700)
            self.assertEqual(item.stat().st_uid, os.geteuid())
        self.assertEqual(MarkdownFeedbackJournal(fresh).root, j.root)
        existing = Path(self.temp.name) / "existing-secure-journal"
        existing.mkdir(mode=0o700)
        for channel in ("lab", "production"):
            (existing / channel).mkdir(mode=0o700)
        self.assertEqual(MarkdownFeedbackJournal(existing).root, existing)

    def test_cr01_foreign_owner_rejected_without_permissions_change(self):
        existing = Path(self.temp.name) / "foreign-owner"
        existing.mkdir(mode=0o700)
        before = existing.stat().st_mode & 0o777
        with patch("saturn_ai.feedback_journal.os.geteuid",
                   return_value=os.geteuid() + 1000):
            with self.assertRaises(JournalError):
                MarkdownFeedbackJournal(existing)
        self.assertEqual(existing.stat().st_mode & 0o777, before)
        self.assertFalse((existing / "lab").exists())

    def test_cr01_unsupported_filesystem_atomic_link_fails_closed(self):
        root = Path(self.temp.name) / "no-hardlinks"
        with patch("saturn_ai.feedback_journal.os.link",
                   side_effect=OSError("hardlinks disabled")):
            with self.assertRaisesRegex(JournalError,
                                        "secure_filesystem_unavailable"):
                MarkdownFeedbackJournal(root)
        self.assertFalse(list(root.glob("*.probe")))
        self.assertFalse(list(root.glob("*.link")))
        self.assertEqual(len(list(root.rglob("request.md"))), 0)

    def test_cr01_existing_root_is_not_chmodded_and_files_unmodified(self):
        existing = Path(self.temp.name) / "insecure-root"
        existing.mkdir(mode=0o700)
        marker = existing / "original.md"
        marker.write_text("untouched", encoding="utf-8")
        os.chmod(marker, 0o600)
        before = (marker.read_bytes(), marker.stat().st_mtime_ns,
                  marker.stat().st_mode & 0o777)
        os.chmod(existing, 0o777)
        with self.assertRaises(JournalError):
            MarkdownFeedbackJournal(existing)
        self.assertEqual(existing.stat().st_mode & 0o777, 0o777)
        self.assertEqual((marker.read_bytes(), marker.stat().st_mtime_ns,
                          marker.stat().st_mode & 0o777), before)

    def test_cr01_insecure_lab_and_production_are_rejected(self):
        for channel in ("lab", "production"):
            with self.subTest(channel=channel):
                existing = Path(self.temp.name) / ("unsafe-" + channel)
                existing.mkdir(mode=0o700)
                for name in ("lab", "production"):
                    (existing / name).mkdir(mode=0o700)
                os.chmod(existing / channel, 0o755)
                with self.assertRaises(JournalError):
                    MarkdownFeedbackJournal(existing)
                self.assertEqual((existing / channel).stat().st_mode & 0o777,
                                 0o755)

    def test_cr01_source_root_symlink_and_ancestor_symlink_are_rejected(self):
        target = Path(self.temp.name) / "actual-target"
        target.mkdir(mode=0o700)
        alias = Path(self.temp.name) / "alias-target"
        alias.symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError):
            MarkdownFeedbackJournal(alias)
        with self.assertRaises(ValueError):
            MarkdownFeedbackJournal(alias / "journal")
        self.assertFalse((target / "journal").exists())

    def test_cr01_unsafe_intermediate_directory_is_rejected(self):
        root = Path(self.temp.name) / "nested-journal"
        journal = MarkdownFeedbackJournal(root)
        from datetime import datetime, timezone
        year = root / "lab" / datetime.now(timezone.utc).strftime("%Y")
        year.mkdir(mode=0o700)
        os.chmod(year, 0o775)
        with self.assertRaises(JournalError):
            MarkdownFeedbackJournal(root)
        with self.assertRaises(JournalError):
            journal.start_request("question", channel="lab", run_id=RUN)
        self.assertFalse(list(root.glob("lab/2026/**/*.md")))
        self.assertEqual(year.stat().st_mode & 0o777, 0o775)

    def test_cr01_nested_symlink_rejected_and_does_not_follow(self):
        root = Path(self.temp.name) / "links-journal"
        MarkdownFeedbackJournal(root)
        outside = Path(self.temp.name) / "outside-data"
        outside.mkdir(mode=0o700)
        (root / "lab" / "2026").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(JournalError):
            MarkdownFeedbackJournal(root)
        self.assertFalse(list(outside.iterdir()))

    def test_cr01_separate_temp_git_checkout_is_rejected(self):
        git_root = Path(self.temp.name) / "other-git-checkout"
        git_root.mkdir(mode=0o700)
        subprocess.run(["git", "init", "-q", str(git_root)],
                       check=True, capture_output=True)
        with self.assertRaises(ValueError):
            MarkdownFeedbackJournal(git_root / "journal")
        self.assertFalse((git_root / "journal").exists())

    def test_cr01_new_rag_and_trusted_site_checkout_rejected(self):
        repo = Path(__file__).resolve().parents[3]
        with self.assertRaises(ValueError):
            MarkdownFeedbackJournal(repo / "feedback-journal")
        trusted = Path(self.temp.name) / "Saturn-Main-Site"
        trusted.mkdir(mode=0o700)
        with self.assertRaises(ValueError):
            MarkdownFeedbackJournal(trusted / "journal")
        self.assertFalse((trusted / "journal").exists())

    def test_cr01_symlinked_existing_file_fails_on_restart(self):
        root = Path(self.temp.name) / "file-links"
        MarkdownFeedbackJournal(root)
        protected = Path(self.temp.name) / "original"
        protected.write_text("private", encoding="utf-8")
        (root / "lab" / "linked.md").symlink_to(protected)
        with self.assertRaises(JournalError):
            MarkdownFeedbackJournal(root)
        self.assertEqual(protected.read_text(), "private")

    def test_cr02_csv_and_json_export_all_rows_above_10000(self):
        """Synthetic source enumeration: no creation of 10k journal files."""
        entries = []
        for i in range(10023):
            entries.append({
                "request": {
                    "request_id": f"{i:032x}",
                    "received_at_utc": "2026-11-16T00:00:00Z",
                    "channel": "lab",
                    "question": "Вопрос 你好 " + str(i),
                    "run_id": RUN,
                },
                "answer": {
                    "finished_at_utc": "2026-11-16T00:00:01Z",
                    "duration_ms": 7,
                    "status": "answered",
                    "reason_code": None,
                    "answer_text": "Ответ " + str(i),
                    "snapshot_id": "synthetic",
                    "bundle_id": "synthetic",
                    "code_revision": SHA,
                    "policy_revision": "synthetic",
                    "model_id": "synthetic",
                    "declared_model_sha256": MODEL_SHA,
                    "citations": [],
                    "diagnostics": [],
                },
                "reviews": [],
                "review_status": "accepted",
            })
        with patch.object(self.journal, "list_entries", return_value=entries) as listing:
            csv_result = self.journal.export_csv(channel="lab", status="accepted")
            json_result = self.journal.export_json(channel="lab", status="accepted")
        self.assertEqual(listing.call_count, 2)
        for call in listing.call_args_list:
            self.assertEqual(call.kwargs,
                             {"channel": "lab", "status": "accepted", "limit": None})
        csv_rows = list(csv.DictReader(StringIO(csv_result)))
        json_rows = json.loads(json_result)
        self.assertEqual(len(csv_rows), 10023)
        self.assertEqual(len(json_rows), 10023)
        self.assertEqual({r["request_id"] for r in csv_rows},
                         {r["request"]["request_id"] for r in json_rows})
        self.assertEqual(csv_rows[-1]["question"], entries[-1]["request"]["question"])
        self.assertEqual(csv_rows[-1]["answer_text"], entries[-1]["answer"]["answer_text"])

    def test_no_path_traversal_secrets_and_repository_root(self):
        with self.assertRaises(ValueError):
            self.journal.get_entry("../escape")
        with self.assertRaises(ValueError):
            self.start("Authorization: Bearer token")
        with self.assertRaises(ValueError):
            self.start("password=abc")
        with self.assertRaises(ValueError):
            self.start("-----BEGIN OPENSSH PRIVATE KEY-----")
        with self.assertRaises(ValueError):
            self.journal.start_request("hello", channel="../production", run_id=RUN)
        with self.assertRaises(ValueError):
            MarkdownFeedbackJournal(Path(__file__).resolve().parents[3])
        self.assertEqual(len(self.journal.list_entries()), 0)

    def test_symlink_escape_and_limit(self):
        ref = self.start()
        directory = self.journal._entry_dir(ref.request_id, "lab")
        outside = Path(self.temp.name) / "external.md"
        outside.write_text("steal")
        (directory / "answer.md").symlink_to(outside)
        with self.assertRaises(JournalError):
            self.journal.get_entry(ref.request_id)
        with self.assertRaises(ValueError):
            self.start("x" * 4001)

    def test_review_requires_answer_and_records_are_never_mutated(self):
        ref = self.start()
        with self.assertRaises(JournalError):
            self.journal.save_review(ref.request_id, expert="E", comment="")
        files_before = list(self.root.rglob("*.md"))
        self.assertEqual(len(files_before), 1)


class LabServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal = MarkdownFeedbackJournal(Path(self.temp.name) / "journal")
        self.stand = SimpleNamespace(
            snapshot=SimpleNamespace(snapshot_id="snapshot-real-test"),
            bundle=SimpleNamespace(manifest=SimpleNamespace(bundle_id="bundle-test")))
        self.config = SaturnLocalModelConfig(
            EXACT_MODEL_ENDPOINT, "Qwen3-4B", MODEL_SHA)

    def service(self, runner):
        return FeedbackLabService(
            stand=self.stand, journal=self.journal, model_config=self.config,
            run_id=RUN, code_revision=SHA, question_runner=runner)

    def test_uses_actual_provider_type_and_persists_question_answer(self):
        def runner(stand, question, *, draft_provider):
            self.assertEqual(type(draft_provider).__name__, "SaturnLocalClaimProvider")
            self.assertIs(stand, self.stand)
            return outcome(question)
        item = self.service(runner).ask("Тест")
        self.assertEqual(item["answer"]["status"], "answered")
        self.assertEqual(item["review_status"], "unreviewed")
        self.assertEqual(item["answer"]["model_id"], "Qwen3-4B")

    def test_failure_records_error_without_original_exception_message(self):
        def failed(_stand, _question, *, draft_provider):
            raise RuntimeError("Authorization: SECRET!!!!")
        item = self.service(failed).ask("Тест ошибки")
        self.assertEqual(item["answer"]["status"], "error")
        self.assertEqual(item["answer"]["technical_error"], "lab_runtime_RuntimeError")
        self.assertNotIn("SECRET", self.journal.export_json())
        self.assertEqual(item["review_status"], "unreviewed")

    def test_interrupt_not_caught_and_question_survives(self):
        def interrupted(_stand, _question, *, draft_provider):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.service(interrupted).ask("Прерывание")
        entries = self.journal.list_entries()
        self.assertEqual(len(entries), 1)
        self.assertIsNone(entries[0]["answer"])

    def test_endpoint_cannot_change_to_cloud_or_other_loopback_port(self):
        config = SaturnLocalModelConfig(
            "http://127.0.0.1:18080/v1/chat/completions", "model", MODEL_SHA)
        with self.assertRaises(ValueError):
            FeedbackLabService(stand=self.stand, journal=self.journal,
                               model_config=config, run_id=RUN,
                               code_revision=SHA)

    def test_http_host_origin_csrf_and_loopback(self):
        service = self.service(lambda s, q, *, draft_provider: outcome(q))
        server = FeedbackLabHTTPServer(0, service)
        self.addCleanup(server.server_close)
        self.assertEqual(server.server_address[0], "127.0.0.1")
        port = server.server_address[1]
        th = Thread(target=server.serve_forever, daemon=True)
        th.start()
        self.addCleanup(lambda: (server.shutdown(), th.join(timeout=2)))

        def request(method, path, body=None, headers=None):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            raw = response.read()
            status = response.status
            conn.close()
            return status, raw

        status, raw = request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"csrf-token", raw)
        status, _ = request("GET", "/", headers={"Host": "evil.invalid"})
        self.assertEqual(status, 403)
        payload = json.dumps({"question": "Как работает?"}).encode()
        base = {"Content-Type": "application/json"}
        status, _ = request("POST", "/api/ask", payload, base)
        self.assertEqual(status, 403)
        headers = dict(base, Origin="http://evil.invalid",
                       **{"X-Lab-CSRF": server.csrf_token})
        status, _ = request("POST", "/api/ask", payload, headers)
        self.assertEqual(status, 403)
        headers["Origin"] = server.lab_origin
        status, raw = request("POST", "/api/ask", payload, headers)
        self.assertEqual(status, 200, raw)
        item = json.loads(raw)["entry"]
        self.assertEqual(item["review_status"], "unreviewed")
        request_id = item["request"]["request_id"]
        status, raw = request("POST", "/api/reviews/" + request_id,
                              json.dumps({"expert": "E", "comment": ""}).encode(), headers)
        self.assertEqual(status, 200, raw)
        self.assertEqual(json.loads(raw)["entry"]["review_status"], "accepted")
        status, raw = request("GET", "/api/export?format=json")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)[0]["reviews"][0]["decision"], "accepted")
        status, _ = request("GET", "/api/entries?status=commented")
        self.assertEqual(status, 200)
        # Interface only listens on 127.0.0.1, not another 127.x loopback
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            self.assertNotEqual(sock.connect_ex(("127.0.0.2", port)), 0)

    def test_no_database_dependency(self):
        from saturn_ai import feedback_journal, feedback_lab
        for mod in (feedback_journal, feedback_lab):
            content = Path(mod.__file__).read_text()
            self.assertNotIn("import sqlite3", content)
            self.assertNotIn("import psycopg", content)
            self.assertNotIn("import redis", content)
            self.assertNotIn("sqlalchemy", content)


if __name__ == "__main__":
    unittest.main()
