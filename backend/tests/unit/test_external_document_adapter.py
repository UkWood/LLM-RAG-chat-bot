"""Offline contract, revision, provenance and worker tests for stage 3B."""
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from saturn_ai.ingestion.external_document_adapter import (
    CatalogValidationError, adapt_external_documents,
)
from saturn_ai.ingestion.external_document_extractor import (
    ExtractedPdf, SubprocessPdfExtractor, _run_worker_bounded, _parse_worker_reply,
)
from saturn_ai.ingestion.external_document_transport import (
    DocumentError, DocumentFetchPolicy,
)
from saturn_ai.ingestion.saturn_site_adapter import (
    PinnedSiteSnapshot, adapt_snapshot, git_blob_sha1,
)
from saturn_ai.ingestion.support_catalog_adapter import adapt_support_catalog
from unit.test_support_catalog_adapter import catalog, source, PRODUCT, SECOND, SYSTEM
from unit.test_pdf import make_pdf


URL = "https://www.mnppsaturn.ru/ftp/guide.pdf"
PDF = make_pdf(("Synthetic page one", "Physical page two"))


def policy(**kwargs):
    return replace(DocumentFetchPolicy(
        allowed_hosts=("www.mnppsaturn.ru",),
        allowed_path_prefixes=("/ftp", "/public", "/photos"),
    ), **kwargs)


def sample(*, two=False, owners=False):
    if owners:
        block = 'documents:\n  - {title: Manual, kind: manual, url: /ftp/guide.pdf}\n'
        return catalog({PRODUCT: source(fields=block), SECOND: source("Other", fields=block)})
    body = "[Guide](/ftp/guide.pdf)"
    if two:
        body += "\n[Another](/ftp/another.pdf)"
    return catalog({PRODUCT: source(body=body)})


class MemoryTransport:
    def __init__(self, raw=PDF, failure=None):
        self.raw = raw
        self.failure = failure
        self.calls = []

    def fetch(self, url, config):
        self.calls.append(url)
        if self.failure:
            raise DocumentError(self.failure)
        return self.raw[url] if type(self.raw) is dict else self.raw


class MemoryExtractor:
    def __init__(self, pages=((1, "First"), (2, "Second")), failure=None):
        self.pages = pages
        self.failure = failure
        self.calls = 0

    def extract(self, raw, config):
        self.calls += 1
        if self.failure:
            raise DocumentError(self.failure)
        return ExtractedPdf(len(self.pages), self.pages)


