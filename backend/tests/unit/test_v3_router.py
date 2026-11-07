"""Custom schema examples only; never loads the V3 blind payload."""
from dataclasses import replace
import unittest
from unit.test_evidence_gate import prepared
from saturn_ai.snapshots import SnapshotCatalog
from saturn_ai.grounding.projections import build_projections
from saturn_ai.grounding.contracts import GateResult
from saturn_ai.grounding.v3_contracts import QueryPlanV3,IntentEntry
from saturn_ai.grounding.roles_v3 import parse_roles
from saturn_ai.grounding.router_v3 import IntentRouter,plan_v3
from saturn_ai.grounding.v3_config import load_v3_config


class PairModel:
    identity={'model_id':'test/intent','revision':'a'*40,'max_length':512}
    def __init__(self,scores=(9.,1.)):self.scores=list(scores);self.calls=0;self.length=20
    def pair_lengths(self,q,p):return [self.length]*len(p)
    def score_pairs(self,q,p):self.calls+=1;return self.scores[:len(p)]


class RouterTests(unittest.TestCase):
    def test_neural_order_abstention_and_errors(self):
        entries=(IntentEntry('power','','supply voltage'),IntentEntry('interfaces','','physical connection'))
        m=PairModel();r=IntentRouter(m);cfg=load_v3_config()[0]
        self.assertEqual(r.propose('electrical supply',entries,cfg).predicate,'power')
        m.scores=[4.,4.];self.assertIsInstance(r.propose('topic',entries,cfg),GateResult)
        m.scores=[float('nan'),1.]
        with self.assertRaises(ValueError):r.propose('topic',entries,cfg)
        m.scores=[1.]
        with self.assertRaises(ValueError):r.propose('topic',entries,cfg)

    def test_no_truncation_identity_drift_or_catalogue_overflow(self):
        e=(IntentEntry('power','','supply'),IntentEntry('interfaces','','interface'))
        m=PairModel();r=IntentRouter(m);cfg=load_v3_config()[0];m.length=513
        self.assertIsInstance(r.propose('topic',e,cfg),GateResult);self.assertEqual(m.calls,0)
        with self.assertRaises(ValueError):r.propose('topic',e*11,cfg)
        m.identity=dict(m.identity,revision='b'*40)
        with self.assertRaises(ValueError):r.propose('topic',e,cfg)

    def test_one_credible_low_margin_class_is_not_fake_ambiguity(self):
        e=(IntentEntry('power','','a'),IntentEntry('interfaces','','b'))
        result=IntentRouter(PairModel((.2,-.1))).propose('topic',e,load_v3_config()[0])
        self.assertEqual(result.state,'insufficient')


class RolesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.s=prepared();cls.p=build_projections(cls.s)
    def plan(self,q):return plan_v3(q,self.s,self.p,IntentRouter(PairModel()),load_v3_config()[0],SnapshotCatalog(self.s.registry))

    def test_exact_multi_needs_scopes_and_original_spans(self):
        q='Питание и интерфейсы EDU-420 по таблице?'
        clauses=parse_roles(q,self.s)
        self.assertEqual(len(clauses),2)
        self.assertTrue(all(c.entity_ids==('products/edu-420',) and c.constraints.representation=='markdown_table' for c in clauses))
        plan=self.plan(q);self.assertIsInstance(plan,QueryPlanV3)
        self.assertEqual({n.predicate for n in plan.needs},{'power','interfaces'})
        covered={i for span in plan.roles for i in range(span.start,span.end)}
        self.assertTrue(all(i in covered for i,c in enumerate(q) if not c.isspace()))
        p=self.plan('Питание EDU-410 по карточке и EDU-420 по таблице.')
        self.assertEqual([n.constraints.document_kind for n in p.needs],['product_card','any'])
        self.assertEqual(p.needs[1].constraints.representation,'markdown_table')

    def test_whole_query_operators_qualifiers_and_unicode_refuse(self):
        for q in ['У EDU-410 нет питания?', 'Измени питание EDU-410?', 'Можно ли поменять питание EDU-410?',
                  'Какой протокол TCP у EDU-410?', 'Протокол Modbus EDU-410?', 'Питание или интерфейсы EDU-410?',
                  'Питание EDU-410 и рецепт борща?', 'Питание EDU-410\u200b?', 'Питание EDU-410.5?',
                  'Какой интерфейс настроить EDU-410?', 'Питание EDU-410 для самолета?',
                  'Какая программа настраивает EDU-410?']:
            with self.subTest(q=q):self.assertNotIsInstance(self.plan(q),QueryPlanV3)
        self.assertEqual(self.plan('Питание EDU-41?').state,'ambiguous')
        self.assertNotIsInstance(self.plan('Питание EDU-999?'),QueryPlanV3)

    def test_specs_references_and_supported_lookup_actions(self):
        self.assertEqual(self.plan('Число цифровых входов EDU-410?').needs[0].selector,'цифровые входы')
        self.assertEqual(self.plan('Найдите руководство EDU-410.').needs[0].predicate,'document_reference')
        self.assertEqual(self.plan('Тип сущности EDU-CONFIG?').needs[0].predicate,'entity_type')
        self.assertEqual(self.plan('Какой программой изменить адрес контроллера через кабель USB?').needs[0].predicate,'purpose')
        self.assertEqual(self.plan('Через какой разъём настраивают EDU-410 рядом со стендом?').needs[0].predicate,'configuration_interface')

    def test_unbound_modifiers_and_multihead_topics_never_reach_router(self):
        for q in ('Беспроводные интерфейсы EDU-410?', 'Максимальное питание EDU-410?',
                  'Протокол PROFINET EDU-420?', 'Питание/интерфейсы EDU-410?',
                  'Питание протоколы EDU-410?', 'Интерфейсы по карточке в невесомости EDU-410?'):
            with self.subTest(q=q):self.assertIsInstance(parse_roles(q,self.s),GateResult)

    def test_declared_field_lookup_is_supported_but_empty_action_not_inherited(self):
        for q in ('Какое питание требуется EDU-410?', 'Какие протоколы поддерживает EDU-420?'):
            self.assertIsInstance(self.plan(q),QueryPlanV3)
        self.assertNotIsInstance(self.plan('Питание EDU-410 и поддерживает EDU-420?'),QueryPlanV3)
        self.assertNotIsInstance(self.plan('Питание EDU-410 и найдите EDU-420?'),QueryPlanV3)

    def test_declared_connector_and_scoped_training_lookup_roles(self):
        examples=(('Какие разъёмы предусмотрены у EDU-420?', 'interfaces'),
                  ('Каков статус учебного EDU-430?', 'status'),
                  ('Найдите учебное руководство EDU-410.', 'document_reference'))
        for q,predicate in examples:
            with self.subTest(q=q):
                plan=self.plan(q)
                self.assertIsInstance(plan,QueryPlanV3)
                self.assertEqual(plan.needs[0].predicate,predicate)
        for q in ('Питание EDU-410 и предусмотрены EDU-420?',
                  'Найдите беспроводное руководство EDU-410.',
                  'Каков статус резервного EDU-430?'):
            with self.subTest(q=q):self.assertIsInstance(parse_roles(q,self.s),GateResult)

    def test_typed_lookup_never_discards_remaining_qualifiers_or_topic(self):
        self.assertEqual(self.plan('К какому типу относится EDU-410?').needs[0].predicate,'entity_type')
        for q in ('К какому типу относится EDU-410 беспроводной?',
                  'К какому типу относится EDU-410 питание?',
                  'К какому типу относится EDU-410 PROFINET?'):
            with self.subTest(q=q):self.assertIsInstance(parse_roles(q,self.s),GateResult)

    def test_exact_noun_inflections_do_not_accept_distinct_compound_quantities(self):
        for q,predicate in (('Диапазон температуры EDU-410?', 'temperature_c'),
                            ('Найдите инструкцию EDU-410?', 'document_reference')):
            with self.subTest(q=q):self.assertEqual(self.plan(q).needs[0].predicate,predicate)
        for q in ('Температуропроводность EDU-410?', 'Температуростойкость EDU-410?',
                  'Найдите руководствоведение EDU-410?'):
            with self.subTest(q=q):self.assertIsInstance(parse_roles(q,self.s),GateResult)

    def test_designation_cannot_drop_adjacent_dangling_or_alternate_separators(self):
        self.assertEqual(self.plan('Питание EDU-410.').needs[0].predicate,'power')
        for q in ('Питание EDU-410-?', 'Питание EDU-410—?',
                  'Питание EDU-410—X?', 'Питание EDU-410/?'):
            with self.subTest(q=q):self.assertIsInstance(parse_roles(q,self.s),GateResult)

    def test_shared_entity_comparison_scope_must_not_be_guessed(self):
        p=self.plan('Питание EDU-410 и EDU-420 по таблице?')
        self.assertIsInstance(p,GateResult);self.assertEqual(p.state,'ambiguous')

    def test_prefix_consumption_preserves_entity_and_source_roles(self):
        q='Для EDU-420 назовите питание по карточке?'
        c=parse_roles(q,self.s)[0]
        self.assertEqual([q[r.start:r.end] for r in c.roles if r.role=='entity'],['EDU-420'])
        self.assertTrue(any(r.role=='source_constraint' for r in c.roles))

    def test_ambiguous_canonical_spec_stems_are_not_first_match(self):
        from saturn_ai.grounding.router_v3 import exact_intent
        e=(IntentEntry('spec','температура входа','a'),IntentEntry('spec','температура входов','b'))
        self.assertIsInstance(exact_intent('температуры входа',e),GateResult)

    def test_malformed_value_does_not_erase_its_known_spec_selector(self):
        from unit.test_evidence_gate import power_snapshot
        from saturn_ai.grounding.router_v3 import catalogue
        s=power_snapshot(["24 В постоянного тока\nspecs:\n  - name: Цифровые входы\n    value: '4 V'"])
        c=SnapshotCatalog(s.registry);p=build_projections(s)
        self.assertIn('цифровые входы',{e.selector for e in catalogue(s,p,c)})

    def test_other_physical_quantities_are_not_supply_voltage(self):
        for q in ('Мощность EDU-410?', 'Ток EDU-410?', 'Потребляемый ток EDU-420?'):
            with self.subTest(q=q):self.assertIsInstance(parse_roles(q,self.s),GateResult)


from unit.test_reranker_model import HAS_ONNX,source,profile
from pathlib import Path
import tempfile
@unittest.skipUnless(HAS_ONNX,'requires locked optional ONNX profile')
class TokenBudgetTests(unittest.TestCase):
    def test_verified_tokenizer_counts_before_truncation_without_changing_scorer(self):
        from saturn_ai.retrieval.reranker_model import prepare_local_reranker,LocalONNXReranker
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);files=source(root/'input');prepare_local_reranker(profile(),*files,root/'bundle')
            m=LocalONNXReranker(root/'bundle')
            self.assertEqual(m.pair_lengths('one',['two']),[5])
            self.assertGreater(m.pair_lengths('one',['two '*600])[0],512)
            r=IntentRouter(m).propose('one',(IntentEntry('power','','two '*600),),load_v3_config()[0])
            self.assertIsInstance(r,GateResult);self.assertEqual(r.reason,'intent_input_budget')
            self.assertEqual(m.score_pairs('one',['two']),[17.0])
