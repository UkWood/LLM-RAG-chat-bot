"""Adversarial Stage 5E cases against public Saturn end-to-end answer results.

These deliberately damage result objects AFTER the genuine runtime returns.
The evaluator must detect wrong provenance, unsafe additional content,
partial-without-unresolved, stage-specific failures and blind overwrite attempts.
"""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from saturn_ai.evaluation.saturn_answer_dataset import validate_gold, serialize_gold
from saturn_ai.evaluation.saturn_answer_freeze import (
    BlindIntegrityError, BlindRun, freeze_manifest,
)
from saturn_ai.evaluation.saturn_answer_reporting import breakdown, calculate_metrics
from saturn_ai.evaluation.saturn_answer_scoring import SaturnStageTrace, score_answer
from saturn_ai.evaluation.saturn_fixture import fixture_snapshot, calibration_gold_bytes
from saturn_ai.evaluation.saturn_grounding import (
    _run_question, SaturnEvaluationProfile,
)
from saturn_ai.grounding.saturn_answer_assembly import SaturnAnswerAssemblyService
from saturn_ai.grounding.saturn_answer_renderer import render_answer
from saturn_ai.grounding.saturn_claim_provider import SaturnFakeClaimProvider
from saturn_ai.grounding.saturn_generation import SaturnClaimVerificationService
from saturn_ai.grounding.saturn_sufficiency_gate import SaturnQuestionGate
from saturn_ai.retrieval.saturn_channel import SaturnRetrievalService, build_saturn_retrieval_bundle


class SaturnGroundingAdversarialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = fixture_snapshot()
        cls.raw = calibration_gold_bytes(cls.snapshot)
        cls.dataset = validate_gold(cls.raw, cls.snapshot)
        cls.profile = SaturnEvaluationProfile("synthetic_calibration")
        cls.service = SaturnRetrievalService()
        cls.service.publish(build_saturn_retrieval_bundle(cls.snapshot))
        cls.gate = SaturnQuestionGate()
        cls.verifier = SaturnClaimVerificationService(provider=SaturnFakeClaimProvider())
        cls.assembly = SaturnAnswerAssemblyService(verifier=cls.verifier)

    @classmethod
    def gold(cls, case_id):
        return next(c for c in cls.dataset.cases if c.case_id == case_id)

    @classmethod
    def ask(cls, case_id):
        return _run_question(
            cls.service, cls.assembly, cls.gate, cls.verifier,
            cls.gold(case_id).question, cls.profile)

    @classmethod
    def score(cls, case_id, result, trace=None, *, rebind_question=False):
        if rebind_question:
            # Hypothetical forged answer for this case; the scorer must check
            # substantive policy/errors independently from question-hash guard.
            result = replace(result, question_sha256=sha256(
                cls.gold(case_id).question.encode("utf-8")).hexdigest())
        return score_answer(cls.gold(case_id), result, cls.snapshot, trace)

    def test_t58_wrong_field_unit_changes_assertion(self):
        answer, trace = self.ask("C03")
        s = answer.statements[0]
        bad = replace(s, text=s.text.replace("[unit: kg]", "[unit: V]"))
        out = self.score("C03", replace(answer, statements=(bad,),
                                         answer_text=bad.text), trace)
        self.assertFalse(out.fully_correct)
        self.assertEqual(out.unsupported_claim_count, 1)

    def test_t59_wrong_qualifier_injected(self):
        answer, trace = self.ask("C03")
        s = answer.statements[0]
        bad = replace(s, text=s.text[:-1] + ' [qualifiers: {"mode":"fake"}].')
        out = self.score("C03", replace(answer, statements=(bad,),
                                         answer_text=bad.text), trace)
        self.assertFalse(out.fully_correct)

    def test_t60_extra_supported_but_unrequested_fact_not_full(self):
        a, trace = self.ask("C01")
        extra, _ = self.ask("C02")
        forged = replace(
            a, statements=a.statements + extra.statements,
            citations=a.citations + extra.citations,
            answer_text=a.answer_text + "\n" + extra.answer_text)
        out = self.score("C01", forged, trace)
        self.assertFalse(out.fully_correct)
        self.assertIn("unexpected_claim", out.failure_codes)

    def test_t61_orphan_citation_rejected(self):
        a, trace = self.ask("C01")
        extra, _ = self.ask("C02")
        forged = replace(a, citations=a.citations + extra.citations)
        out = self.score("C01", forged, trace)
        self.assertFalse(out.fully_correct)
        self.assertIn("citation_error", out.failure_codes)

    def test_t62_real_pdf_quote_integrity_non_entailing(self):
        a, trace = self.ask("C26")
        self.assertEqual(a.status, "needs_support")
        self.assertTrue(all(s.statement_kind == "source_quote" for s in a.statements))
        out = self.score("C26", a, trace)
        self.assertTrue(out.citation_valid)
        self.assertEqual(out.supported_fact_count, 0)

    def test_t63_pdf_physical_page_tampering(self):
        a, trace = self.ask("C26")
        self.assertTrue(a.citations)
        bad = replace(a.citations[0], physical_page=2000)
        out = self.score("C26", replace(a, citations=(bad,)), trace)
        self.assertFalse(out.citation_valid)
        self.assertFalse(out.fully_correct)

    def test_t64_pdf_parser_version_tampering(self):
        a, trace = self.ask("C26")
        bad = replace(a.citations[0], pdf_parser_version="forged/1")
        self.assertFalse(self.score(
            "C26", replace(a, citations=(bad,)), trace).citation_valid)

    def test_t65_pdf_bytes_sha_tampering(self):
        a, trace = self.ask("C26")
        bad = replace(a.citations[0], pdf_bytes_sha256="f"*64)
        self.assertFalse(self.score(
            "C26", replace(a, citations=(bad,)), trace).citation_valid)

    def test_t66_multi_owner_provenance_integrity(self):
        a, trace = self.ask("C15")
        self.assertGreaterEqual(len(a.citations[0].owner_entity_ids), 2)
        bad = replace(a.citations[0], owner_entity_ids=())
        out = self.score("C15", replace(a, citations=(bad,)), trace)
        self.assertFalse(out.citation_valid)
        self.assertFalse(out.fully_correct)

    def test_t67_false_partial_without_unresolved_need(self):
        a, trace = self.ask("C20")
        self.assertEqual(a.status, "partial")
        bad = replace(a, unresolved_need_ids=())
        out = self.score("C20", bad, trace)
        self.assertFalse(out.fully_correct)

    def test_t68_unsafe_negative_answer(self):
        positive, trace = self.ask("C01")
        out = self.score("C18", positive, trace, rebind_question=True)
        self.assertFalse(out.fully_correct)
        self.assertIn("sufficiency_false_positive", out.failure_codes)

    def test_t69_extra_answer_text_counted_unsafe(self):
        a, trace = self.ask("C01")
        out = self.score("C01", replace(a, answer_text=a.answer_text+
                         "\nInvented Ethernet capability."), trace)
        self.assertFalse(out.fully_correct)
        self.assertEqual(out.extra_answer_text_count, 1)
        self.assertEqual(out.source_unsupported_claim_count, 0)

    def test_t70_observed_retrieval_miss_attribution(self):
        a, _ = self.ask("C18")
        out = self.score("C01", a, SaturnStageTrace(
            retrieval_diagnostics_complete=True), rebind_question=True)
        self.assertIn("retrieval_miss", out.failure_codes)

    def test_t71_parser_failure_after_source_hit(self):
        a, _ = self.ask("C18")
        eid = self.gold("C01").required[0].evidence_id
        trace = SaturnStageTrace(ranked_evidence_ids=(eid,),
                                 selected_evidence_ids=(eid,))
        out = self.score("C01", a, trace, rebind_question=True)
        self.assertIn("question_parse_failure", out.failure_codes)

    def test_t72_gate_false_negative_after_parse(self):
        a, _ = self.ask("C18")
        eid = self.gold("C01").required[0].evidence_id
        trace = SaturnStageTrace(ranked_evidence_ids=(eid,),
                                 selected_evidence_ids=(eid,),
                                 parsed_need_kinds=("field_value",),
                                 finding_statuses=("missing_in_context",))
        out = self.score("C01", a, trace, rebind_question=True)
        self.assertIn("sufficiency_false_negative", out.failure_codes)

    def test_t73_claim_generation_missing_after_sufficiency(self):
        a, _ = self.ask("C18")
        eid = self.gold("C01").required[0].evidence_id
        trace = SaturnStageTrace(ranked_evidence_ids=(eid,),
                                 selected_evidence_ids=(eid,),
                                 parsed_need_kinds=("field_value",),
                                 finding_statuses=("covered_structured",))
        self.assertIn("claim_generation_missing",
                      self.score("C01", a, trace, rebind_question=True).failure_codes)

    def test_t74_assembly_missing_after_verified_fact(self):
        a, _ = self.ask("C18")
        eid = self.gold("C01").required[0].evidence_id
        trace = SaturnStageTrace(ranked_evidence_ids=(eid,),
                                 selected_evidence_ids=(eid,),
                                 parsed_need_kinds=("field_value",),
                                 finding_statuses=("covered_structured",),
                                 verified_evidence_ids=(eid,))
        self.assertIn("answer_assembly_missing",
                      self.score("C01", a, trace, rebind_question=True).failure_codes)

    def test_t75_technical_failure_not_evidence_miss(self):
        a, _ = self.ask("C18")
        out = self.score("C01", a, SaturnStageTrace(technical_failure=True))
        self.assertIn("technical_failure", out.failure_codes)

    def test_t76_false_partial_on_positive_gold(self):
        partial, trace = self.ask("C20")
        out = self.score("C11", partial, trace, rebind_question=True)
        self.assertIn("false_refusal", out.failure_codes)

    def test_t77_source_channel_breakdown(self):
        items = (self.score("C01", *self.ask("C01")),
                 self.score("C15", *self.ask("C15")))
        groups = breakdown(items)
        self.assertEqual(groups["source_channel"]["site"]["case_count"], 1)
        self.assertEqual(
            groups["source_channel"]["document_metadata"]["case_count"], 1)

    def test_t78_complete_receipt_written_and_reuse_fails(self):
        with TemporaryDirectory() as tmp:
            freeze = freeze_manifest(
                experiment_id="completion-proof", code_revision="a"*40,
                dataset_sha256=sha256(self.raw).hexdigest(),
                snapshot=self.snapshot, case_count=28,
                case_ids=tuple(x.case_id for x in self.dataset.cases))
            b = BlindRun(freeze=freeze, receipts_dir=Path(tmp)/"receipts",
                         report_path=Path(tmp)/"result.json")
            b.start()
            # Former implementation accepted an arbitrary JSON object; this
            # is now explicitly rejected and cannot create COMPLETE.
            with self.assertRaises(BlindIntegrityError):
                b.complete(b'{"x":1}\n')
            self.assertFalse(b.complete_path.exists())
            self.assertFalse(b.report_path.exists())
            with self.assertRaises(BlindIntegrityError):
                BlindRun(freeze=freeze, receipts_dir=Path(tmp)/"receipts",
                         report_path=Path(tmp)/"result.json").start()

    def test_t79_real_pdf_gold_page_and_exact_quote_accepted_in_negative(self):
        pdf = next(p for p in self.snapshot.answer_evidence
                   if p.evidence_type == "pdf_passage")
        raw = json.loads(self.raw)
        case = raw["cases"][17]  # negative case C18
        case["required"] = [{
            "requirement_id": "r1", "kind": "pdf_quote",
            "canonical_id": self.snapshot.pdf_revisions[0].document_id,
            "source_revision_id": pdf.source_revision_id,
            "evidence_id": pdf.evidence_id, "physical_page": pdf.page_number,
            "exact_quote": pdf.text[:15],
        }]
        result = validate_gold(serialize_gold(raw), self.snapshot)
        self.assertEqual(result.cases[17].required[0].physical_page, pdf.page_number)

    def test_t80_document_hit_five_ranks_not_ten(self):
        a, trace = self.ask("C15")
        did = self.gold("C15").required[0].canonical_id
        misplaced = replace(trace, ranked_document_ids=(
            "x", "y", "z", "w", "v", did))
        out = self.score("C15", a, misplaced)
        self.assertIs(out.document_hit_at_5, False)

    def test_t81_wrong_relation_direction_detected(self):
        a, trace = self.ask("C13")
        wrong = replace(a.statements[0],
                        text="Heating system — systems — Device X.")
        out = self.score("C13", replace(a, statements=(wrong,),
                          answer_text=wrong.text), trace)
        self.assertFalse(out.fully_correct)
        self.assertEqual(out.unsupported_claim_count, 1)


    def test_t82_wrong_question_hash_not_same_answer(self):
        a, trace = self.ask("C01")
        bad = replace(a, question_sha256="f"*64)
        out = self.score("C01", bad, trace)
        self.assertFalse(out.fully_correct)
        self.assertIn("technical_failure", out.failure_codes)

    def test_t83_negative_cannot_emit_unrequested_valid_document(self):
        doc, trace = self.ask("C15")
        # Deliberately self-consistent final text + source-backed citation.
        # Even if provenance is valid, negative gold forbids this content.
        forged = replace(
            doc, status="needs_support",
            question_sha256=sha256(self.gold("C18").question.encode("utf-8")).hexdigest(),
            answer_text=render_answer("needs_support", doc.statements))
        out = self.score("C18", forged, trace)
        self.assertFalse(out.fully_correct)
        self.assertIn("unexpected_claim", out.failure_codes)


if __name__ == "__main__":
    unittest.main()
