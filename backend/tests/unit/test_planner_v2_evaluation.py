"""Evaluator tests use custom cases only. NEVER loads the pinned blind dataset."""
from dataclasses import replace
import unittest
from unit.test_evidence_gate import prepared
from unit.test_reranking import Scorer
from saturn_ai.providers import FakeLLMProvider
from saturn_ai.snapshots import SnapshotCatalog
from saturn_ai.retrieval.lexical import BM25Index
from saturn_ai.retrieval.service import RetrievalService,IndexSet
from saturn_ai.grounding.application_v2 import GroundedConsultantV2
from saturn_ai.grounding.v2_contracts import GroundedResultV2
from saturn_ai.evaluation.planner_v2 import score_v2_case,aggregate_v2


class PlannerV2EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.snapshot=prepared();service=RetrievalService(SnapshotCatalog(self.snapshot.registry))
        service.publish(IndexSet(self.snapshot,BM25Index(self.snapshot)))
        self.app=GroundedConsultantV2(service,Scorer(),FakeLLMProvider(),mode='lexical')
        chunk=next(c for c in self.snapshot.chunks if c.source_id=='synthetic:products/edu-410' and c.chunk.field_path=='power')
        self.case=dict(id='custom-positive',group='single_field',question='Питание EDU-410?',expected_status='answered',requirements=[
            dict(entity_id='products/edu-410',predicate='power',selector='',document_kind='any',representation='any',reference=None,
                 evidence=[dict(source_id=chunk.source_id,field_path='power',page=None,text='24 В')])])

    def test_need_correctness_and_exact_pointer_coverage_are_separate(self):
        result=self.app.answer(self.case['question']);row=score_v2_case(self.case,self.snapshot,result)
        self.assertTrue(row['fully_correct']);self.assertEqual(row['requirement_coverage'],1.0)
        self.assertEqual(row['gold_pointer_coverage'],1.0)
        # Valid canonical quote alone cannot cure an explicitly wrong v2 subject binding.
        badneed=replace(result.plan.needs[0],entity_id='products/edu-420')
        bad=replace(result,plan=replace(result.plan,needs=(badneed,)))
        self.assertFalse(score_v2_case(self.case,self.snapshot,bad)['fully_correct'])
        wrong=replace(result,sources=(replace(result.sources[0],page_start=999),))
        self.assertFalse(score_v2_case(self.case,self.snapshot,wrong)['canonical_output_valid'])

    def test_refs_do_not_require_fabricated_quote_claims(self):
        result=self.app.answer('Какой тип сущности у EDU-CONFIG?')
        self.assertEqual(result.status,'answered')
        reference=result.references[0]
        case=dict(id='custom-ref',group='relationship_type',question='Какой тип сущности у EDU-CONFIG?',expected_status='answered',requirements=[
            dict(entity_id='products/edu-config',predicate='entity_type',selector='',document_kind='any',representation='any',evidence=[],
                 reference=dict(kind='entity_type',source_id=reference.source_id,value='Software'))])
        row=score_v2_case(case,self.snapshot,result);self.assertTrue(row['fully_correct']);self.assertEqual(row['claim_count'],0)
        wrong_scope=dict(case,requirements=[dict(case['requirements'][0],document_kind='manual')])
        self.assertFalse(score_v2_case(wrong_scope,self.snapshot,result)['fully_correct'])
        wrong_plan=replace(result,plan=replace(result.plan,needs=(replace(result.plan.needs[0],predicate='power'),)))
        self.assertFalse(score_v2_case(case,self.snapshot,wrong_plan)['fully_correct'])
        forged=replace(result,references=(replace(reference,value='Device'),))
        self.assertFalse(score_v2_case(case,self.snapshot,forged)['fully_correct'])

    def test_negative_errors_and_missing_need_not_success(self):
        refused=dict(self.case,id='custom-negative',expected_status='refused',requirements=[])
        error=GroundedResultV2('error','not_evaluated','retrieval_unavailable',self.snapshot.snapshot_id)
        r=score_v2_case(refused,self.snapshot,error);self.assertFalse(r['fully_correct'])
        capture_error=replace(error,snapshot_id='')
        self.assertEqual(score_v2_case(refused,self.snapshot,capture_error)['status'],'error')
        positive=score_v2_case(self.case,self.snapshot,GroundedResultV2('refused','insufficient','no_evidence',self.snapshot.snapshot_id))
        metrics=aggregate_v2([r,positive]);self.assertEqual(metrics['errors'],1);self.assertEqual(metrics['false_refusal_rate'],1.0)
        self.assertEqual(metrics['fully_correct_rate'],0.0);self.assertIsNone(metrics['verbatim_claim_support_rate'])
        answered=self.app.answer(self.case['question']);self.assertFalse(score_v2_case(refused,self.snapshot,answered)['fully_correct'])