class ExternalAdapterTests(unittest.TestCase):
    def test_clean_happy_path_and_physical_pages(self):
        result = adapt_external_documents(sample(), policy(), transport=MemoryTransport(),
                                          extractor=MemoryExtractor())
        self.assertTrue(result.ready_for_promotion)
        self.assertEqual(result.statuses[0].status, "extracted")
        self.assertEqual([e.page_number for e in result.evidence], [1, 2])
        self.assertEqual([e.text for e in result.evidence], ["First", "Second"])
        revision = result.revisions[0]
        self.assertEqual(revision.bytes_sha256, sha256(PDF).hexdigest())
        self.assertEqual(result.evidence[0].source_revision_id, result.statuses[0].revision_id)
        self.assertEqual(result.evidence[0].locator, URL + "#page=1")
        self.assertEqual(result.associations[0].document_id, revision.document_id)
        self.assertEqual(len(result.associations[0].source_revision_ids), 1)
        with self.assertRaises(FrozenInstanceError):
            result.revisions[0].bytes_sha256 = "a" * 64

    def test_partial_text_and_no_invented_empty_page(self):
        result = adapt_external_documents(sample(), policy(), transport=MemoryTransport(),
                                          extractor=MemoryExtractor(((1, "Text"), (2, ""))))
        self.assertFalse(result.complete)
        self.assertEqual(result.statuses[0].status, "partial_text")
        self.assertEqual([e.page_number for e in result.evidence], [1])
        self.assertEqual(result.revisions[0].page_count, 2)
        self.assertEqual(result.diagnostics[0].code, "ocr_required")

    def test_image_only_metadata_stays_available(self):
        result = adapt_external_documents(sample(), policy(), transport=MemoryTransport(),
                                          extractor=MemoryExtractor(((1, ""), (2, ""))))
        self.assertEqual(result.statuses[0].status, "ocr_required")
        self.assertEqual(result.revisions[0].extraction_state, "fetched")
        self.assertEqual(result.revisions[0].page_count, 2)
        self.assertEqual(result.evidence, ())
        self.assertFalse(result.ready_for_promotion)

    def test_fetch_failure_no_forged_hash_or_evidence(self):
        result = adapt_external_documents(sample(), policy(),
                    transport=MemoryTransport(failure="network_error"), extractor=MemoryExtractor())
        self.assertEqual(result.revisions, ())
        self.assertEqual(result.evidence, ())
        self.assertEqual(result.statuses[0].revision_id, None)
        self.assertEqual(result.associations[0].source_locators,
                         sample().pdf_candidates[0].source_locators)

    def test_extraction_failure_has_failed_revision_not_previous_text(self):
        ok = adapt_external_documents(sample(), policy(), transport=MemoryTransport(),
                                      extractor=MemoryExtractor())
        changed = b"%PDF-" + PDF[5:] + b"\n% changed"
        failure = adapt_external_documents(
            sample(), policy(), transport=MemoryTransport(changed),
            extractor=MemoryExtractor(failure="parser_error"),
            previous_cache=ok.cached_extractions,
        )
        self.assertEqual(failure.statuses[0].status, "parser_error")
        self.assertNotEqual(failure.statuses[0].revision_id, ok.statuses[0].revision_id)
        self.assertEqual(failure.revisions[0].extraction_state, "failed")
        self.assertEqual(failure.evidence, ())
        self.assertEqual(failure.cached_extractions, ())

    def test_identical_bytes_reuse_vs_modified_bytes(self):
        first_extractor = MemoryExtractor()
        first = adapt_external_documents(sample(), policy(), transport=MemoryTransport(),
                                         extractor=first_extractor)
        second_extractor = MemoryExtractor(failure="parser_error")
        second = adapt_external_documents(sample(), policy(), transport=MemoryTransport(),
                                          extractor=second_extractor,
                                          previous_cache=first.cached_extractions)
        self.assertEqual(second_extractor.calls, 0)
        self.assertEqual(second.evidence, first.evidence)
        self.assertEqual(second.revisions, first.revisions)
        changed = b"%PDF-" + PDF[5:] + b"\nchanged"
        fresh = adapt_external_documents(sample(), policy(), transport=MemoryTransport(changed),
                                         extractor=MemoryExtractor(),
                                         previous_cache=first.cached_extractions)
        self.assertNotEqual(fresh.statuses[0].revision_id, first.statuses[0].revision_id)

    def test_changed_parser_version_reextracts(self):
        first = adapt_external_documents(sample(), policy(), transport=MemoryTransport(),
                                         extractor=MemoryExtractor())
        parser = MemoryExtractor()
        updated = adapt_external_documents(sample(), policy(), transport=MemoryTransport(),
                                           extractor=parser, parser_version="next-parser/2",
                                           previous_cache=first.cached_extractions)
        self.assertEqual(parser.calls, 1)
        self.assertNotEqual(updated.evidence[0].source_revision_id,
                            first.evidence[0].source_revision_id)

    def test_bad_cached_text_is_not_trusted(self):
        first = adapt_external_documents(sample(), policy(), transport=MemoryTransport(),
                                         extractor=MemoryExtractor())
        tampered = replace(first.cached_extractions[0],
                           extraction=ExtractedPdf(2, ((1, "tampered"), (2, "Second"))))
        parser = MemoryExtractor()
        adapt_external_documents(sample(), policy(), transport=MemoryTransport(),
                                 extractor=parser, previous_cache=(tampered,))
        self.assertEqual(parser.calls, 1)

    def test_owner_updates_do_not_change_revision_identity(self):
        single = adapt_external_documents(sample(), policy(), transport=MemoryTransport(),
                                          extractor=MemoryExtractor())
        many = adapt_external_documents(sample(owners=True), policy(),
                                        transport=MemoryTransport(), extractor=MemoryExtractor(),
                                        previous_cache=single.cached_extractions)
        self.assertEqual(single.statuses[0].revision_id, many.statuses[0].revision_id)
        self.assertEqual(len(many.associations[0].owner_entity_ids), 2)
        self.assertEqual(len(many.associations[0].source_locators), 2)
        removed = adapt_external_documents(sample(), policy(), transport=MemoryTransport(),
                                           extractor=MemoryExtractor(),
                                           previous_cache=many.cached_extractions)
        self.assertEqual(len(removed.associations[0].owner_entity_ids), 1)

    def test_removed_document_not_in_next_active_result(self):
        old = adapt_external_documents(sample(), policy(), transport=MemoryTransport(),
                                       extractor=MemoryExtractor())
        no_doc = catalog({PRODUCT: source(body="No linked documents")})
        result = adapt_external_documents(no_doc, policy(), transport=MemoryTransport(),
                                          extractor=MemoryExtractor(),
                                          previous_cache=old.cached_extractions)
        self.assertEqual(result.evidence, ())
        self.assertEqual(result.revisions, ())
        self.assertEqual(result.associations, ())
        self.assertTrue(result.complete)

    def test_policy_denial_does_not_fetch(self):
        t = MemoryTransport()
        result = adapt_external_documents(sample(), replace(policy(), allowed_hosts=()),
                                          transport=t, extractor=MemoryExtractor())
        self.assertEqual(t.calls, [])
        self.assertEqual(result.statuses[0].status, "policy_denied")

    def test_all_catalog_checks_precede_any_fetch(self):
        from dataclasses import replace
        good = sample(two=True)
        t = MemoryTransport()
        damaged = replace(good, pdf_candidates=(
            good.pdf_candidates[0],
            replace(good.pdf_candidates[1], source_locators=("forged-locator",)),
        ))
        with self.assertRaises(CatalogValidationError):
            adapt_external_documents(damaged, policy(), transport=t, extractor=MemoryExtractor())
        self.assertEqual(t.calls, [])
        with self.assertRaises(CatalogValidationError):
            adapt_external_documents(replace(good, upstream_ready=False),
                                     policy(), transport=t, extractor=MemoryExtractor())
        self.assertEqual(t.calls, [])

    def test_budget_blocks_all_network_activity(self):
        t = MemoryTransport()
        with self.assertRaises(CatalogValidationError):
            adapt_external_documents(sample(two=True), replace(policy(), max_requests=1),
                                     transport=t, extractor=MemoryExtractor())
        self.assertEqual(t.calls, [])

    def test_mock_malformed_extractions_rejected_fail_closed(self):
        for pages in [((2, "fake"),), ((1, "a"), (1, "b")),
                      ((1, " \n "),), ((1, "\x00"),)]:
            with self.subTest(pages=pages):
                result = adapt_external_documents(sample(), policy(),
                    transport=MemoryTransport(), extractor=MemoryExtractor(pages))
                self.assertEqual(result.statuses[0].status, "parser_error")
                self.assertFalse(result.evidence)

    def test_page_and_text_limits_fail_without_evidence(self):
        for p in (replace(policy(), max_pages=1),
                  replace(policy(), max_page_text_bytes=1),
                  replace(policy(), max_text_bytes=1)):
            with self.subTest(p=p):
                result = adapt_external_documents(sample(), p, transport=MemoryTransport(),
                                                  extractor=MemoryExtractor())
                self.assertEqual(result.evidence, ())
                self.assertEqual(result.statuses[0].status, "parser_error" if p.max_pages == 1 else "resource_limit")

    def test_reproducible_two_documents_and_no_mixed_state(self):
        cat = sample(two=True)
        transport = MemoryTransport()
        a = adapt_external_documents(cat, policy(), transport=transport,
                                     extractor=MemoryExtractor())
        b = adapt_external_documents(cat, policy(), transport=MemoryTransport(),
                                     extractor=MemoryExtractor())
        self.assertEqual(a, b)
        self.assertEqual(len(a.statuses), 2)
        self.assertEqual(set(transport.calls), {URL,
                    "https://www.mnppsaturn.ru/ftp/another.pdf"})

    def test_real_read_only_site_fixtures_with_synthetic_bytes(self):
        root = Path(__file__).resolve().parents[1] / "fixtures" / "saturn_support_real"
        files = {}
        for path in root.rglob("*"):
            if path.is_file() and path.name != "README.md":
                rel = path.relative_to(root).as_posix()
                raw = path.read_bytes()
                files[rel] = (git_blob_sha1(raw), raw)
        pinned = PinnedSiteSnapshot.from_mapping(
            commit_sha="084d759487bfab6e111549c9b5469711ac5fc13e",
            tree_sha="a5297822bf3a5e071b10cc1dca553481c1b84d47",
            files=files,
        )
        support = adapt_support_catalog(adapt_snapshot(pinned))
        self.assertTrue(support.ready_for_promotion)
        self.assertEqual(len(support.pdf_candidates), 8)
        t = MemoryTransport()
        result = adapt_external_documents(support, policy(), transport=t,
                                          extractor=MemoryExtractor(((1, "Synthetic test only"),)))
        self.assertEqual(len(result.associations), 8)
        self.assertEqual(len(result.statuses), 8)
        self.assertTrue(all(s.status in ("extracted", "policy_denied") for s in result.statuses))
        self.assertEqual(len(t.calls), sum(s.status == "extracted" for s in result.statuses))
        self.assertTrue(all(e.source_revision_id in
                            {s.revision_id for s in result.statuses} for e in result.evidence))
        # No actual Saturn PDF bytes are included or downloaded by this test.


