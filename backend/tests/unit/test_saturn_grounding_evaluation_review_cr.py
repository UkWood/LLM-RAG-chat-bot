"""PR #31 consolidated independent-review corrections CR01–CR05.

All blind-like data here is constructed from the PUBLIC OPEN C01/C02
calibration cases in memory; no historical/new hidden blind is opened/run.
"""
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest

from saturn_ai.evaluation.saturn_answer_dataset import (
    validate_gold, serialize_gold,
)
from saturn_ai.evaluation.saturn_answer_freeze import (
    BlindRun, BlindIntegrityError, freeze_manifest, validate_freeze, config_hash,
)
from saturn_ai.evaluation.saturn_answer_reporting import (
    build_report, report_bytes, calculate_metrics, breakdown,
)
from saturn_ai.evaluation.saturn_answer_scoring import (
    SaturnStageTrace, SaturnEvaluationOutcome, score_answer,
    _indexes, _citation_ok, _evaluate_statement,
)
from saturn_ai.evaluation.saturn_fixture import (
    fixture_snapshot, calibration_gold_bytes,
)
from saturn_ai.evaluation.saturn_grounding import (
    SaturnEvaluationProfile, _run_question,
)
from saturn_ai.grounding.saturn_answer_contracts import (
    SaturnAnswerStatement, SaturnCitation,
)
from saturn_ai.grounding.saturn_answer_assembly import SaturnAnswerAssemblyService
from saturn_ai.grounding.saturn_answer_renderer import render_answer
from saturn_ai.grounding.saturn_claim_provider import SaturnFakeClaimProvider
from saturn_ai.grounding.saturn_generation import SaturnClaimVerificationService
from saturn_ai.grounding.saturn_sufficiency_gate import SaturnQuestionGate
from saturn_ai.ingestion.saturn_contracts import stable_id
from saturn_ai.retrieval.saturn_channel import (
    SaturnRetrievalService, SaturnOperationalPolicy,
    SaturnPolicyProvider, build_saturn_retrieval_bundle,
)


