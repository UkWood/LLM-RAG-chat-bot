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
