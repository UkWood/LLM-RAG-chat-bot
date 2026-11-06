from dataclasses import replace
import unittest
from unit.test_evidence_gate import prepared
from unit.test_evaluation import DATASET
from saturn_ai.evaluation.dataset import validate_dataset
from saturn_ai.domain import Claim
from saturn_ai.grounding.contracts import GroundedResult,GroundedCitation
from saturn_ai.evaluation.grounding import score_grounded_result,aggregate_grounding


class GroundingEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=prepared();cls.dataset=validate_dataset(DATASET.read_bytes(),cls.snapshot)

    def citation(self,c):
        record=next(r for r in self.snapshot.registry.entries if r.source_id==c.source_id)
        return GroundedCitation(c.chunk_id,c.source_id,record.title,record.url or record.canonical_path,
            c.chunk.document_id,c.source_hash,c.source_commit,c.chunk.heading_path,c.chunk.page_start,c.chunk.page_end)

    def test_correct_and_false_refusal_denominators_and_errors(self):
        positive=next(c for c in self.dataset.cases if c.must_answer)
        negative=next(c for c in self.dataset.cases if c.must_refuse)
        typo=next(c for c in self.dataset.cases if c.expected_status=='clarification')
        def row(case,status):return score_grounded_result(case,self.snapshot,GroundedResult(status,'insufficient','test',self.snapshot.snapshot_id))
        metrics=aggregate_grounding([row(positive,'refused'),row(negative,'refused'),row(typo,'clarification'),row(negative,'error')])
        self.assertEqual(metrics['positive_cases'],1);self.assertEqual(metrics['false_refusal_rate'],1.0)
        self.assertEqual(metrics['proper_refusal_rate'],0.5);self.assertEqual(metrics['proper_clarification_rate'],1.0)
        self.assertEqual(metrics['errors'],1);self.assertEqual(metrics['expected_status_accuracy'],0.5)
        self.assertIsNone(metrics['verbatim_claim_support_rate'])

    def test_real_source_id_does_not_make_fabricated_text_supported(self):
        case=next(c for c in self.dataset.cases if c.must_answer)
        chunk=next(c for c in self.snapshot.chunks if any(c.source_id==ev.source_id and c.chunk.field_path==ev.field_path for ev in case.expected_evidence))
        good=GroundedResult('answered','sufficient',None,self.snapshot.snapshot_id,
            (Claim(chunk.chunk.text,chunk.chunk_id),),(self.citation(chunk),))
        row=score_grounded_result(case,self.snapshot,good)
        self.assertEqual(row['expected_evidence_recall'],1.0);self.assertTrue(row['citation_valid'])
        forged=replace(good,claims=(Claim('Invented unsupported values',chunk.chunk_id),))
        row=score_grounded_result(case,self.snapshot,forged)
        self.assertEqual(row['supported_claim_count'],0);self.assertEqual(row['expected_evidence_recall'],0.0)
        wrong=replace(good,sources=(replace(good.sources[0],page_start=999),))
        self.assertFalse(score_grounded_result(case,self.snapshot,wrong)['citation_valid'])
        wrong=replace(good,sources=(replace(good.sources[0],url='https://evil.invalid/'),))
        self.assertFalse(score_grounded_result(case,self.snapshot,wrong)['citation_valid'])

    def test_report_rows_omit_raw_questions_context_answers(self):
        case=self.dataset.cases[0]
        row=score_grounded_result(case,self.snapshot,GroundedResult('refused','insufficient','unsupported_question',self.snapshot.snapshot_id))
        for key in ('question','answer','context','claims'):self.assertNotIn(key,row)

    def test_runner_passes_only_question_then_scores_labels(self):
        from unittest.mock import patch
        from unit.test_evaluation import CORPUS
        from unit.test_retrieval import TestEncoder
        from unit.test_reranking import Scorer
        from saturn_ai.evaluation.grounding import run_grounding_evaluation
        seen=[];snapshot=self.snapshot
        class OfflineStub:
            def answer(self,question):
                seen.append(question)
                return GroundedResult('refused','insufficient','unsupported_question',snapshot.snapshot_id)
        provenance={k:'test-only' for k in ('bundle_id','model_card_sha256','license_sha256')}
        with patch('saturn_ai.evaluation.grounding.load_semantic_reranker',return_value=(Scorer(),provenance)), \
             patch('saturn_ai.evaluation.grounding.load_embedding',return_value=(TestEncoder(),provenance)), \
             patch('saturn_ai.evaluation.grounding.GroundedConsultant',return_value=OfflineStub()), \
             patch('saturn_ai.evaluation.grounding.version',return_value='test-only'):
            report=run_grounding_evaluation(CORPUS,DATASET,None,None)
        self.assertEqual(seen,[c.question for c in self.dataset.cases])
        self.assertFalse(report['grounding_target_met']);self.assertFalse(report['full_prototype_accepted'])
        self.assertEqual(report['metrics']['all']['positive_cases'],20)
        self.assertTrue(all(not r['provider_called'] for r in report['cases']))
