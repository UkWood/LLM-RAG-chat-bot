from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from unit.test_evaluation import ROOT, CORPUS, DATASET
from unit.test_retrieval import TestEncoder
from saturn_ai.ingestion.registry import load_registry
from saturn_ai.ingestion.pipeline import build_fixture
from saturn_ai.snapshots import build_snapshot
from saturn_ai.evaluation.dataset import validate_dataset
from saturn_ai.retrieval.contracts import Candidate, SearchTrace
from saturn_ai.retrieval.service import RetrievalService
from saturn_ai.evaluation.retrieval import score_case, aggregate, run_retrieval_evaluation


class RetrievalEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry=load_registry((CORPUS/'registry.json').read_bytes())
        cls.snapshot=build_snapshot(build_fixture(CORPUS,cls.registry,cls.registry.source_snapshot),cls.registry)
        cls.dataset=validate_dataset(DATASET.read_bytes(),cls.snapshot)

    def trace(self, chunks):
        candidates=tuple(Candidate(c.chunk_id,c.source_id,self.snapshot.snapshot_id,1/rank,rank,'lexical')
                         for rank,c in enumerate(chunks,1))
        return SearchTrace(self.snapshot.snapshot_id,'lexical',candidates,(),candidates)

    def test_source_hit_is_not_gold_fact_hit_and_mrr_uses_actual_rank(self):
        case=self.dataset.cases[0]
        wrong=next(c for c in self.snapshot.chunks if c.source_id not in case.expected_sources)
        right_source_wrong_fact=next(c for c in self.snapshot.chunks if c.source_id in case.expected_sources and c.chunk.field_path=='title')
        row=score_case(case,self.snapshot,self.trace([wrong,right_source_wrong_fact]))
        self.assertTrue(row['source_hit_at_5'])
        self.assertEqual(row['gold_evidence_recall_at_5'],0)
        self.assertEqual(row['reciprocal_rank_at_5'],0.5)
        missing=score_case(case,self.snapshot,self.trace([wrong]))
        result=aggregate([row,missing])
        self.assertEqual(result['positive_cases'],2)
        self.assertEqual(result['source_hit_at_5'],0.5)
        self.assertEqual(result['mrr_at_5'],0.25)

    def test_negative_cases_not_scored_as_refusal_or_added_to_positive_denominator(self):
        case=next(c for c in self.dataset.cases if c.expected_status=='refused')
        row=score_case(case,self.snapshot,self.trace([self.snapshot.chunks[0]]))
        self.assertIsNone(row['source_hit_at_5'])
        self.assertEqual(row['answer_evaluation'],'not_run')
        metrics=aggregate([row])
        self.assertEqual(metrics['positive_cases'],0)
        self.assertIsNone(metrics['source_hit_at_5'])
        self.assertIsNone(metrics['mrr_at_5'])

    def test_multi_source_recall_does_not_become_all_source_success(self):
        case=next(c for c in self.dataset.cases if c.category=='multi_doc')
        first=next(c for c in self.snapshot.chunks if c.source_id==case.expected_sources[0])
        row=score_case(case,self.snapshot,self.trace([first]))
        self.assertTrue(row['source_hit_at_5'])
        self.assertFalse(row['all_expected_sources_at_5'])
        self.assertEqual(row['expected_source_recall_at_5'],0.5)

    def test_untrusted_results_with_wrong_identity_are_rejected(self):
        from dataclasses import replace
        case=self.dataset.cases[0];trace=self.trace([self.snapshot.chunks[0]])
        for bad in [replace(trace,snapshot_id='0'*64),
                    replace(trace,final=(replace(trace.final[0],source_id='invented'),)),
                    replace(trace,final=trace.final+trace.final),
                    replace(trace,final=(replace(trace.final[0],score=float('nan')),))]:
            with self.assertRaises(ValueError):score_case(case,self.snapshot,bad)

    def test_real_lexical_runner_receives_questions_without_expected_labels(self):
        seen=[];original=RetrievalService.search
        def spy(service,query,**kwargs):
            seen.append(query)
            return original(service,query,**kwargs)
        with patch.object(RetrievalService,'search',new=spy):
            report=run_retrieval_evaluation(CORPUS,DATASET)
        self.assertEqual(seen,[c.question for c in self.dataset.cases])
        self.assertEqual(report['quality_evaluation'],dict(lexical='measured',dense='not_run',hybrid='not_run',
                                                         reranking='not_run',grounding='not_run',refusal='not_run'))
        self.assertEqual(report['metrics']['all']['positive_cases'],20)
        self.assertEqual(report['metrics']['calibration']['positive_cases'],14)
        self.assertEqual(report['metrics']['held_out']['positive_cases'],6)
        self.assertEqual(len(report['cases']),30)
        self.assertNotIn('question',report['cases'][0])

    def test_dense_quality_report_requires_real_local_checkpoint(self):
        with self.assertRaises(ValueError):
            run_retrieval_evaluation(CORPUS,DATASET,mode='hybrid')
        with patch('saturn_ai.evaluation.retrieval.LocalONNXEncoder',return_value=TestEncoder()):
            with self.assertRaises(ValueError):
                run_retrieval_evaluation(CORPUS,DATASET,mode='hybrid',model_directory=Path('test-placeholder'))
