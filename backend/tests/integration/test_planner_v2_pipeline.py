"""V2 integration on authored schema/calibration examples, never blind payload."""
from dataclasses import replace
import unittest
from unittest.mock import patch
from unit.test_evidence_gate import prepared,power_snapshot,candidates
from unit.test_reranking import Scorer
from saturn_ai.providers import FakeLLMProvider
from saturn_ai.domain import Claim
from saturn_ai.snapshots import SnapshotCatalog
from saturn_ai.retrieval.lexical import BM25Index
from saturn_ai.retrieval.service import RetrievalService,IndexSet
from saturn_ai.grounding.projections import build_projections
from saturn_ai.grounding.planner_v2 import plan_v2
from saturn_ai.grounding.v2_contracts import EvidenceNeed,SourceConstraints,QueryPlanV2
from saturn_ai.grounding.gate_v2 import evaluate_v2
from saturn_ai.grounding.application_v2 import GroundedConsultantV2


class V2GateTests(unittest.TestCase):
    def setUp(self):
        self.snapshot=prepared();self.projections=build_projections(self.snapshot);self.catalog=SnapshotCatalog(self.snapshot.registry)

    def evaluate(self,question,selected):
        return evaluate_v2(plan_v2(question,self.snapshot,self.projections),self.snapshot,candidates(self.snapshot,selected),self.catalog,self.projections)

    def chunk(self,source,field):
        return next(c for c in self.snapshot.chunks if c.source_id==source and c.chunk.field_path==field)

    def test_missing_second_need_never_becomes_partial_answer(self):
        power=self.chunk('synthetic:products/edu-410','power')
        result=self.evaluate('Питание и интерфейсы EDU-410?',[power])
        self.assertNotEqual(result.state,'sufficient')
        interface=[c for c in self.snapshot.chunks if c.source_id==power.source_id and c.chunk.field_path.startswith('interfaces[')]
        result=self.evaluate('Питание и интерфейсы EDU-410?',[power]+interface)
        self.assertEqual(result.state,'sufficient');self.assertEqual(len(result.bindings),2)

    def test_wrong_row_or_source_scope_is_not_an_answer(self):
        table=next(c for c in self.snapshot.chunks if c.source_id=='synthetic:pages/edu-specs' and '|' in c.chunk.text)
        power=self.chunk('synthetic:products/edu-410','power')
        self.assertEqual(self.evaluate('Питание EDU-420 по таблице?',[table]).state,'sufficient')
        self.assertNotEqual(self.evaluate('Питание EDU-420 по таблице?',[power]).state,'sufficient')
        self.assertNotEqual(self.evaluate('Питание EDU-410 по таблице в руководстве?',[table]).state,'sufficient')
        forged=replace(self.projections[0],value='999')
        plan=plan_v2('Питание EDU-410?',self.snapshot,self.projections)
        with self.assertRaises(ValueError):evaluate_v2(plan,self.snapshot,candidates(self.snapshot,[power]),self.catalog,(forged,)+self.projections[1:])

    def test_refs_are_backend_metadata_and_manual_anchor_is_same_source(self):
        page=next(c for c in self.snapshot.chunks if c.source_id=='synthetic:pdf:edu-410-manual' and c.chunk.page_start==2)
        result=self.evaluate('Найдите руководство EDU-410.',[page])
        self.assertEqual(result.state,'sufficient');ref=result.bindings[0].reference
        self.assertEqual(ref.source_id,page.source_id);self.assertEqual(ref.page,1);self.assertEqual(len(result.anchor_ids),1)
        self.catalog.revoke(page.source_id)
        self.assertNotEqual(self.evaluate('Найдите руководство EDU-410.',[page]).state,'sufficient')

    def test_scalar_and_set_disagreement_fail_without_union(self):
        for values,question in [(['24 В постоянного тока','12 В постоянного тока'],'Питание EDU-410?'),
            (['24 В постоянного тока\ninterfaces: [USB]','24 В постоянного тока\ninterfaces: [RS-485]'],'Интерфейсы EDU-410?')]:
            snapshot=power_snapshot(values);projections=build_projections(snapshot);plan=plan_v2(question,snapshot,projections)
            field='power' if 'Питание' in question else 'interfaces'
            chunks=[c for c in snapshot.chunks if c.chunk.field_path.split('[')[0]==field]
            result=evaluate_v2(plan,snapshot,candidates(snapshot,chunks),SnapshotCatalog(snapshot.registry),projections)
            self.assertEqual(result.state,'conflict')


