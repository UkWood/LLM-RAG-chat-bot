"""End-to-end canonical V3 contracts; no blinded evaluation payload."""
from dataclasses import replace
import unittest
from unit.test_evidence_gate import prepared
from unit.test_v3_evidence import Scorer3
from saturn_ai.snapshots import SnapshotCatalog
from saturn_ai.retrieval.service import RetrievalService,IndexSet
from saturn_ai.retrieval.lexical import BM25Index
from saturn_ai.providers import FakeLLMProvider
from saturn_ai.grounding.application_v3 import GroundedConsultantV3

class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.s=prepared();self.c=SnapshotCatalog(self.s.registry);self.service=RetrievalService(self.c)
        self.service.publish(IndexSet(self.s,BM25Index(self.s)));self.provider=FakeLLMProvider()
        self.app=GroundedConsultantV3(self.service,Scorer3(),self.provider,mode='lexical')
    def test_complete_multi_need_and_canonical_quotes_and_trace(self):
        r=self.app.answer('Питание EDU-410 и протокол EDU-420?')
        self.assertEqual(r.status,'answered');self.assertEqual(len(r.bindings),2);self.assertEqual(r.schema_version,3)
        canonical={c.chunk_id:c.chunk.text for c in self.s.chunks}
        self.assertTrue(all(c.text==canonical[c.chunk_id] for c in r.claims))
        self.assertEqual(r.trace['search_count'],2);self.assertLessEqual(r.trace['intent_pairs']+r.trace['pairs_scored'],110)
    def test_all_reference_bypasses_provider_and_mixed_reference_is_canonical(self):
        r=self.app.answer('Руководство EDU-410?');self.assertEqual(r.status,'answered');self.assertEqual(r.claims,())
        self.assertEqual(len(r.references),1);self.assertEqual(self.provider.calls,[])
        r=self.app.answer('Руководство EDU-410 и питание EDU-410?')
        self.assertEqual(r.status,'answered');self.assertTrue(r.claims);self.assertEqual(len(r.references),1)
    def test_guards_refuse_whole_request_without_provider(self):
        for q in ('Нет питания EDU-410?', 'Измени питание EDU-410?', 'Протокол TCP EDU-410?',
                  'Питание EDU-410 и рецепт борща?', 'Питание EDU-999?'):
            with self.subTest(q=q):
                r=self.app.answer(q);self.assertEqual(r.status,'refused');self.assertEqual(r.claims,());self.assertEqual(r.sources,())
        self.assertEqual(self.provider.calls,[])
    def test_provider_omission_and_policy_revocation_cannot_publish(self):
        class Missing(FakeLLMProvider):
            def generate(self,q):return super().generate(q)[:1]
        r=GroundedConsultantV3(self.service,Scorer3(),Missing(),mode='lexical').answer('Интерфейсы EDU-410?')
        self.assertEqual(r.reason_code,'unverified_answer')
        catalog=self.c
        class Revoking(FakeLLMProvider):
            def generate(self,q):
                catalog.revoke('synthetic:products/edu-410');return super().generate(q)
        r=GroundedConsultantV3(self.service,Scorer3(),Revoking(),mode='lexical').answer('Интерфейсы EDU-410?')
        self.assertEqual(r.status,'refused');self.assertEqual(r.claims,());self.assertEqual(r.sources,())
    def test_errors_are_errors_not_refusals(self):
        class Broken(Scorer3):
            def score_pairs(self,q,p):raise ValueError('test runtime')
        r=GroundedConsultantV3(self.service,Broken(),self.provider,mode='lexical').answer('Питание EDU-410?')
        self.assertEqual(r.status,'error');self.assertEqual(self.provider.calls,[])
