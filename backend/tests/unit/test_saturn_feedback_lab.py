"""Stage 5J offline tests: no source/network/model downloads and no DB."""
from concurrent.futures import ThreadPoolExecutor
import csv
from io import StringIO
import http.client
import json
from pathlib import Path
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
        self.assertIn("'+CMD", csv_rows[0]["reviews"])
        self.assertEqual(_csv_safe("\t=1"), "'\t=1")
        self.assertEqual(_csv_safe("-12"), "'-12")

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
