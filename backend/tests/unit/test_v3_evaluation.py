"""Calibration/grader guards; never opens the V3 blind payload."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unit import test_v3_evidence as support
from saturn_ai.providers import FakeLLMProvider
from saturn_ai.grounding.application_v3 import GroundedConsultantV3
from saturn_ai.grounding.v3_config import load_v3_config
from saturn_ai.evaluation.v3_dataset import validate_v3
from saturn_ai.evaluation.planner_v3 import score_v3_case,choose_configuration,project_threshold_result,create_v3_freeze

class EvaluationTests(unittest.TestCase):
    def setUp(self):support.EvidenceTests.setUp(self)
    def test_calibration_schema_canonical_groups_and_bad_count(self):
        # Implementer-authored calibration is exposed; this test never touches independent blind.
        raw=Path('evaluation/datasets/planner-v3-calibration.json').read_bytes()
        cases=validate_v3(raw,self.s,'calibration');self.assertEqual(len(cases),60)
        data=json.loads(raw);data['cases'][0]['requirements'][0]['evidence'][0]['text']='invented'
        with self.assertRaises(ValueError):validate_v3(json.dumps(data).encode(),self.s,'calibration')
        data=json.loads(raw);data['cases'].pop()
        with self.assertRaises(ValueError):validate_v3(json.dumps(data).encode(),self.s,'calibration')
    def test_exact_plan_and_quote_support_are_separate(self):
        q='Питание EDU-410 по карточке?';r=GroundedConsultantV3(self.service,support.Scorer3(),FakeLLMProvider(),mode='lexical').answer(q)
        case=dict(id='custom',group='single_field',question=q,expected_status='answered',requirements=[dict(entity_id='products/edu-410',predicate='power',selector='',document_kind='product_card',representation='any',reference=None,evidence=[dict(source_id='synthetic:products/edu-410',field_path='power',page=None,text='24 В')])])
        row=score_v3_case(case,self.s,r);self.assertTrue(row['fully_correct']);self.assertTrue(row['plan_correct'])
        n=replace(r.plan.needs[0],constraints=replace(r.plan.needs[0].constraints,document_kind='any'))
        bad=replace(r,plan=replace(r.plan,needs=(n,)))
        row=score_v3_case(case,self.s,bad);self.assertFalse(row['plan_correct']);self.assertFalse(row['fully_correct'])
    def test_threshold_projection_can_only_abstain_and_grid_must_improve_safely(self):
        r=GroundedConsultantV3(self.service,support.Scorer3(),FakeLLMProvider(),mode='lexical').answer('Питание EDU-410?')
        cfg=load_v3_config()[0];frames=[dict(scores=[5.,4.5])]
        projected=project_threshold_result(r,frames,cfg)
        self.assertEqual(projected.status,'clarification');self.assertEqual(projected.claims,())
        low=project_threshold_result(r,frames,dict(cfg,score_min=10.))
        self.assertEqual(low.status,'refused')
        pos=dict(expected_status='answered',status='answered',fully_correct=True,canonical_output_valid=True,unsafe_answer=False)
        neg=dict(expected_status='refused',status='refused',fully_correct=True,canonical_output_valid=True,unsafe_answer=False)
        baseline=[dict(pos,status='refused',fully_correct=False),neg]
        grid=[dict(settings=cfg,rows=[pos,dict(neg,status='error',fully_correct=False)],legacy_regression_ids=[])]
        self.assertIsNone(choose_configuration(grid,baseline))
        grid[0]['rows']=[pos,neg];self.assertIsNotNone(choose_configuration(grid,baseline))
        self.assertIsNone(choose_configuration(grid,[pos,neg]))
    def test_infeasibility_cannot_create_freeze_or_consume_blind(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);report=root/'cal.json';report.write_text(json.dumps(dict(feasible=False)))
            with self.assertRaises(ValueError):create_v3_freeze(root/'absent-blind.json',report,root/'model',root/'reranker',root/'freeze.json')
            self.assertFalse((root/'freeze.json').exists())

    def test_grid_cannot_qualify_missing_cases(self):
        pos=dict(expected_status='answered',status='answered',fully_correct=True,canonical_output_valid=True,unsafe_answer=False)
        neg=dict(expected_status='refused',status='refused',fully_correct=True,canonical_output_valid=True,unsafe_answer=False)
        baseline=[dict(pos,status='refused',fully_correct=False),neg]
        trial=dict(settings=load_v3_config()[0],rows=[pos],legacy_regression_ids=[])
        self.assertIsNone(choose_configuration([trial],baseline))

    def test_malformed_gold_need_is_cleanly_rejected(self):
        data=json.loads(Path('evaluation/datasets/planner-v3-calibration.json').read_bytes())
        for invalid in (None,dict(data['cases'][0]['requirements'][0],entity_id=[])):
            candidate=json.loads(json.dumps(data));candidate['cases'][0]['requirements']=[invalid]
            with self.subTest(invalid_type=type(invalid).__name__),self.assertRaises(ValueError):
                validate_v3(json.dumps(candidate).encode(),self.s,'calibration')

    def test_uninstrumented_baseline_retrieval_is_not_reported_as_zero_recall(self):
        from saturn_ai.grounding.application_v2 import GroundedConsultantV2
        q='Питание EDU-410?';result=GroundedConsultantV2(self.service,support.Scorer3(),FakeLLMProvider(),mode='lexical').answer(q)
        case=dict(id='baseline',group='single_field',question=q,expected_status='answered',requirements=[dict(entity_id='products/edu-410',predicate='power',selector='',document_kind='any',representation='any',reference=None,evidence=[dict(source_id='synthetic:products/edu-410',field_path='power',page=None,text='24 В')])])
        row=score_v3_case(case,self.s,result)
        self.assertIsNone(row['pool_gold_pointer_recall']);self.assertIsNone(row['retrieval_pairs'])