class V2ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.snapshot=prepared();self.service=RetrievalService(SnapshotCatalog(self.snapshot.registry))
        self.service.publish(IndexSet(self.snapshot,BM25Index(self.snapshot)))
        self.provider=FakeLLMProvider();self.app=GroundedConsultantV2(self.service,Scorer(),self.provider,mode='lexical')

    def test_multi_field_and_named_spec_and_verbatim_support(self):
        result=self.app.answer('Питание и интерфейсы EDU-410?')
        self.assertEqual(result.status,'answered');self.assertEqual(len(result.bindings),2)
        self.assertEqual({c.text for c in result.claims},{'24 В постоянного тока','interfaces: USB','interfaces: RS-485'})
        # Lexical test adapter has no Russian inflection semantics; planner morphology is tested separately.
        result=self.app.answer('Цифровые входы EDU-410?')
        self.assertEqual(result.status,'answered');self.assertIn('4',result.claims[0].text)

    def test_all_reference_does_not_call_provider_and_is_policy_checked(self):
        result=self.app.answer('Какой тип сущности у EDU-CONFIG?')
        self.assertEqual(result.status,'answered');self.assertEqual(result.references[0].value,'Software')
        self.assertEqual(result.claims,());self.assertEqual(self.provider.calls,[])
        self.service.catalog.revoke(result.references[0].source_id)
        self.assertNotEqual(self.app.answer('Какой тип сущности у EDU-CONFIG?').status,'answered')

    def test_omitted_forged_claim_and_mutation_cannot_pass(self):
        class Bad(FakeLLMProvider):
            def generate(self,request):return (Claim('Invented value',request.evidence[0].chunk_id),)
        result=GroundedConsultantV2(self.service,Scorer(),Bad(),mode='lexical').answer('Питание EDU-410?')
        self.assertEqual(result.reason_code,'unverified_answer')
        class Missing(FakeLLMProvider):
            def generate(self,request):return super().generate(request)[:1]
        result=GroundedConsultantV2(self.service,Scorer(),Missing(),mode='lexical').answer('Питание и интерфейсы EDU-410?')
        self.assertEqual(result.reason_code,'unverified_answer')

    def test_revocation_during_generation_and_capture_publication(self):
        service=self.service
        class Revoking(FakeLLMProvider):
            def generate(self,request):
                service.catalog.revoke('synthetic:products/edu-410');return super().generate(request)
        result=GroundedConsultantV2(service,Scorer(),Revoking(),mode='lexical').answer('Питание EDU-410?')
        self.assertEqual(result.reason_code,'source_revoked');self.assertEqual(result.sources,())
        self.setUp();alternate=power_snapshot(['12 В постоянного тока']);original=self.service._rerank
        def publish(indexes,*args,**kwargs):
            self.service.publish(IndexSet(alternate,BM25Index(alternate)));return original(indexes,*args,**kwargs)
        with patch.object(self.service,'_rerank',side_effect=publish):result=self.app.answer('Питание EDU-410?')
        self.assertEqual(result.status,'answered');self.assertEqual(result.snapshot_id,self.snapshot.snapshot_id)

    def test_unknown_negated_and_budget_are_not_provider_requests(self):
        for q in ['Питание EDU-999?','Не сообщай питание EDU-410.', 'Питание EDU-410 и обслуживание?']:
            self.assertNotEqual(self.app.answer(q).status,'answered')
        self.assertEqual(self.provider.calls,[])

    def test_review_explicit_qualifier_never_returns_different_interface(self):
        result=self.app.answer('Через какой интерфейс Ethernet настраивают EDU-410?')
        self.assertNotEqual(result.status,'answered')

    def test_open_features_and_non_count_units_do_not_satisfy_count(self):
        from unit.test_evidence_gate import power_snapshot
        for tail,q in [("features: [USB и другие]",'Функции EDU-410?')]+[
                (f"specs:\n  - name: Цифровые входы\n    value: '{v}'",'Сколько цифровых входов у EDU-410?') for v in ('4 V','4 A','4.5')]:
            snapshot=power_snapshot(['24 В постоянного тока\n'+tail]);service=RetrievalService(SnapshotCatalog(snapshot.registry))
            service.publish(IndexSet(snapshot,BM25Index(snapshot)))
            app=GroundedConsultantV2(service,Scorer(),FakeLLMProvider(),mode='lexical')
            with self.subTest(tail=tail):self.assertNotEqual(app.answer(q).status,'answered')

    def test_no_negation_refuses_whole_request_before_generation(self):
        for question in ('У EDU-410 нет питания?', 'Питание EDU-410 и нет интерфейсов EDU-420?'):
            with self.subTest(question=question):
                result=self.app.answer(question)
                self.assertEqual(result.status,'refused')
                self.assertEqual(result.claims,())
                self.assertEqual(result.sources,())
                self.assertEqual(result.references,())
        self.assertEqual(self.provider.calls,[])

    def test_protocol_literals_refuse_instead_of_returning_different_protocol(self):
        questions=('Какой протокол TCP у EDU-410?', 'Протокол Modbus TCP EDU-410?',
                   'Протокол RTU EDU-420?', 'Протокол Modbus EDU-410?',
                   'Протокол TCP и питание EDU-410?', 'Протокол EDU-410 и EDU-420 RTU?',
                   'Питание EDU-410 и протокол TCP EDU-420?')
        for question in questions:
            with self.subTest(question=question):
                result=self.app.answer(question)
                self.assertEqual(result.status,'refused')
                self.assertEqual(result.claims,())
                self.assertEqual(result.sources,())
                self.assertEqual(result.references,())
        self.assertEqual(self.provider.calls,[])

    def test_unqualified_protocol_questions_still_quote_canonical_protocol(self):
        for question,quote in (('Протокол EDU-410?','protocols: Modbus RTU'),
                               ('Протокол EDU-420?','protocols: Modbus TCP')):
            with self.subTest(question=question):
                result=self.app.answer(question)
                self.assertEqual(result.status,'answered')
                self.assertEqual([c.text for c in result.claims],[quote])

    def test_modification_requests_refuse_before_provider(self):
        for question in ('Можно ли поменять питание EDU-410?', 'Измени питание EDU-410?',
                         'Как изменить питание EDU-410?', 'Настрой питание EDU-410?',
                         'Как настроить питание EDU-410?', 'Измени назначение EDU-CONFIG?',
                         'Настрой интерфейс EDU-410?', 'Как настроить интерфейс EDU-410?',
                         'Какой интерфейс настроить EDU-410?'):
            with self.subTest(question=question):
                result=self.app.answer(question)
                self.assertEqual(result.status,'refused')
                self.assertEqual(result.claims,())
                self.assertEqual(result.sources,())
                self.assertEqual(result.references,())
        self.assertEqual(self.provider.calls,[])
