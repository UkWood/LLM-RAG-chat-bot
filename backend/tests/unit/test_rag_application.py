"""Application contracts with a model double; these are not LLM quality scores."""
from dataclasses import replace
import unittest
from saturn_ai.publication.extract import PublishedSource
from saturn_ai.publication.snapshot import PublishedSnapshot,PublishedCatalog
from saturn_ai.retrieval.lexical import BM25Index
from saturn_ai.retrieval.service import RetrievalService,IndexSet
from saturn_ai.rag.application import Consultant,SUPPORT_TEXT
from saturn_ai.rag.provider import ProviderError

class Scorer:
    identity={'model_id':'test-pairs','revision':'a'*40}
    def score_pairs(self,q,passages):return [float(len(passages)-i) for i in range(len(passages))]
class Model:
    remote=False
    identity={'kind':'test-double'}
    def __init__(self,responses,hook=None):self.responses=list(responses);self.hook=hook;self.requests=[]
    def complete(self,system,user):
        self.requests.append(user)
        if self.hook:self.hook(len(self.requests))
        value=self.responses.pop(0)
        if isinstance(value,Exception):raise value
        return value

class ApplicationTests(unittest.TestCase):
    def setUp(self):
        a=PublishedSource('https://example.invalid/site/a', '<main>Блок А. Напряжение 24 В.</main>'.encode(),'text/html')
        b=PublishedSource('https://example.invalid/site/b', '<main>Блок А. Интерфейс Ethernet.</main>'.encode(),'text/html')
        self.snapshot=PublishedSnapshot((a,b),'p');self.current={s.url:s.content_hash for s in self.snapshot.sources}
        self.catalog=PublishedCatalog(lambda:dict(self.current));self.service=RetrievalService(self.catalog)
        self.queries=[]
        class RecordingIndex(BM25Index):
            def search(index,question,*args,**kwargs):self.queries.append(question);return super().search(question,*args,**kwargs)
        self.service.publish(IndexSet(self.snapshot,RecordingIndex(self.snapshot)))
        self.ids={c.source_id:c.chunk_id for c in self.snapshot.chunks}
    def draft(self):
        return {'claims':[{'id':'power','text':'Напряжение блока — 24 В.','evidence':[{'chunk_id':self.ids['https://example.invalid/site/a'],'quote':'Напряжение 24 В.'}]},
            {'id':'port','text':'Блок имеет интерфейс Ethernet.','evidence':[{'chunk_id':self.ids['https://example.invalid/site/b'],'quote':'Интерфейс Ethernet.'}]}], 'questions':[]}
    def verdict(self,*,complete=True,questions=None):
        return {'verdicts':[{'id':'power','status':'supported'},{'id':'port','status':'supported'}],
            'questions':questions or [],'complete':complete,'ambiguous':False}
    def app(self,model):return Consultant(self.service,Scorer(),model,mode='lexical')
    def test_natural_question_is_searched_and_partial_supported_answer_survives(self):
        question='Какие питание и интерфейсы у «Блок А», есть ли BACnet?'
        model=Model([self.draft(),self.verdict(complete=False,questions=['Поддерживает ли Блок А BACnet?'])])
        result=self.app(model).answer(question)
        self.assertEqual(self.queries,[question]);self.assertEqual(result.status,'partial')
        self.assertEqual(len(result.claims),2);self.assertEqual(len(result.sources),2)
        self.assertIn(SUPPORT_TEXT,result.text);self.assertEqual(result.text.count(SUPPORT_TEXT),1)
        self.assertIn('BACnet?',result.text);self.assertIn('24 В',result.text)
    def test_complete_verified_answer_has_backend_citations_and_no_support_gap(self):
        result=self.app(Model([self.draft(),self.verdict()])).answer('Блок А: питание и интерфейс?')
        self.assertEqual(result.status,'answered');self.assertNotIn(SUPPORT_TEXT,result.text)
        self.assertTrue(all(s.url.startswith('https://example.invalid/') for s in result.sources))
    def test_unknown_quote_and_invented_number_cannot_become_supported(self):
        draft=self.draft();draft['claims'][0]['text']='Напряжение — 48 В.'
        verify=self.verdict();verify['verdicts']=[{'id':'port','status':'supported'}]
        result=self.app(Model([draft,verify])).answer('Блок А: питание и интерфейс?')
        self.assertEqual(result.status,'partial');self.assertEqual([c.id for c in result.claims],['port'])
        self.assertNotIn('48 В',result.text)
        draft=self.draft();draft['claims'][0]['evidence'][0]['quote']='Не существующая цитата'
        result=self.app(Model([draft,verify])).answer('Блок А: питание и интерфейс?')
        self.assertEqual([c.id for c in result.claims],['port'])
    def test_semantically_wrong_true_quote_is_removed_by_verification(self):
        verdict=self.verdict(complete=False,questions=['Какое питание у блока?'])
        verdict['verdicts'][0]['status']='unsupported'
        result=self.app(Model([self.draft(),verdict])).answer('Блок А: питание и интерфейс?')
        self.assertEqual(result.status,'partial');self.assertEqual(len(result.claims),1)
    def test_revoked_source_is_not_sent_again_or_published(self):
        def revoke(call):
            if call==1:self.current.pop('https://example.invalid/site/a')
        verify=self.verdict(complete=False,questions=['Какое напряжение у блока?']);verify['verdicts']=[{'id':'port','status':'supported'}]
        model=Model([self.draft(),verify],hook=revoke)
        result=self.app(model).answer('Блок А: питание и интерфейс?')
        self.assertEqual([c.id for c in result.claims],['port'])
        self.assertNotIn('Напряжение 24 В.',model.requests[1]);self.assertNotIn('24 В',result.text)
    def test_revocation_during_verification_keeps_independent_claim_only(self):
        def revoke(call):
            if call==2:self.current.pop('https://example.invalid/site/a')
        result=self.app(Model([self.draft(),self.verdict()],hook=revoke)).answer('Блок А: питание и интерфейс?')
        self.assertEqual(result.status,'partial');self.assertEqual([c.id for c in result.claims],['port'])
    def test_provider_and_malformed_verifier_are_errors_not_missing_information(self):
        for responses in ([ProviderError('http_429')],[self.draft(),{'verdicts':[]} ]):
            result=self.app(Model(responses)).answer('Блок А?')
            self.assertEqual(result.status,'error');self.assertFalse(result.claims)
    def test_no_evidence_gives_question_and_support_without_calling_model(self):
        result=self.app(Model([])).answer('Где сведения о неизвестном XYZ999?')
        self.assertEqual(result.status,'needs_support');self.assertFalse(result.sources)
        self.assertIn('?',result.text);self.assertIn(SUPPORT_TEXT,result.text)
    def test_remote_call_requires_explicit_public_question_and_cloud_source_scope(self):
        model=Model([]);model.remote=True
        result=self.app(model).answer('Блок А?')
        self.assertEqual(result.status,'error');self.assertEqual(result.reason_code,'public_question_required')
        result=self.app(model).answer('Блок А?',public_question=True)
        self.assertEqual(result.status,'error');self.assertEqual(result.reason_code,'cloud_source_not_approved')

    def test_ambiguous_verdict_cannot_be_rendered_as_complete_answer(self):
        verdict=self.verdict();verdict['ambiguous']=True
        result=self.app(Model([self.draft(),verdict])).answer('Какой именно Блок А?')
        self.assertEqual(result.status,'partial');self.assertTrue(result.questions)

    def test_invalid_generation_schema_has_fixed_specific_code(self):
        result=self.app(Model([{'claims':'bad synthetic response','questions':[]}])).answer('Блок А?')
        self.assertEqual(result.status,'error');self.assertEqual(result.reason_code,'invalid_generation_response')
        self.assertNotIn('bad synthetic response',result.text)

    def test_invalid_verification_schema_has_fixed_specific_code(self):
        result=self.app(Model([self.draft(),{'verdicts':[]}])).answer('Блок А?')
        self.assertEqual(result.reason_code,'invalid_verification_response')

    def test_unexpected_retrieval_failure_does_not_expose_exception(self):
        from unittest.mock import patch
        with patch.object(self.service,'_rerank',side_effect=RuntimeError('private exception content')):
            result=self.app(Model([])).answer('Блок А?')
        self.assertEqual(result.reason_code,'retrieval_unavailable')
        self.assertNotIn('private exception content',str(result.to_dict()))

    def test_true_but_unrequested_facts_leave_only_the_requested_support_question(self):
        verdict=self.verdict(complete=False,questions=['Сколько стоит Блок А?'])
        for item in verdict['verdicts']:item['status']='irrelevant'
        result=self.app(Model([self.draft(),verdict])).answer('Сколько стоит Блок А?')
        self.assertEqual(result.status,'needs_support');self.assertFalse(result.claims);self.assertFalse(result.sources)
        self.assertNotIn('24 В',result.text);self.assertNotIn('Ethernet',result.text)
        self.assertEqual(result.questions,('Сколько стоит Блок А?',))

    def test_removing_unrequested_fact_does_not_turn_a_complete_answer_into_partial(self):
        verdict=self.verdict();verdict['verdicts'][1]['status']='irrelevant'
        result=self.app(Model([self.draft(),verdict])).answer('Какое питание у Блока А?')
        self.assertEqual(result.status,'answered');self.assertEqual([c.id for c in result.claims],['power'])
        self.assertFalse(result.questions);self.assertNotIn('Ethernet',result.text)
        self.assertEqual(len(result.sources),1)

    def test_relevant_partial_answer_survives_removal_of_extra_fact(self):
        verdict=self.verdict(complete=False,questions=['При какой температуре работает Блок А?'])
        verdict['verdicts'][1]['status']='irrelevant'
        result=self.app(Model([self.draft(),verdict])).answer('Какое питание и рабочая температура Блока А?')
        self.assertEqual(result.status,'partial');self.assertEqual([c.id for c in result.claims],['power'])
        self.assertNotIn('Ethernet',result.text);self.assertIn('температуре',result.questions[0])

    def test_mixed_requested_and_unrequested_statement_is_not_published(self):
        draft=self.draft();draft['claims']=draft['claims'][:1]
        draft['claims'][0]['text']='Напряжение блока 24 В; интерфейс Ethernet.'
        draft['claims'][0]['evidence'].append(self.draft()['claims'][1]['evidence'][0])
        verdict={'verdicts':[{'id':'power','status':'irrelevant'}],
            'questions':['Какое питание у Блока А?'],'complete':False,'ambiguous':False}
        result=self.app(Model([draft,verdict])).answer('Какое питание у Блока А?')
        self.assertFalse(result.claims);self.assertNotIn('Ethernet',result.text)
        self.assertEqual(result.status,'needs_support')