class ExternalWorkerTests(unittest.TestCase):
    def test_real_development_worker_pages(self):
        raw = make_pdf(("one", "two"))
        got = SubprocessPdfExtractor(enable_development_worker=True).extract(raw, policy())
        self.assertEqual(got.pages, ((1, "one"), (2, "two")))

    def test_default_worker_not_a_production_sandbox(self):
        with self.assertRaises(DocumentError) as context:
            SubprocessPdfExtractor().extract(PDF, policy())
        self.assertEqual(context.exception.code, "policy_denied")

    def test_image_only_and_partial_pdf(self):
        blank = make_pdf(("",))
        parser = SubprocessPdfExtractor(enable_development_worker=True)
        self.assertEqual(parser.extract(blank, policy()).pages, ((1, ""),))
        partial = make_pdf(("page 1", ""))
        self.assertEqual(parser.extract(partial, policy()).pages, ((1, "page 1"), (2, "")))

    def test_bad_encrypted_page_size_and_corrupt_but_inert_navigation(self):
        parser = SubprocessPdfExtractor(enable_development_worker=True)
        # Root /OpenAction is navigation metadata, not an executable RAG input.
        self.assertEqual(parser.extract(make_pdf(("ok",), active=True), policy()).pages,
                         ((1, "ok"),))
        cases = [
            (make_pdf(("ok",), encrypted=True), "encrypted_pdf", policy()),
            (PDF, "page_limit", replace(policy(), max_pages=1)),
            (b"%PDF-corrupt", "parser_error", policy()),
            (PDF, "resource_limit", replace(policy(), max_page_text_bytes=1)),
        ]
        for raw, expected, p in cases:
            with self.subTest(expected=expected):
                with self.assertRaises(DocumentError) as context:
                    parser.extract(raw, p)
                self.assertEqual(context.exception.code, expected)

    def _script_worker(self, script, config=None):
        """Use a real isolated test process, never a network request."""
        cmd = [sys.executable, "-u", "-c", script]
        return _run_worker_bounded(cmd, PDF, config or policy())

    def test_cr01_stdout_over_limit_is_resource_limit_and_worker_reaped(self):
        config = replace(policy(), max_text_bytes=32, max_pages=1)
        processes = []
        original = subprocess.Popen

        def capture(*args, **kwargs):
            child = original(*args, **kwargs)
            processes.append(child)
            return child

        script = ("import sys,time\n"
                  "while True:\n"
                  " sys.stdout.buffer.write(b'X'*65536)\n"
                  " sys.stdout.flush()\n"
                  " time.sleep(.001)\n")
        with patch("saturn_ai.ingestion.external_document_extractor.subprocess.Popen",
                   side_effect=capture):
            with self.assertRaises(DocumentError) as caught:
                self._script_worker(script, config)
        self.assertEqual(caught.exception.code, "resource_limit")
        self.assertEqual(len(processes), 1)
        self.assertIsNotNone(processes[0].returncode)
        self.assertIsNotNone(processes[0].poll())
        self.assertNotEqual(processes[0].returncode, 0)

    def test_cr01_large_stderr_is_discarded_without_deadlock(self):
        script = (
            "import json,sys\n"
            "sys.stderr.buffer.write(b'private-PDF-worker-error'*30000)\n"
            "sys.stderr.flush()\n"
            "print(json.dumps({'page_count':1,'pages':[{'number':1,'text':'ok'}]}))\n"
        )
        returncode, output = self._script_worker(
            script, replace(policy(), max_text_bytes=256, max_pages=1))
        self.assertEqual(returncode, 0)
        self.assertNotIn(b"private-PDF-worker-error", output)
        self.assertEqual(_parse_worker_reply(returncode, output)["page_count"], 1)

    def test_cr01_overflow_fail_closed_no_pdf_evidence_or_successful_revision(self):
        with patch("saturn_ai.ingestion.external_document_extractor._run_worker_bounded",
                   side_effect=DocumentError("resource_limit")):
            result = adapt_external_documents(
                sample(), policy(), transport=MemoryTransport(),
                extractor=SubprocessPdfExtractor(enable_development_worker=True))
        self.assertEqual(result.statuses[0].status, "resource_limit")
        self.assertEqual(result.diagnostics[0].code, "resource_limit")
        self.assertEqual(result.revisions[0].bytes_sha256, sha256(PDF).hexdigest())
        self.assertEqual(result.revisions[0].extraction_state, "failed")
        self.assertEqual(result.evidence, ())
        self.assertEqual(result.cached_extractions, ())
        self.assertFalse(result.ready_for_promotion)

    def test_cr02_signal_minus_nine_empty_stdout_resource_limit(self):
        ret, out = self._script_worker(
            "import os,signal; os.kill(os.getpid(), signal.SIGKILL)")
        self.assertEqual(ret, -9)
        self.assertEqual(out, b"")
        with self.assertRaises(DocumentError) as caught:
            _parse_worker_reply(ret, out)
        self.assertEqual(caught.exception.code, "resource_limit")

    def test_cr02_signal_with_invalid_json_prioritizes_resource_limit(self):
        ret, out = self._script_worker(
            "import os,signal,sys\n"
            "sys.stdout.write('broken'); sys.stdout.flush()\n"
            "os.kill(os.getpid(), signal.SIGKILL)")
        self.assertEqual(ret, -9)
        with self.assertRaises(DocumentError) as caught:
            _parse_worker_reply(ret, out)
        self.assertEqual(caught.exception.code, "resource_limit")

    def test_cr02_success_invalid_json_is_parser_error(self):
        ret, out = self._script_worker("print('not valid json')")
        self.assertEqual(ret, 0)
        with self.assertRaises(DocumentError) as caught:
            _parse_worker_reply(ret, out)
        self.assertEqual(caught.exception.code, "parser_error")

    def test_cr02_structured_nonzero_error_response(self):
        ret, out = self._script_worker(
            "import sys; print('{\"error\":\"encrypted_pdf\"}'); sys.exit(2)")
        self.assertEqual(ret, 2)
        with self.assertRaises(DocumentError) as caught:
            _parse_worker_reply(ret, out)
        self.assertEqual(caught.exception.code, "encrypted_pdf")
        for broken in (b"nonsense", b'{"error": []}'):
            with self.assertRaises(DocumentError) as caught:
                _parse_worker_reply(2, broken)
            self.assertEqual(caught.exception.code, "parser_error")

    def test_cr02_timeout_kills_and_reaps_worker(self):
        config = replace(policy(), worker_wall_seconds=1)
        processes = []
        original = subprocess.Popen

        def capture(*args, **kwargs):
            child = original(*args, **kwargs)
            processes.append(child)
            return child

        with patch("saturn_ai.ingestion.external_document_extractor.subprocess.Popen",
                   side_effect=capture):
            with self.assertRaises(DocumentError) as caught:
                self._script_worker("import time; time.sleep(5)", config)
        self.assertEqual(caught.exception.code, "timeout")
        self.assertEqual(len(processes), 1)
        self.assertIsNotNone(processes[0].poll())

    def test_cr02_valid_json_response_unchanged(self):
        ret, out = self._script_worker(
            "import json; print(json.dumps({'page_count':1,'pages':[{'number':1,'text':'ok'}]}))")
        self.assertEqual(ret, 0)
        self.assertEqual(_parse_worker_reply(ret, out),
                         {"page_count": 1, "pages": [{"number": 1, "text": "ok"}]})
        parsed = SubprocessPdfExtractor(enable_development_worker=True).extract(
            make_pdf(("real page text",)), policy())
        self.assertEqual(parsed.pages, ((1, "real page text"),))
