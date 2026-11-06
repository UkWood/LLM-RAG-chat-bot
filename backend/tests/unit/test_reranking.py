from dataclasses import replace
import math
import unittest
from unittest.mock import patch

from unit.test_snapshots import prepared
from saturn_ai.snapshots import build_snapshot, SnapshotCatalog
from saturn_ai.retrieval.lexical import BM25Index
from saturn_ai.retrieval.service import RetrievalService, IndexSet
from saturn_ai.retrieval.contracts import passage_text
from saturn_ai.retrieval.reranking import validate_pairs


class Scorer:
    identity={'kind':'test_only','revision':'numeric'}
    def __init__(self, action=None):self.seen=[];self.action=action
    def score_pairs(self,query,passages):
        self.seen.append((query,passages))
        if self.action:return self.action(passages)
        return [0.0]*len(passages)


class RerankingTests(unittest.TestCase):
    def setUp(self):
        registry,ingestion=prepared();self.snapshot=build_snapshot(ingestion,registry)
        self.catalog=SnapshotCatalog(registry);self.service=RetrievalService(self.catalog)
        self.index=BM25Index(self.snapshot);self.indexes=IndexSet(self.snapshot,self.index)
        self.service.publish(self.indexes)

    def test_ties_preserve_input_rank_and_canonical_passages(self):
        scorer=Scorer();trace=self.service.rerank('RS-485',scorer,mode='lexical')
        self.assertEqual(trace.final,trace.scored[:5])
        self.assertEqual([c.chunk_id for c in trace.final],[c.chunk_id for c in trace.input_candidates[:5]])
        mapping={c.chunk_id:c for c in self.snapshot.chunks}
        self.assertEqual(scorer.seen,[('RS-485',[passage_text(self.snapshot,mapping[c.chunk_id]) for c in trace.input_candidates])])
        self.assertEqual(trace.baseline.final,self.service.search('RS-485').final)
        self.assertTrue(all(c.channel=='reranker' for c in trace.final))

    def test_descending_scores_and_identity_are_copied(self):
        scorer=Scorer(lambda p:list(range(len(p))))
        result=self.service.rerank('RS-485',scorer,mode='lexical')
        self.assertEqual(result.final[0].chunk_id,result.input_candidates[-1].chunk_id)
        scorer.identity['revision']='changed'
        self.assertEqual(result.reranker_identity['revision'],'numeric')
        scorer.identity['revision']='numeric'

    def test_revocation_during_scoring_is_removed_and_ranks_renumbered(self):
        target='synthetic:products/demo-300'
        def revoke(passages):self.catalog.revoke(target);return [0.0]*len(passages)
        result=self.service.rerank('RS-485',Scorer(revoke),mode='lexical')
        self.assertFalse(any(c.source_id==target for c in result.scored))
        self.assertEqual([c.rank for c in result.scored],list(range(1,len(result.scored)+1)))

    def test_revocation_before_scoring_does_not_reach_scorer(self):
        target='synthetic:products/demo-300';self.catalog.revoke(target)
        scorer=Scorer();trace=self.service.rerank('RS-485',scorer,mode='lexical')
        self.assertFalse(any(c.source_id==target for c in trace.input_candidates))

    def test_capture_is_stable_when_new_active_indexes_published(self):
        from unit.test_evaluation import CORPUS
        from saturn_ai.ingestion.registry import load_registry
        from saturn_ai.ingestion.pipeline import build_fixture
        registry=load_registry((CORPUS/'registry.json').read_bytes())
        alternate=build_snapshot(build_fixture(CORPUS,registry,registry.source_snapshot),registry)
        self.assertNotEqual(alternate.snapshot_id,self.snapshot.snapshot_id)
        original=self.index.search
        def republish(*args):
            self.service.publish(IndexSet(alternate,BM25Index(alternate)))
            return original(*args)
        with patch.object(self.index,'search',side_effect=republish):
            result=self.service.rerank('RS-485',Scorer(),mode='lexical')
        self.assertEqual(result.snapshot_id,self.snapshot.snapshot_id)

    def test_invalid_scores_and_adapter_errors_do_not_fallback(self):
        for action in [lambda p:[],lambda p:[math.nan]*len(p),lambda p:[math.inf]*len(p),
                       lambda p:[[1.0]]*len(p),lambda p:[True]*len(p)]:
            with self.subTest(action=action),self.assertRaises(ValueError):
                self.service.rerank('RS-485',Scorer(action),mode='lexical')
        def broken(_):raise RuntimeError('model unavailable')
        with self.assertRaises(RuntimeError):self.service.rerank('RS-485',Scorer(broken),mode='lexical')

    def test_invalid_candidates_rejected_before_scoring(self):
        original=self.index.search
        for mutate in [lambda r:r+r[:1],lambda r:(replace(r[0],source_id='invented'),)+r[1:],
                       lambda r:(replace(r[0],snapshot_id='0'*64),)+r[1:]]:
            scorer=Scorer()
            with patch.object(self.index,'search',side_effect=lambda *a:mutate(original(*a))):
                with self.assertRaises(ValueError):self.service.rerank('RS-485',scorer,mode='lexical')
            self.assertEqual(scorer.seen,[])

    def test_empty_and_input_bounds(self):
        scorer=Scorer();result=self.service.rerank('zzzz_nonexistent',scorer,mode='lexical')
        self.assertEqual(result.final,());self.assertEqual(scorer.seen,[])
        for query,passages in [('',[]),('q'*4001,[]),('q',['p'*20001]),('q',['p']*31),('q',[None])]:
            with self.assertRaises(ValueError):validate_pairs(query,passages)
        self.assertIsNone(validate_pairs('q',[]))
        with self.assertRaises(ValueError):self.service.rerank('q',scorer,mode='invalid')

    def test_hybrid_rejects_corrupt_channel_candidates_before_fusion(self):
        from unit.test_retrieval import TestEncoder
        from saturn_ai.retrieval.dense import QdrantIndex
        dense=QdrantIndex(self.snapshot,TestEncoder())
        self.service.publish(IndexSet(self.snapshot,self.index,dense))
        corruptions=[lambda r:r+r[:1],lambda r:(replace(r[0],snapshot_id='0'*64),)+r[1:],
                     lambda r:(replace(r[0],score=float('nan')),)+r[1:],
                     lambda r:(replace(r[0],rank=999),)+r[1:],
                     lambda r:(replace(r[0],chunk_id='invented'),)+r[1:]]
        try:
            for channel in (self.index,dense):
                original=channel.search
                for mutate in corruptions:
                    scorer=Scorer()
                    with self.subTest(channel=type(channel).__name__,mutation=mutate), \
                         patch.object(channel,'search',side_effect=lambda *a:mutate(original(*a))):
                        with self.assertRaises(ValueError):self.service.rerank('RS-485',scorer)
                    self.assertEqual(scorer.seen,[])
        finally:dense.close()