class NumericIdentifierTests(unittest.TestCase):
    def answer(self,text,quote,*,source=None):
        source=source or 'Контроллер Тест-17. Напряжение 24 В. Интерфейс RS-485.'
        a=PublishedSource('https://example.invalid/numeric/a',('<main>'+source+'</main>').encode(),'text/html')
        b=PublishedSource('https://example.invalid/numeric/b','<main>Другой-99. Напряжение 24 В.</main>'.encode(),'text/html')
        snapshot=PublishedSnapshot((a,b),'numeric-regression')
        service=RetrievalService(PublishedCatalog(lambda:{s.url:s.content_hash for s in snapshot.sources}))
        service.publish(IndexSet(snapshot,BM25Index(snapshot)))
        cid=next(c.chunk_id for c in snapshot.chunks if c.source_id==a.url)
        class Verifier(Model):
            def complete(model,system,user):
                import json
                payload=json.loads(user)
                if 'claims' in payload:
                    return {'verdicts':[{'id':c['id'],'status':'supported'} for c in payload['claims']],
                        'questions':[],'complete':bool(payload['claims']),'ambiguous':False}
                return {'claims':[{'id':'power','text':text,'evidence':[{'chunk_id':cid,'quote':quote}]}],'questions':[]}
        return Consultant(service,None,Verifier([]),mode='lexical').answer('Контроллер Тест-17: напряжение и интерфейс?',context_ids=(cid,))

    def test_identifier_in_cited_context_does_not_require_repeating_it_in_short_quote(self):
        result=self.answer('Напряжение Тест-17 составляет 24 В.','Напряжение 24 В.')
        self.assertEqual(result.status,'answered');self.assertEqual(len(result.claims),1)
        self.assertIn('Тест-17',result.text);self.assertEqual(len(result.sources),1)

    def test_backed_interface_identifier_in_quote_is_not_a_negative_quantity(self):
        result=self.answer('Тест-17 имеет интерфейс RS-485.','Интерфейс RS-485.')
        self.assertEqual(result.status,'answered');self.assertEqual(len(result.claims),1)

    def test_identifier_digits_cannot_license_invented_values_units_or_other_entities(self):
        for text,quote in [
            ('Напряжение Тест-17 составляет 17 В.','Напряжение 24 В.'),
            ('Напряжение Тест-17 составляет 48 В.','Напряжение 24 В.'),
            ('Напряжение Тест-17 составляет 24 мВ.','Напряжение 24 В.'),
            ('Напряжение Другой-99 составляет 24 В.','Напряжение 24 В.'),
            ('Напряжение Тест-170 составляет 24 В.','Напряжение 24 В.')]:
            with self.subTest(text=text):
                result=self.answer(text,quote)
                self.assertFalse(result.claims);self.assertEqual(result.status,'needs_support')

    def test_numeric_signs_still_require_exact_quote_support(self):
        for text,expected in [('Тест-17 работает при -20 °C.','answered'),('Тест-17 работает при 20 °C.','needs_support')]:
            with self.subTest(text=text):
                result=self.answer(text,'Температура -20 °C.',source='Тест-17. Температура -20 °C.')
                self.assertEqual(result.status,expected)

    def test_digits_in_an_interface_identifier_are_not_evidence_for_a_channel_count(self):
        result=self.answer('Тест-17 имеет 485 каналов.','Интерфейс RS-485.')
        self.assertFalse(result.claims);self.assertEqual(result.status,'needs_support')

    def test_unit_suffix_in_a_backed_product_identifier_is_not_a_measured_quantity(self):
        result=self.answer('Напряжение БП-12В составляет 24 В.','Напряжение 24 В.',
            source='БП-12В. Напряжение 24 В.')
        self.assertEqual(result.status,'answered');self.assertEqual(len(result.claims),1)