class ReviewCorrections(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = fixture_snapshot()
        cls.dataset = validate_gold(calibration_gold_bytes(cls.snapshot), cls.snapshot)
        cls.bundle = build_saturn_retrieval_bundle(cls.snapshot)
        cls.service = SaturnRetrievalService()
        cls.service.publish(cls.bundle)
        cls.verifier = SaturnClaimVerificationService(provider=SaturnFakeClaimProvider())
        cls.assembly = SaturnAnswerAssemblyService(verifier=cls.verifier)
        cls.gate = SaturnQuestionGate()
        cls.profile = SaturnEvaluationProfile("synthetic_calibration")

    @classmethod
    def case(cls, name):
        return next(x for x in cls.dataset.cases if x.case_id == name)

    @classmethod
    def ask(cls, name, *, service=None):
        case = cls.case(name)
        return _run_question(service or cls.service, cls.assembly,
                             cls.gate, cls.verifier, case.question, cls.profile)

    @classmethod
    def score(cls, name, answer, trace):
        return score_answer(cls.case(name), answer, cls.snapshot, trace)

    @staticmethod
    def _for_question(answer, trace, question):
        digest = sha256(question.encode("utf-8")).hexdigest()
        return replace(answer, question_sha256=digest), replace(trace, question_sha256=digest)

    # CR01: need source identity, unresolved invariants, explicit owner scopes
    def test_cr01_t01_one_need_cannot_satisfy_two_distinct_claims(self):
        a, trace = self.ask("C11")
        self.assertEqual(len(a.statements), 2)
        second = a.statements[1]
        bad = replace(second, need_id=a.statements[0].need_id,
                      statement_id=stable_id("saturn-answer-statement-v1",
                                           a.statements[0].need_id,
                                           second.evidence_id, second.document_id,
                                           second.statement_kind,
                                           second.citation_ids[0]))
        outcome = self.score("C11", replace(a, statements=(a.statements[0], bad)), trace)
        self.assertFalse(outcome.fully_correct)
        self.assertIn("need_binding_failure", outcome.failure_codes)

    def test_cr01_t02_answered_with_unresolved_is_not_complete(self):
        a, trace = self.ask("C01")
        out = self.score("C01", replace(a, unresolved_need_ids=(trace.needs[0].need_id,)), trace)
        self.assertFalse(out.fully_correct)
        self.assertIn("unresolved_need_mismatch", out.failure_codes)

    def test_cr01_t03_partial_fake_unresolved_id(self):
        a, trace = self.ask("C20")
        self.assertEqual(a.status, "partial")
        out = self.score("C20", replace(a, unresolved_need_ids=("fake-need-id",)), trace)
        self.assertFalse(out.fully_correct)
        self.assertIn("unresolved_need_mismatch", out.failure_codes)

    def test_cr01_t04_general_document_not_owner_qualified_after_rebinding(self):
        general, _ = self.ask("C15")
        _, qualified_trace = self.ask("C16")
        forged = replace(general, question_sha256=sha256(
            self.case("C16").question.encode("utf-8")).hexdigest())
        out = self.score("C16", forged, qualified_trace)
        self.assertFalse(out.fully_correct)
        self.assertTrue({"need_binding_failure", "owner_scope_mismatch"} &
                        set(out.failure_codes))

    def test_cr01_t05_owner_qualified_document_accepts_only_correct_owner(self):
        a, trace = self.ask("C16")
        case = self.case("C16")
        self.assertIsNotNone(case.required[0].owner_entity_id)
        self.assertEqual(a.citations[0].owner_entity_ids,
                         (case.required[0].owner_entity_id,))
        self.assertTrue(self.score("C16", a, trace).fully_correct)

    def test_cr01_t06_unknown_need_cannot_be_claimed(self):
        a, trace = self.ask("C01")
        s = a.statements[0]
        bad = replace(s, need_id="unknown-need",
                      statement_id=stable_id("saturn-answer-statement-v1",
                                           "unknown-need", s.evidence_id,
                                           s.document_id, s.statement_kind,
                                           s.citation_ids[0]))
        out = self.score("C01", replace(a, statements=(bad,)), trace)
        self.assertFalse(out.fully_correct)
        self.assertIn("need_binding_failure", out.failure_codes)

    def test_cr01_t07_wrong_bundle_identity(self):
        a, trace = self.ask("C01")
        out = self.score("C01", replace(a, bundle_id="f"*64), trace)
        self.assertFalse(out.fully_correct)
        self.assertIn("technical_failure", out.failure_codes)

    def test_cr01_t08_existing_multi_relation_document_positive(self):
        for name in ("C01", "C11", "C12", "C13", "C14", "C15", "C16", "C20"):
            with self.subTest(case=name):
                a, trace = self.ask(name)
                self.assertTrue(self.score(name, a, trace).fully_correct)

    # CR03: quotation is exact substring, NOT engineering entailment
    def _site_passage_citation_and_statement(self):
        unit = next(e for e in self.snapshot.answer_evidence
                    if e.evidence_type == "site_passage" and len(e.text) >= 12
                    and e.entity_id is not None)
        ent = next(e for e in self.snapshot.entities if e.entity_id == unit.entity_id)
        rev = next(r for r in self.snapshot.source_revisions
                   if r.revision_id == unit.source_revision_id)
        ident = stable_id("saturn-answer-citation-v1", "site",
                          unit.evidence_id, rev.revision_id,
                          unit.locator, None, None)
        citation = SaturnCitation(
            ident, "site", rev.revision_id, ent.title,
            ent.canonical_url, unit.locator, evidence_id=unit.evidence_id,
            entity_id=ent.entity_id, source_repository=rev.repository,
            source_branch=rev.branch, source_path=rev.path,
            source_commit_sha=rev.commit_sha, source_blob_sha=rev.blob_sha,
            source_content_sha256=rev.content_sha256)
        quote = unit.text[3:9]
        statement = SaturnAnswerStatement(
            "test-statement", "test-need", "source_quote",
            "Цитата источника (не подтверждает характеристику): " + quote,
            (citation.citation_id,), evidence_id=unit.evidence_id)
        return unit, citation, statement

    def test_cr03_t01_middle_site_passage(self):
        unit, citation, statement = self._site_passage_citation_and_statement()
        self.assertTrue(_citation_ok(citation, self.snapshot, _indexes(self.snapshot)))
        self.assertIn(statement.text.split(": ", 1)[1], unit.text)
        self.assertFalse(unit.text.startswith(statement.text.split(": ", 1)[1]))
        self.assertIsNotNone(_evaluate_statement(
            statement, {citation.citation_id: citation}, _indexes(self.snapshot)))

    def test_cr03_t02_middle_pdf_passage(self):
        a, trace = self.ask("C26")
        unit = next(x for x in self.snapshot.answer_evidence
                    if x.evidence_id == a.statements[0].evidence_id)
        mid = unit.text[5:18]
        self.assertIn(mid, unit.text)
        self.assertFalse(unit.text.startswith(mid))
        changed = replace(a.statements[0],
                          text="Цитата источника (не подтверждает характеристику): " + mid)
        outcome = self.score("C26", replace(a, statements=(changed,)), trace)
        self.assertTrue(outcome.fully_correct)
        self.assertEqual(outcome.supported_fact_count, 0)

    def test_cr03_t03_modified_quote_rejected(self):
        a, trace = self.ask("C26")
        changed = replace(a.statements[0],
                          text="Цитата источника (не подтверждает характеристику): nonexistent altered quote")
        out = self.score("C26", replace(a, statements=(changed,)), trace)
        self.assertFalse(out.fully_correct)
        self.assertIn("unsafe_claim", out.failure_codes)

    def test_cr03_t04_pdf_page_or_revision_substitution(self):
        a, trace = self.ask("C26")
        for change in ({"physical_page": 999},
                       {"pdf_revision_id": "f"*64},
                       {"pdf_parser_version": "forged"}):
            with self.subTest(change=change):
                forged = replace(a.citations[0], **change)
                out = self.score("C26", replace(a, citations=(forged,)), trace)
                self.assertFalse(out.citation_valid)
                self.assertFalse(out.fully_correct)

    def test_cr03_t05_quotes_never_satisfy_technical_gold(self):
        quote, trace = self.ask("C26")
        fake, fake_trace = self._for_question(
            quote, trace, self.case("C01").question)
        out = self.score("C01", fake, fake_trace)
        self.assertEqual(out.supported_fact_count, 0)
        self.assertFalse(out.fully_correct)

    # CR04: same pinned session even when a different bundle is published
    def test_cr04_t01_concurrent_publication_keeps_pinned_diagnostics(self):
        second = build_saturn_retrieval_bundle(
            fixture_snapshot(site_commit="b"*40))
        local = SaturnRetrievalService()
        local.publish(self.bundle)
        original = SaturnRetrievalService._search_captured
        published = []
        def concurrent(self_service, bundle, question, mode, top_k):
            if not published:
                self_service.publish(second)
                published.append(True)
            return original(self_service, bundle, question, mode, top_k)
        with patch.object(SaturnRetrievalService, "_search_captured", concurrent):
            a, trace = self.ask("C01", service=local)
        self.assertTrue(published)
        self.assertEqual(local.capture().snapshot.snapshot_id,
                         second.snapshot.snapshot_id)
        self.assertEqual(a.snapshot_id, self.snapshot.snapshot_id)
        self.assertEqual(trace.snapshot_id, self.snapshot.snapshot_id)
        self.assertEqual(trace.bundle_id, self.bundle.manifest.bundle_id)
        self.assertTrue(self.score("C01", a, trace).fully_correct)

    def test_cr04_t02_stage_trace_same_snapshot_and_bundle(self):
        a, trace = self.ask("C11")
        self.assertEqual((trace.snapshot_id, trace.bundle_id, trace.question_sha256),
                         (a.snapshot_id, a.bundle_id, a.question_sha256))

    def test_cr04_t03_missing_doc_retrieval_attribution(self):
        a, t = self.ask("C23")
        a, t = self._for_question(a, t, self.case("C15").question)
        t = replace(t, ranked_document_ids=(), selected_document_ids=(),
                    retrieval_diagnostics_complete=True)
        out = self.score("C15", a, t)
        self.assertIn("retrieval_miss", out.failure_codes)

    def test_cr04_t04_selected_document_omitted_at_assembly(self):
        a, _ = self.ask("C23")
        _, found_trace = self.ask("C15")
        a = replace(a, question_sha256=sha256(
            self.case("C15").question.encode("utf-8")).hexdigest())
        out = self.score("C15", a, found_trace)
        self.assertIn("answer_assembly_missing", out.failure_codes)
        self.assertNotIn("retrieval_miss", out.failure_codes)

    def test_cr04_t05_missing_observation_is_undetermined(self):
        a, trace = self.ask("C23")
        a, trace = self._for_question(a, trace, self.case("C15").question)
        trace = replace(trace, ranked_document_ids=(), selected_document_ids=(),
                        retrieval_diagnostics_complete=False)
        out = self.score("C15", a, trace)
        self.assertIn("undetermined", out.failure_codes)

    def test_cr04_t06_retrieval_denominators_unchanged(self):
        a, t = self.ask("C01")
        b, u = self.ask("C15")
        metrics = calculate_metrics((
            self.score("C01", a, t), self.score("C15", b, u)))
        self.assertEqual(metrics["source_hit_at_5"]["denominator"], 1)
        self.assertEqual(metrics["document_hit_at_5"]["denominator"], 1)

    # CR05: no semantic conflation of source-unsupported, off-topic and text
    def test_cr05_t01_valid_but_unrequested_fact_counted(self):
        a, t = self.ask("C01")
        extra, _ = self.ask("C02")
        forged = replace(a, statements=a.statements+extra.statements,
                         citations=a.citations+extra.citations,
                         answer_text=a.answer_text+"\n"+extra.answer_text)
        out = self.score("C01", forged, t)
        m = calculate_metrics((out,))
        self.assertFalse(out.fully_correct)
        self.assertEqual(out.off_question_claim_count, 1)
        self.assertEqual(out.source_unsupported_claim_count, 0)
        self.assertEqual(m["off_question_source_backed_claims"]["count"], 1)

    def test_cr05_t02_added_unproven_text_not_claim_denominator(self):
        a, t = self.ask("C01")
        out = self.score("C01", replace(a, answer_text=a.answer_text +
                         "\nInvented capability."), t)
        metrics = calculate_metrics((out,))
        self.assertEqual(out.extra_answer_text_count, 1)
        self.assertEqual(out.source_unsupported_claim_count, 0)
        self.assertEqual(metrics["extra_unsupported_answer_text"]["case_rate"]["denominator"], 1)
        self.assertEqual(metrics["source_unsupported_claims"]["ratio"]["denominator"], 1)

    def test_cr05_t03_source_unsupported_separate_from_off_question(self):
        a, t = self.ask("C01")
        s = replace(a.statements[0], text="Device X — interface: fabricated.")
        forged = replace(a, statements=(s,), answer_text=s.text)
        out = self.score("C01", forged, t)
        self.assertEqual(out.source_unsupported_claim_count, 1)
        self.assertEqual(out.off_question_claim_count, 0)

    def test_cr05_t04_partial_not_grouped_with_negative(self):
        results = [self.score(x, *self.ask(x))
                   for x in ("C01", "C18", "C21", "C20")]
        groups = breakdown(results)["status_group"]
        for group in ("positive", "negative", "clarification", "partial"):
            self.assertEqual(groups[group]["case_count"], 1)
        self.assertEqual(calculate_metrics(results)["negative_correctness"]["denominator"], 2)

    def test_cr05_t05_policy_restriction_observed(self):
        required = self.case("C01").required[0]
        provider = SaturnPolicyProvider(SaturnOperationalPolicy(
            "blocked-for-evaluation", blocked_evidence_ids=frozenset(
                (required.evidence_id,))))
        local = SaturnRetrievalService(policy_provider=provider)
        local.publish(self.bundle)
        a, trace = self.ask("C01", service=local)
        out = self.score("C01", a, trace)
        self.assertTrue(out.policy_restriction)
        self.assertEqual(calculate_metrics((out,))["policy_restriction"]["numerator"], 1)

    def test_cr05_t06_technical_error_not_correct_refusal(self):
        a, t = self.ask("C18")
        bad = replace(a, status="error",
                      answer_text="Не удалось выполнить проверку.")
        out = self.score("C18", bad, replace(t, technical_failure=True))
        self.assertFalse(out.fully_correct)
        self.assertIn("technical_failure", out.failure_codes)
        self.assertEqual(calculate_metrics((out,))["technical_error"]["numerator"], 1)

    def test_cr05_t07_conflict_not_ordinary_missing(self):
        a, t = self.ask("C18")
        a, t = self._for_question(a, t, self.case("C01").question)
        observed = replace(t, ranked_evidence_ids=(
            self.case("C01").required[0].evidence_id,),
            selected_evidence_ids=(self.case("C01").required[0].evidence_id,),
            need_findings=tuple(replace(f, status="potential_conflict")
                                for f in t.need_findings))
        out = self.score("C01", a, observed)
        self.assertTrue(out.evidence_conflict)
        self.assertIn("evidence_conflict", out.failure_codes)
        self.assertNotIn("retrieval_miss", out.failure_codes)
        self.assertEqual(calculate_metrics((out,))["evidence_conflict"]["numerator"], 1)


class BlindReportContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = fixture_snapshot()
        cls.raw = calibration_gold_bytes(cls.snapshot)

    def sample(self, ids=("C01",)):
        # In-memory test data derived from OPEN calibration only; no actual
        # held-out dataset, no blind CLI invocation.
        raw = json.loads(self.raw)
        raw["cases"] = [x for x in raw["cases"] if x["case_id"] in ids]
        for case in raw["cases"]:
            case["split"] = "synthetic_blind"
        raw["split"] = "synthetic_blind"
        raw["dataset_id"] = "test-only-CR02-public-source-cases"
        raw["author"] = "independent-test-author"
        raw["reviewer"] = "independent-test-reviewer"
        dataset_bytes = serialize_gold(raw)
        dataset = validate_gold(dataset_bytes, self.snapshot,
                                split="synthetic_blind")
        bundle = build_saturn_retrieval_bundle(self.snapshot)
        svc = SaturnRetrievalService()
        svc.publish(bundle)
        verifier = SaturnClaimVerificationService(provider=SaturnFakeClaimProvider())
        assembly = SaturnAnswerAssemblyService(verifier=verifier)
        gate = SaturnQuestionGate()
        profile = SaturnEvaluationProfile("synthetic_calibration")
        outcomes = []
        for case in dataset.cases:
            answer, trace = _run_question(svc, assembly, gate, verifier,
                                          case.question, profile)
            outcomes.append(score_answer(case, answer, self.snapshot, trace))
        freeze = freeze_manifest(
            experiment_id="cr02-test-only", code_revision="a"*40,
            dataset_sha256=dataset.sha256, snapshot=self.snapshot,
            case_count=len(dataset.cases),
            case_ids=tuple(x.case_id for x in dataset.cases))
        report = build_report(
            dataset, outcomes, code_revision="a"*40,
            config_hash=config_hash(mode="lexical", top_k=10), bundle=bundle,
            blind_status="RUN", experiment_id=freeze["experiment_id"])
        return freeze, dataset, report, dataset_bytes

    def attempt(self, mutation=None, *, ids=("C01",), valid=False):
        freeze, dataset, report, dataset_bytes = self.sample(ids)
        if mutation:
            mutation(report)
        with TemporaryDirectory() as tmp:
            b = BlindRun(freeze=freeze, receipts_dir=Path(tmp)/"receipts",
                         report_path=Path(tmp)/"report.json")
            b.start()
            if valid:
                b.complete(report_bytes(report), dataset_bytes=dataset_bytes, snapshot=self.snapshot)
                self.assertTrue(b.complete_path.is_file())
                self.assertTrue(b.start_path.is_file())
            else:
                with self.assertRaises(BlindIntegrityError):
                    b.complete(report_bytes(report), dataset_bytes=dataset_bytes, snapshot=self.snapshot)
                self.assertFalse(b.complete_path.exists())
                self.assertFalse(b.report_path.exists())

    def test_cr02_t01_arbitrary_json_rejected(self):
        freeze, dataset, _, dataset_bytes = self.sample()
        with TemporaryDirectory() as tmp:
            b = BlindRun(freeze=freeze, receipts_dir=Path(tmp),
                         report_path=Path(tmp)/"report.json")
            b.start()
            with self.assertRaises(BlindIntegrityError):
                b.complete(b'{"x":1}', dataset_bytes=dataset_bytes, snapshot=self.snapshot)

    def test_cr02_t02_wrong_dataset_hash(self):
        self.attempt(lambda r: r["dataset"].update(sha256="f"*64))

    def test_cr02_t03_wrong_snapshot_or_corpus(self):
        for key in ("snapshot_id", "corpus_hash"):
            with self.subTest(key=key):
                self.attempt(lambda r: r["snapshot"].update({key: "f"*64}))

    def test_cr02_t04_wrong_code_or_config_or_rubric(self):
        for section, key in (("runtime", "code_revision"),
                             ("runtime", "scorer_revision"),
                             ("runtime", "rubric_revision"),
                             ("configuration", "hash")):
            with self.subTest(section=section, key=key):
                self.attempt(lambda r: r[section].update({key: "forged"}))

    def test_cr02_t05_missing_or_duplicate_case_id(self):
        self.attempt(lambda r: r["cases"].pop(), ids=("C01", "C02"))
        self.attempt(lambda r: r["cases"][1].update(
            case_id=r["cases"][0]["case_id"]), ids=("C01", "C02"))

    def test_cr02_t06_unavailable_code_sha_no_freeze(self):
        with self.assertRaises(BlindIntegrityError):
            freeze_manifest(
                experiment_id="no-code", code_revision="unavailable",
                dataset_sha256="f"*64, snapshot=self.snapshot,
                case_count=1, case_ids=("C01",))

    def test_cr02_t07_cannot_validate_freeze_without_git_sha(self):
        freeze, dataset, _, dataset_bytes = self.sample()
        with self.assertRaises(BlindIntegrityError):
            validate_freeze(freeze, code_revision="unavailable",
                            dataset_bytes=b"test", snapshot=self.snapshot,
                            mode="lexical", top_k=10)

    def test_cr02_t07b_unavailable_git_head_cannot_make_start_receipt(self):
        from saturn_ai.evaluation.saturn_grounding import main
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            dataset_path = folder / "unused-public-calibration.json"
            dataset_path.write_bytes(self.raw)
            freeze_path = folder / "freeze.json"
            freeze_path.write_text("{}", encoding="utf-8")
            receipts = folder / "receipts"
            with patch("saturn_ai.evaluation.saturn_grounding._code_revision",
                       return_value="unavailable"):
                with self.assertRaises(SystemExit) as raised:
                    main(["--profile", "blind", "--dataset", str(dataset_path),
                          "--report", str(folder / "report.json"),
                          "--freeze", str(freeze_path),
                          "--receipts-dir", str(receipts)])
            self.assertNotEqual(raised.exception.code, 0)
            self.assertFalse(receipts.exists())

    def test_cr02_t08_valid_first_run_writes_start_and_complete(self):
        self.attempt(valid=True)

    def test_cr02_t09_reuse_and_failure_remain_blocked(self):
        freeze, dataset, report, dataset_bytes = self.sample()
        with TemporaryDirectory() as tmp:
            b = BlindRun(freeze=freeze, receipts_dir=Path(tmp),
                         report_path=Path(tmp)/"r.json")
            b.start()
            b.fail("test_failure")
            with self.assertRaises(BlindIntegrityError):
                b.complete(report_bytes(report), dataset_bytes=dataset_bytes, snapshot=self.snapshot)
            with self.assertRaises(BlindIntegrityError):
                BlindRun(freeze=freeze, receipts_dir=Path(tmp),
                         report_path=Path(tmp)/"r.json").start()

    def test_cr02_t10_no_real_blind_dataset_run(self):
        freeze, dataset, report, dataset_bytes = self.sample()
        self.assertEqual(dataset.dataset_id, "test-only-CR02-public-source-cases")
        self.assertEqual(report["independent_blind_evaluation"], "RUN")
        # 'RUN' is a TEST FIXTURE schema exercise only; it was never recorded
        # as a blind experiment or written into evaluation/experiments.
        self.assertEqual(freeze["expected_case_ids"], ["C01"])


if __name__ == "__main__":
    unittest.main()
