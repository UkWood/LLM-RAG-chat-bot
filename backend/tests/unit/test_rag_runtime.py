"""Persisted index/runtime boundaries; model kernels are controlled test dependencies."""
from dataclasses import asdict
from io import StringIO
from contextlib import redirect_stdout
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from saturn_ai.publication.policy import PublicationPolicy
from saturn_ai.publication.store import PublicationStore,atomic_json
from saturn_ai.publication.refresh import RefreshController
from saturn_ai.publication.fetch import Fetched
from saturn_ai.retrieval.lexical import BM25Index
from saturn_ai.retrieval.dense import QdrantIndex
from unit.test_retrieval import TestEncoder
from unit.test_rag_application import Scorer,Model

ROOT='https://example.invalid/site/'
class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.policy=PublicationPolicy(ROOT,cloud_allowed=True)
        self.store=PublicationStore(self.root/'store',self.policy)
        self.encoder=TestEncoder()
        def build(snapshot,directory):
            lexical=BM25Index(snapshot);dense=QdrantIndex(snapshot,self.encoder,path=directory/'dense')
            try:atomic_json(directory/'index.json',dict(mode='hybrid',embedding=self.encoder.identity,
                lexical=asdict(lexical.descriptor),dense=asdict(dense.descriptor)))
            finally:dense.close()
        fetch=lambda url,kind:Fetched(url,'<main>Блок А. Напряжение 24 В.</main>'.encode(),'text/html',200)
        self.assertEqual(RefreshController(self.policy,self.store,fetch,index_builder=build).run()['status'],'completed')
        self.directory=self.root/'store'/'versions'/self.store.capture().snapshot_id
        self.patchers=[patch('saturn_ai.evaluation.reranking.load_embedding',return_value=(self.encoder,{})),
            patch('saturn_ai.retrieval.reranker_model.load_semantic_reranker',return_value=(Scorer(),{}))]
        for p in self.patchers:p.start();self.addCleanup(p.stop)
    def load(self,model):
        from saturn_ai.rag.runtime import load_runtime
        return load_runtime(self.store,self.root/'model',self.root/'reranker',model)
    def model(self):
        cid=self.store.capture().chunks[0].chunk_id
        return Model([{'claims':[{'id':'power','text':'Напряжение 24 В.','evidence':[{'chunk_id':cid,'quote':'Напряжение 24 В.'}]}],'questions':[]},
            {'verdicts':[{'id':'power','status':'supported'}],'questions':[],'complete':True,'ambiguous':False}])
    def test_reopened_index_produces_cited_answer_and_stale_store_fails_closed(self):
        with self.load(self.model()) as runtime:
            answer=runtime.app.answer('Напряжение Блока А?')
            self.assertEqual(answer.status,'answered');self.assertEqual(answer.sources[0].url,ROOT)
            self.assertIsNotNone(answer.as_of)
            self.store.clock=lambda:10**15
            self.assertEqual(runtime.app.answer('Блок А?').reason_code,'publication_not_current')
    def test_changed_saved_identity_and_vectors_are_rejected_without_rebuild(self):
        path=self.directory/'index.json';original=path.read_text();value=json.loads(original)
        for key,new in [('embedding',{'kind':'different'}),('mode','lexical'),('lexical',{})]:
            bad=dict(value);bad[key]=new;atomic_json(path,bad)
            with self.assertRaises(ValueError):self.load(Model([]))
        path.write_text(original)
        dense=QdrantIndex(self.store.capture(),self.encoder,path=self.directory/'dense')
        dense._client.delete_collection(dense.collection);dense.close()
        with self.assertRaises(ValueError):self.load(Model([]))
        # Failed reader must not silently recreate the missing collection.
        from qdrant_client import QdrantClient
        client=QdrantClient(path=str(self.directory/'dense'))
        try:self.assertEqual(client.get_collections().collections,[])
        finally:client.close()
    def test_cli_ask_uses_public_operator_flags_and_outputs_safe_json(self):
        from saturn_ai.rag.__main__ import main
        policy_path=self.root/'policy.json';policy_path.write_text(json.dumps(asdict(self.policy)))
        args=['ask','--policy',str(policy_path),'--store',str(self.store.root),'--model-dir','unused',
            '--reranker-dir','unused','--query','Напряжение Блока А?']
        model=self.model();model.remote=True
        def invoke(extra):
            out=StringIO()
            with patch('saturn_ai.rag.__main__.OpenAICompatibleClient',return_value=model),patch(
                'saturn_ai.rag.__main__.ProviderSettings.from_env',return_value=object()),redirect_stdout(out):
                code=main(args+extra)
            return code,json.loads(out.getvalue())
        code,result=invoke([])
        self.assertEqual(code,2);self.assertEqual(result['reason_code'],'cloud_operator_flags_required')
        code,result=invoke(['--allow-cloud','--public-question'])
        self.assertEqual(code,0);self.assertEqual(result['status'],'answered');self.assertEqual(result['sources'][0]['url'],ROOT)
