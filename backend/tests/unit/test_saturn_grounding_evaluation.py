"""Stage 5E independent evaluator contract/integration tests.

Positive integration tests exercise actual Saturn 4A->5D APIs. Malformed
SaturnAnswerResult is used ONLY to test scorer resistance to corruption.
"""
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest

from saturn_ai.evaluation.saturn_answer_dataset import (
    GoldValidationError, validate_gold, serialize_gold,
)
from saturn_ai.evaluation.saturn_answer_freeze import (
    BlindIntegrityError, BlindRun, config_hash, freeze_manifest, validate_freeze,
)
from saturn_ai.evaluation.saturn_answer_reporting import (
    calculate_metrics, build_report, report_bytes,
)
from saturn_ai.evaluation.saturn_answer_scoring import (
    SaturnStageTrace, score_answer,
)
from saturn_ai.evaluation.saturn_fixture import (
    CASES, calibration_gold_bytes, fixture_snapshot,
)
from saturn_ai.evaluation.saturn_grounding import (
    SaturnEvaluationProfile, _run_question, evaluate,
)
from saturn_ai.grounding.saturn_answer_assembly import SaturnAnswerAssemblyService
from saturn_ai.grounding.saturn_claim_provider import SaturnFakeClaimProvider
from saturn_ai.grounding.saturn_generation import SaturnClaimVerificationService
from saturn_ai.grounding.saturn_sufficiency_gate import SaturnQuestionGate
from saturn_ai.retrieval.saturn_channel import (
    SaturnRetrievalService, build_saturn_retrieval_bundle,
)


class SaturnGroundingEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = fixture_snapshot()
        cls.raw = calibration_gold_bytes(cls.snapshot)
        cls.dataset = validate_gold(cls.raw, cls.snapshot, split="synthetic_calibration")
        cls.profile = SaturnEvaluationProfile("synthetic_calibration")
        cls.bundle = build_saturn_retrieval_bundle(cls.snapshot)
        cls.service = SaturnRetrievalService()
        cls.service.publish(cls.bundle)
        cls.verifier = SaturnClaimVerificationService(provider=SaturnFakeClaimProvider())
        cls.gate = SaturnQuestionGate()
        cls.assembly = SaturnAnswerAssemblyService(verifier=cls.verifier)

    @classmethod
    def ask(cls, case_id):
        case = next(x for x in cls.dataset.cases if x.case_id == case_id)
        return _run_question(cls.service, cls.assembly, cls.gate,
                             cls.verifier, case.question, cls.profile)

    @classmethod
    def assess(cls, case_id):
        case = next(x for x in cls.dataset.cases if x.case_id == case_id)
        answer, trace = cls.ask(case_id)
        return score_answer(case, answer, cls.snapshot, trace)

    def mutate_dataset(self, mutate):
        source = json.loads(self.raw)
        mutate(source)
        return serialize_gold(source)

    def assert_gold_fail(self, raw):
        with self.assertRaises(GoldValidationError):
            validate_gold(raw, self.snapshot)

    # A: Strict gold/schema identity and canonical provenance.
    def test_t01_valid_pinned_calibration(self):
        self.assertEqual(len(self.dataset.cases), 28)
        self.assertEqual(self.dataset.sha256, sha256(self.raw).hexdigest())
        self.assertEqual(self.dataset.snapshot_id, self.snapshot.snapshot_id)

    def test_t02_wrong_snapshot(self):
        self.assert_gold_fail(self.mutate_dataset(
            lambda d: d.update(snapshot_id="f" * 64)))

    def test_t03_wrong_corpus(self):
        self.assert_gold_fail(self.mutate_dataset(
            lambda d: d.update(corpus_hash="f" * 64)))

    def test_t04_duplicate_ids(self):
        self.assert_gold_fail(self.mutate_dataset(
            lambda d: d["cases"][1].update(case_id=d["cases"][0]["case_id"])))

    def test_t05_duplicate_question(self):
        self.assert_gold_fail(self.mutate_dataset(
            lambda d: d["cases"][1].update(question=d["cases"][0]["question"])))

    def test_t06_invalid_status(self):
        self.assert_gold_fail(self.mutate_dataset(
            lambda d: d["cases"][0].update(expected_status="pass")))

    def test_t07_positive_without_gold(self):
        self.assert_gold_fail(self.mutate_dataset(
            lambda d: d["cases"][0].update(required=[])))

    def test_t08_fabricated_fact(self):
        self.assert_gold_fail(self.mutate_dataset(
            lambda d: d["cases"][0]["required"][0].update(canonical_id="invented")))

    def test_t09_fabricated_pointer(self):
        self.assert_gold_fail(self.mutate_dataset(
            lambda d: d["cases"][0]["required"][0].update(evidence_id="invented")))

    def test_t10_wrong_revision(self):
        self.assert_gold_fail(self.mutate_dataset(
            lambda d: d["cases"][0]["required"][0].update(source_revision_id="f"*64)))

    def test_t11_duplicate_requirements(self):
        self.assert_gold_fail(self.mutate_dataset(
            lambda d: d["cases"][10]["required"].append(
                dict(d["cases"][10]["required"][0]))))

    def test_t12_oversized_question(self):
        self.assert_gold_fail(self.mutate_dataset(
            lambda d: d["cases"][0].update(question="Q" * 4001)))

    def test_t13_excess_cases(self):
        self.assert_gold_fail(self.mutate_dataset(
            lambda d: d.update(cases=d["cases"] * 12)))

    def test_t14_unknown_extra_field(self):
        self.assert_gold_fail(self.mutate_dataset(
            lambda d: d["cases"][0].update(untrusted_extra=True)))

    def test_t15_negative_without_justification(self):
        self.assert_gold_fail(self.mutate_dataset(
            lambda d: d["cases"][17].update(negative_reason=None)))

    def test_t16_dataset_split_mismatch(self):
        self.assert_gold_fail(self.mutate_dataset(
            lambda d: d.update(split="synthetic_blind")))

    def test_t17_source_quote_cannot_be_positive_gold(self):
        pdf = next(p for p in self.snapshot.answer_evidence
                   if p.evidence_type == "pdf_passage")
        self.assert_gold_fail(self.mutate_dataset(
            lambda d: d["cases"][0].update(required=[{
                "requirement_id": "r1", "kind": "pdf_quote",
                "canonical_id": self.snapshot.pdf_revisions[0].document_id,
                "source_revision_id": pdf.source_revision_id,
                "evidence_id": pdf.evidence_id, "physical_page": pdf.page_number,
                "exact_quote": pdf.text[:10],
            }])))

    def test_t18_wrong_pdf_page(self):
        pdf = next(p for p in self.snapshot.answer_evidence
                   if p.evidence_type == "pdf_passage")
        self.assert_gold_fail(self.mutate_dataset(
            lambda d: d["cases"][17].update(required=[{
                "requirement_id": "r1", "kind": "pdf_quote",
                "canonical_id": self.snapshot.pdf_revisions[0].document_id,
                "source_revision_id": pdf.source_revision_id,
                "evidence_id": pdf.evidence_id, "physical_page": 1000,
                "exact_quote": pdf.text[:10],
            }])))

    def test_t19_wrong_pdf_exact_extract(self):
        pdf = next(p for p in self.snapshot.answer_evidence
                   if p.evidence_type == "pdf_passage")
        self.assert_gold_fail(self.mutate_dataset(
            lambda d: d["cases"][17].update(required=[{
                "requirement_id": "r1", "kind": "pdf_quote",
                "canonical_id": self.snapshot.pdf_revisions[0].document_id,
                "source_revision_id": pdf.source_revision_id,
                "evidence_id": pdf.evidence_id, "physical_page": pdf.page_number,
                "exact_quote": "not in the actual PDF",
            }])))

    # B: actual 4A-5D results and scorer adversarial tests.
    def test_t20_real_positive_source_identity(self):
        result = self.assess("C01")
        self.assertEqual(result.actual_status, "answered")
        self.assertEqual(result.supported_fact_count, 1)
        self.assertTrue(result.fully_correct)

    def test_t21_real_two_needs(self):
        result = self.assess("C11")
        self.assertEqual(result.required_fact_count, 2)
        self.assertEqual(result.supported_fact_count, 2)
        self.assertTrue(result.fully_correct)

    def test_t22_real_partial_is_not_full_positive(self):
        positive = next(x for x in self.dataset.cases if x.case_id == "C11")
        partial, trace = self.ask("C20")
        partial = replace(partial, question_sha256=sha256(positive.question.encode("utf-8")).hexdigest())
        outcome = score_answer(positive, partial, self.snapshot, trace)
        self.assertFalse(outcome.fully_correct)
        self.assertGreaterEqual(outcome.missing_requirement_count, 1)

    def test_t23_false_refusal(self):
        case = next(x for x in self.dataset.cases if x.case_id == "C01")
        result, trace = self.ask("C18")
        result = replace(result, question_sha256=sha256(case.question.encode("utf-8")).hexdigest())
        result = replace(result, question_sha256=sha256(case.question.encode("utf-8")).hexdigest())
        outcome = score_answer(case, result, self.snapshot, trace)
        self.assertFalse(outcome.fully_correct)
        self.assertIn("false_refusal", outcome.failure_codes)

    def test_t24_false_clarification(self):
        case = next(x for x in self.dataset.cases if x.case_id == "C01")
        result, trace = self.ask("C21")
        outcome = score_answer(case, result, self.snapshot, trace)
        self.assertFalse(outcome.fully_correct)
        self.assertIn("false_refusal", outcome.failure_codes)

    def test_t25_correct_needs_support(self):
        result = self.assess("C18")
        self.assertEqual(result.actual_status, "needs_support")
        self.assertTrue(result.fully_correct)

    def test_t26_correct_clarification(self):
        result = self.assess("C21")
        self.assertEqual(result.actual_status, "clarification")
        self.assertTrue(result.fully_correct)

    def test_t27_error_not_correct_refusal(self):
        case = next(x for x in self.dataset.cases if x.case_id == "C18")
        result, trace = self.ask("C18")
        forged = replace(result, status="error",
                         answer_text="Не удалось выполнить проверку.")
        scored = score_answer(case, forged, self.snapshot, trace)
        self.assertFalse(scored.fully_correct)
        self.assertIn("technical_failure", scored.failure_codes)

    def test_t28_wrong_structured_raw_text_detected(self):
        case = next(x for x in self.dataset.cases if x.case_id == "C01")
        answer, trace = self.ask("C01")
        bad = replace(answer.statements[0], text="Device X — interface: Ethernet.")
        forged = replace(answer, statements=(bad,), answer_text=bad.text)
        scored = score_answer(case, forged, self.snapshot, trace)
        self.assertFalse(scored.fully_correct)
        self.assertGreaterEqual(scored.unsupported_claim_count, 1)

    def test_t29_wrong_source_commit_detected(self):
        case = next(x for x in self.dataset.cases if x.case_id == "C01")
        answer, trace = self.ask("C01")
        c = replace(answer.citations[0], source_commit_sha="f"*40)
        scored = score_answer(case, replace(answer, citations=(c,)),
                              self.snapshot, trace)
        self.assertFalse(scored.fully_correct)
        self.assertFalse(scored.citation_valid)

    def test_t30_wrong_blob_sha_detected(self):
        case = next(x for x in self.dataset.cases if x.case_id == "C01")
        answer, trace = self.ask("C01")
        c = replace(answer.citations[0], source_blob_sha="f"*40)
        self.assertFalse(score_answer(case, replace(answer, citations=(c,)),
                                      self.snapshot, trace).citation_valid)

    def test_t31_wrong_content_sha_detected(self):
        case = next(x for x in self.dataset.cases if x.case_id == "C01")
        answer, trace = self.ask("C01")
        c = replace(answer.citations[0], source_content_sha256="f"*64)
        self.assertFalse(score_answer(case, replace(answer, citations=(c,)),
                                      self.snapshot, trace).citation_valid)

    def test_t32_wrong_field_locator_detected(self):
        case = next(x for x in self.dataset.cases if x.case_id == "C01")
        answer, trace = self.ask("C01")
        c = replace(answer.citations[0], field_path="protocol")
        self.assertFalse(score_answer(case, replace(answer, citations=(c,)),
                                      self.snapshot, trace).citation_valid)

    def test_t33_missing_citation_fails(self):
        case = next(x for x in self.dataset.cases if x.case_id == "C01")
        answer, trace = self.ask("C01")
        scored = score_answer(case, replace(answer, citations=()),
                              self.snapshot, trace)
        self.assertFalse(scored.fully_correct)
        self.assertIsNone(scored.citation_valid)

    def test_t34_no_citation_is_na_not_100(self):
        outcome = self.assess("C18")
        self.assertIsNone(outcome.citation_valid)
        self.assertEqual(calculate_metrics((outcome,))["citation_validity"]["denominator"], 0)
        self.assertIsNone(calculate_metrics((outcome,))["citation_validity"]["rate"])

    def test_t35_document_lookup_provenance(self):
        result = self.assess("C15")
        self.assertEqual(result.actual_status, "answered")
        self.assertTrue(result.fully_correct)

    def test_t36_document_is_not_technical_fact(self):
        case = next(x for x in self.dataset.cases if x.case_id == "C01")
        answer, trace = self.ask("C15")
        answer = replace(answer, question_sha256=sha256(case.question.encode("utf-8")).hexdigest())
        scored = score_answer(case, answer, self.snapshot, trace)
        self.assertFalse(scored.fully_correct)

    def test_t37_real_relation(self):
        result = self.assess("C13")
        self.assertEqual(result.actual_status, "answered")
        self.assertTrue(result.fully_correct)

    def test_t38_quote_only_not_technical_proof(self):
        answer, trace = self.ask("C26")
        case = next(x for x in self.dataset.cases if x.case_id == "C01")
        answer = replace(answer, question_sha256=sha256(case.question.encode("utf-8")).hexdigest())
        scored = score_answer(case, answer, self.snapshot, trace)
        self.assertEqual(scored.supported_fact_count, 0)
        self.assertFalse(scored.fully_correct)

    def test_t39_wrong_answer_text_detected(self):
        case = next(x for x in self.dataset.cases if x.case_id == "C01")
        answer, trace = self.ask("C01")
        scored = score_answer(case, replace(answer,
                               answer_text=answer.answer_text + "\nEthernet."),
                              self.snapshot, trace)
        self.assertFalse(scored.fully_correct)
        self.assertIn("unsafe_claim", scored.failure_codes)

    def test_t40_source_hit_uses_five_candidates(self):
        case = next(x for x in self.dataset.cases if x.case_id == "C01")
        answer, trace = self.ask("C01")
        eid = case.required[0].evidence_id
        modified = replace(trace, ranked_evidence_ids=(
            "a", "b", "c", "d", "e", eid))
        self.assertFalse(score_answer(case, answer, self.snapshot,
                                      modified).source_hit_at_5)

    # C: real reporting and strict denominator tests.
    def test_t41_rates_have_explicit_denominators(self):
        positive = self.assess("C01")
        negative = self.assess("C18")
        m = calculate_metrics((positive, negative))
        self.assertEqual(m["positive_complete_answer"]["denominator"], 1)
        self.assertEqual(m["needs_support_correctness"]["denominator"], 1)
        self.assertEqual(m["status_accuracy"]["denominator"], 2)

    def test_t42_requirement_recall_denominator(self):
        outcomes = [self.assess(x) for x in ("C01", "C11")]
        m = calculate_metrics(outcomes)
        self.assertEqual(m["requirement_recall"]["denominator"], 3)

    def test_t43_false_refusal_denominator(self):
        positive = self.assess("C01")
        refused = replace(positive, actual_status="needs_support",
                          fully_correct=False)
        m = calculate_metrics((positive, refused))
        self.assertEqual(m["false_refusal"]["denominator"], 2)
        self.assertEqual(m["false_refusal"]["numerator"], 1)

    def test_t44_empty_denominator(self):
        m = calculate_metrics(())
        self.assertEqual(m["case_count"], 0)
        self.assertIsNone(m["positive_complete_answer"]["rate"])
        self.assertIsNone(m["citation_validity"]["rate"])

    def test_t45_profiles_never_mixed(self):
        from saturn_ai.evaluation.saturn_answer_reporting import build_report
        a = self.assess("C01")
        with self.assertRaises(ValueError):
            build_report(self.dataset, (replace(a, split="synthetic_blind"),),
                         code_revision="a"*40, config_hash="x", bundle=self.bundle)

    def test_t46_actual_full_offline_calibration_is_measured(self):
        report = evaluate(self.raw, self.snapshot, profile=self.profile,
                          code_revision="a"*40)
        self.assertEqual(report["metrics"]["case_count"], 28)
        self.assertEqual(report["independent_blind_evaluation"], "NOT_RUN")
        self.assertFalse(report["production_readiness"])
        self.assertEqual(len(report["cases"]), 28)
        self.assertIsNone(report["quality_target_met"])
        self.assertEqual(
            report_bytes(report), report_bytes(
                evaluate(self.raw, self.snapshot, profile=self.profile,
                         code_revision="a"*40)))

    def test_t47_default_report_no_raw_source_or_questions(self):
        report = evaluate(self.raw, self.snapshot, profile=self.profile,
                          code_revision="a"*40)
        raw = report_bytes(report)
        self.assertNotIn(b'"question":', raw)
        self.assertNotIn(b'"answer_text":', raw)
        self.assertNotIn(b'"source_text":', raw)
        self.assertNotIn(b'"traceback":', raw)

    # D: durable blind experiment identity, mismatch and first-run protocol.
    def _freeze(self):
        return freeze_manifest(
            experiment_id="blind-001", code_revision="a"*40,
            dataset_sha256=sha256(self.raw).hexdigest(), snapshot=self.snapshot,
            case_count=28)

    def test_t48_freeze_matches_code_and_dataset(self):
        value = self._freeze()
        self.assertEqual(validate_freeze(
            value, code_revision="a"*40, dataset_bytes=self.raw,
            snapshot=self.snapshot, mode="lexical", top_k=10), value)

    def test_t49_dataset_hash_change_rejected(self):
        with self.assertRaises(BlindIntegrityError):
            validate_freeze(self._freeze(), code_revision="a"*40,
                            dataset_bytes=self.raw+b" ", snapshot=self.snapshot,
                            mode="lexical", top_k=10)

    def test_t50_code_change_rejected(self):
        with self.assertRaises(BlindIntegrityError):
            validate_freeze(self._freeze(), code_revision="b"*40,
                            dataset_bytes=self.raw, snapshot=self.snapshot,
                            mode="lexical", top_k=10)

    def test_t51_config_change_rejected(self):
        with self.assertRaises(BlindIntegrityError):
            validate_freeze(self._freeze(), code_revision="a"*40,
                            dataset_bytes=self.raw, snapshot=self.snapshot,
                            mode="dense", top_k=10)

    def test_t52_start_receipt_precedes_blind_gold(self):
        with TemporaryDirectory() as tmp:
            b = BlindRun(freeze=self._freeze(), receipts_dir=Path(tmp)/"receipts",
                         report_path=Path(tmp)/"report.json")
            b.start()
            self.assertTrue(b.start_path.exists())
            self.assertEqual(json.loads(b.start_path.read_text())["status"], "START")

    def test_t53_start_cannot_repeat(self):
        with TemporaryDirectory() as tmp:
            b = BlindRun(freeze=self._freeze(), receipts_dir=Path(tmp)/"receipts",
                         report_path=Path(tmp)/"report.json")
            b.start()
            with self.assertRaises(BlindIntegrityError):
                BlindRun(freeze=self._freeze(),
                         receipts_dir=Path(tmp)/"receipts",
                         report_path=Path(tmp)/"report.json").start()

    def test_t54_existing_report_cannot_overwrite(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)/"report.json"
            path.write_text("existing", encoding="utf-8")
            with self.assertRaises(BlindIntegrityError):
                BlindRun(freeze=self._freeze(),
                         receipts_dir=Path(tmp)/"receipts",
                         report_path=path).start()
            self.assertEqual(path.read_text(), "existing")

    def test_t55_failed_receipt_survives(self):
        with TemporaryDirectory() as tmp:
            b = BlindRun(freeze=self._freeze(), receipts_dir=Path(tmp)/"receipts",
                         report_path=Path(tmp)/"report.json")
            b.start()
            b.fail("evaluation_failed")
            self.assertTrue(b.start_path.exists())
            self.assertTrue(b.failed_path.exists())
            with self.assertRaises(BlindIntegrityError):
                BlindRun(freeze=self._freeze(),
                         receipts_dir=Path(tmp)/"receipts",
                         report_path=Path(tmp)/"report.json").start()

    def test_t56_only_fixed_lexical_profile(self):
        with self.assertRaises(ValueError):
            SaturnEvaluationProfile("synthetic_calibration", top_k=5)
        with self.assertRaises(ValueError):
            SaturnEvaluationProfile("synthetic_calibration", mode="dense")

    def test_t57_gold_not_in_runtime_api(self):
        from saturn_ai.evaluation import saturn_grounding
        case = self.dataset.cases[0]
        seen = []
        real = saturn_grounding._run_question
        def spy(service, assembly, gate, verifier, question, profile):
            seen.append((question, profile))
            self.assertEqual(type(question), str)
            self.assertNotIn("required", question)
            return real(service, assembly, gate, verifier, question, profile)
        with patch.object(saturn_grounding, "_run_question", spy):
            report = evaluate(serialize_gold({
                **{k: v for k, v in json.loads(self.raw).items() if k != "cases"},
                "cases": [json.loads(self.raw)["cases"][0]],
            }), self.snapshot, profile=self.profile, code_revision="a"*40)
        self.assertEqual(len(seen), 1)
        self.assertEqual(report["metrics"]["case_count"], 1)


if __name__ == "__main__":
    unittest.main()
