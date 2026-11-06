"""Locked group and bounded retrieval tests use custom canonical fixtures only."""
from dataclasses import replace
import unittest
from unit.test_evidence_gate import prepared,power_snapshot,candidates
from unit.test_v3_router import PairModel
from saturn_ai.snapshots import SnapshotCatalog
from saturn_ai.retrieval.lexical import BM25Index
from saturn_ai.retrieval.service import RetrievalService,IndexSet
from saturn_ai.grounding.projections import build_projections
from saturn_ai.grounding.router_v3 import IntentRouter,plan_v3
from saturn_ai.grounding.v3_config import load_v3_config
from saturn_ai.grounding.v3_contracts import EvidenceSelectionV3
from saturn_ai.grounding.evidence_v3 import select_v3,evaluate_v3
from saturn_ai.grounding.retrieval_v3 import retrieve_v3

class Scorer3:
    identity={'max_length':512,'model_id':'test/contracts','revision':'a'*40}
    def pair_lengths(self,q,p):return [20]*len(p)
    def score_pairs(self,q,p):return [float(len(p)-i) for i in range(len(p))]

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.s=prepared();self.p=build_projections(self.s);self.c=SnapshotCatalog(self.s.registry)
        self.service=RetrievalService(self.c);self.service.publish(IndexSet(self.s,BM25Index(self.s)))
    def plan(self,q,s=None,c=None):
        s=s or self.s;c=c or self.c
        return plan_v3(q,s,build_projections(s),IntentRouter(PairModel()),load_v3_config()[0],c)
    def pool(self,source,field):return candidates(self.s,[c for c in self.s.chunks if c.source_id==source and c.chunk.field_path.startswith(field)])
    def test_exact_complete_group_is_locked_not_reselected(self):
        plan=self.plan('Интерфейсы EDU-410?');pool=self.pool('synthetic:products/edu-410','interfaces[')
        selection=select_v3(plan,self.s,pool,self.c,self.p)
        self.assertIsInstance(selection,EvidenceSelectionV3)
        self.assertEqual(len(selection.options[0].projection_ids),2)
        self.assertEqual(evaluate_v3(plan,selection,self.s,self.c,self.p).state,'sufficient')
        partial=replace(selection.options[0],projection_ids=selection.options[0].projection_ids[:1])
        with self.assertRaises(ValueError):evaluate_v3(plan,replace(selection,options=(partial,)),self.s,self.c,self.p)
        with self.assertRaises(ValueError):evaluate_v3(replace(plan,planner_revision='bad'),selection,self.s,self.c,self.p)
    def test_missing_group_source_scope_and_caps_refuse(self):
        plan=self.plan('Питание и интерфейсы EDU-410?');pool=self.pool('synthetic:products/edu-410','power')
        self.assertNotEqual(select_v3(plan,self.s,pool,self.c,self.p).state,'sufficient')
        pool=candidates(self.s,[c for c in self.s.chunks if c.source_id=='synthetic:products/edu-410'])
        self.assertEqual(select_v3(plan,self.s,pool,self.c,self.p,limits={'states':0}).reason,'evidence_selection_budget')
        manual_table=self.plan('Питание EDU-410 по таблице в руководстве?')
        self.assertNotEqual(select_v3(manual_table,self.s,pool,self.c,self.p).state,'sufficient')
    def test_conflict_and_current_revocation_are_not_score_choices(self):
        s=power_snapshot(['12 В постоянного тока','24 В постоянного тока']);c=SnapshotCatalog(s.registry)
        plan=self.plan('Питание EDU-410?',s,c)
        r=select_v3(plan,s,candidates(s,s.chunks),c,build_projections(s))
        self.assertEqual(r.state,'conflict')
        plan=self.plan('Питание EDU-410?');pool=self.pool('synthetic:products/edu-410','power')
        selection=select_v3(plan,self.s,pool,self.c,self.p);self.c.revoke('synthetic:products/edu-410')
        self.assertNotEqual(evaluate_v3(plan,selection,self.s,self.c,self.p).state,'sufficient')
    def test_reference_anchor_is_same_retrieved_manual_and_total_cap_one(self):
        pages=[c for c in self.s.chunks if c.chunk.page_start==2]
        pool=candidates(self.s,pages)
        plan=self.plan('Руководство EDU-410?');selection=select_v3(plan,self.s,pool,self.c,self.p)
        self.assertEqual(len(selection.anchors),1)
        r=evaluate_v3(plan,selection,self.s,self.c,self.p);self.assertEqual(r.state,'sufficient')
        plan=self.plan('Руководство EDU-410 и руководство EDU-420?')
        self.assertNotEqual(select_v3(plan,self.s,pool,self.c,self.p).state,'sufficient')
    def test_per_need_retrieval_uses_captured_index_and_finite_canonical_pool(self):
        plan=self.plan('Питание EDU-410 и протокол EDU-420?')
        captured=self.service.capture();pool,trace=retrieve_v3(self.service,captured,plan,'lookup',Scorer3(),mode='lexical')
        self.assertEqual(trace['search_count'],2);self.assertLessEqual(len(pool),30)
        self.assertEqual(trace['pairs_scored'],len(pool));self.assertTrue(all(c.snapshot_id==self.s.snapshot_id for c in pool))
        selection=select_v3(plan,self.s,pool,self.c,self.p)
        self.assertEqual(evaluate_v3(plan,selection,self.s,self.c,self.p).state,'sufficient')
