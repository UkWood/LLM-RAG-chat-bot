from dataclasses import replace
from math import log2
from pathlib import Path
import unittest
from unittest.mock import patch
from unit.test_evaluation import CORPUS,DATASET
from unit.test_retrieval import TestEncoder
from unit.test_reranking import Scorer
from saturn_ai.ingestion.registry import load_registry
from saturn_ai.ingestion.pipeline import build_fixture
from saturn_ai.snapshots import build_snapshot
from saturn_ai.evaluation.dataset import validate_dataset
from saturn_ai.retrieval.contracts import Candidate
from saturn_ai.retrieval.service import RetrievalService
from saturn_ai.evaluation.reranking import evidence_ndcg, run_reranking_evaluation, pool_metrics


class RerankingEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry=load_registry((CORPUS/'registry.json').read_bytes())
        cls.snapshot=build_snapshot(build_fixture(CORPUS,registry,registry.source_snapshot),registry)
        cls.dataset=validate_dataset(DATASET.read_bytes(),cls.snapshot)

    def candidates(self,chunks):
        return tuple(Candidate(c.chunk_id,c.source_id,self.snapshot.snapshot_id,1.0,i,'reranker') for i,c in enumerate(chunks,1))

    def relevant(self,case):
        return [c for c in self.snapshot.chunks if any(c.source_id==e.source_id and c.chunk.field_path==e.field_path
                    and c.chunk.page_start==e.page and e.text in c.chunk.text for e in case.expected_evidence)]

    def test_ndcg_uses_all_snapshot_relevance_not_only_candidate_pool(self):
        case=next(c for c in self.dataset.cases if len(self.relevant(c))>=2)
        relevant=self.relevant(case);wrong=next(c for c in self.snapshot.chunks if c not in relevant)
        dcg=1/log2(3)
        idcg=sum(1/log2(i+2) for i in range(min(5,len(relevant))))
        self.assertAlmostEqual(evidence_ndcg(case,self.snapshot,self.candidates([wrong,relevant[0]])),dcg/idcg)
        self.assertAlmostEqual(evidence_ndcg(case,self.snapshot,self.candidates([relevant[0]])),1/idcg)
        self.assertEqual(evidence_ndcg(case,self.snapshot,self.candidates(relevant[:5])),1.0)
        self.assertEqual(evidence_ndcg(case,self.snapshot,()),0.0)

    def test_negative_null_duplicate_and_missing_gold_fail(self):
        negative=next(c for c in self.dataset.cases if not c.must_answer)
        self.assertIsNone(evidence_ndcg(negative,self.snapshot,()))
        case=next(c for c in self.dataset.cases if c.must_answer);one=self.relevant(case)[0]
        with self.assertRaises(ValueError):evidence_ndcg(case,self.snapshot,self.candidates([one,one]))
        with self.assertRaises(ValueError):evidence_ndcg(replace(case,expected_evidence=()),self.snapshot,())
        # Repeated labels do not make a chunk relevant more than once.
        self.assertEqual(evidence_ndcg(case,self.snapshot,self.candidates([one])),
            evidence_ndcg(replace(case,expected_evidence=case.expected_evidence*2),self.snapshot,self.candidates([one])))

    def test_pool_oracle_is_distinct_from_final_top5(self):
        case=next(c for c in self.dataset.cases if c.category=='multi_doc')
        first=next(c for c in self.snapshot.chunks if c.source_id==case.expected_sources[0])
        metrics=pool_metrics(case,self.candidates([first]))
        self.assertTrue(metrics['oracle_source_hit_at_30'])
        self.assertEqual(metrics['expected_source_coverage_at_30'],0.5)
        self.assertIsNone(pool_metrics(next(c for c in self.dataset.cases if not c.must_answer),())['oracle_source_hit_at_30'])

    def test_runner_routes_questions_without_gold_and_keeps_baseline(self):
        # Dependency substitution tests runner wiring, never publish this as model quality.
        scorer=Scorer();encoder=TestEncoder();encoder.identity=dict(kind='local_onnx',revision='test')
        provenance={'bundle_id':'test','model_card_sha256':'test','license_sha256':'test'}
        seen=[];original=RetrievalService.rerank
        def spy(service,query,reranker,**kwargs):
            seen.append(query);return original(service,query,reranker,**kwargs)
        with patch('saturn_ai.evaluation.reranking.load_semantic_reranker',return_value=(scorer,provenance)), \
             patch('saturn_ai.evaluation.reranking.load_embedding',return_value=(encoder,provenance)), \
             patch.object(RetrievalService,'rerank',new=spy), \
             patch('saturn_ai.evaluation.reranking.version',return_value='test-only'):
            report=run_reranking_evaluation(CORPUS,DATASET,Path('test-only'),Path('test-only'))
        self.assertEqual(seen,[c.question for c in self.dataset.cases])
        self.assertEqual(report['metrics']['all']['positive_cases'],20)
        self.assertEqual(report['quality_evaluation']['grounding'],'not_run')
        self.assertEqual(len(report['cases']),30)
        self.assertTrue(all('question' not in row for row in report['cases']))
        self.assertEqual(report['baseline_metrics']['all']['source_hit_at_5'],report['metrics']['all']['source_hit_at_5'])
        self.assertEqual([q for q,_ in scorer.seen],seen)
