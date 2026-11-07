"""Diagnostic labels score retrieval only; model self-verdicts never grade quality."""
from pathlib import Path
import json
import unittest
from saturn_ai.rag.application import Consultant
from saturn_ai.retrieval.lexical import BM25Index
from saturn_ai.retrieval.service import RetrievalService,IndexSet
from saturn_ai.publication.snapshot import PublishedCatalog
from unit.test_rag_application import Model,Scorer

ROOT=Path(__file__).resolve().parents[3]
class DiagnosticTests(unittest.TestCase):
    def load(self):
        from saturn_ai.evaluation.rag_diagnostic import load_fixture
        return load_fixture(ROOT/'fixtures/rag-diagnostic',ROOT/'evaluation/datasets/grounded-rag-open-v1.json')
    def test_fixture_distribution_and_exact_gold_bindings(self):
        snapshot,dataset=self.load()
        from collections import Counter
        self.assertEqual(Counter(c['kind'] for c in dataset['cases']),dict(full=5,partial=4,missing=3,ambiguous=2,conflict=1))
        self.assertEqual(len(snapshot.sources),8)
        self.assertTrue(all(c['oracle_ids'] for c in dataset['cases'] if c['evidence']))
        self.assertTrue(all(not c['oracle_ids'] for c in dataset['cases'] if not c['evidence']))
    def test_retrieval_report_separates_missing_cases_and_leaves_human_quality_pending(self):
        from saturn_ai.evaluation.rag_diagnostic import run_diagnostic
        snapshot,dataset=self.load();service=RetrievalService(PublishedCatalog(lambda:{s.url:s.content_hash for s in snapshot.sources}))
        service.publish(IndexSet(snapshot,BM25Index(snapshot)))
        report=run_diagnostic(Consultant(service,Scorer(),Model([]),mode='lexical'),dataset,'retrieval')
        self.assertEqual(report['case_count'],15)
        self.assertEqual(report['generation_quality'],'not_run');self.assertEqual(report['human_review'],'pending')
        self.assertTrue(all(c['gold_quote_recall'] is None for c in report['cases'] if c['kind']=='missing'))
        self.assertEqual(report['identities']['snapshot_id'],snapshot.snapshot_id)
    def test_oracle_uses_gold_context_but_does_not_synthesize_expected_answer(self):
        from saturn_ai.evaluation.rag_diagnostic import run_diagnostic
        snapshot,dataset=self.load();service=RetrievalService(PublishedCatalog(lambda:{s.url:s.content_hash for s in snapshot.sources}))
        service.publish(IndexSet(snapshot,BM25Index(snapshot)))
        model=Model([{'claims':[],'questions':['Как уточнить питание?']},
            {'verdicts':[],'questions':['Как уточнить питание?'],'complete':False,'ambiguous':False}])
        dataset=dict(dataset,cases=dataset['cases'][:1])
        report=run_diagnostic(Consultant(service,None,model,mode='lexical'),dataset,'oracle')
        answer=report['cases'][0]['answer']
        self.assertEqual(answer['status'],'needs_support');self.assertEqual(answer['claims'],())
        self.assertEqual(report['generation_quality'],'pending_human_review')
        self.assertNotIn('expected',json.loads(model.requests[0]))
        self.assertNotIn('gaps',json.loads(model.requests[0]))
    def test_cli_records_concrete_missing_runtime_reason_without_network(self):
        from contextlib import redirect_stdout
        from io import StringIO
        import tempfile
        from unittest.mock import patch
        from saturn_ai.evaluation.rag_diagnostic import main
        with tempfile.TemporaryDirectory() as td:
            report=Path(td)/'report.json'
            args=['--mode','oracle','--fixture-root',str(ROOT/'fixtures/rag-diagnostic'),
                '--dataset',str(ROOT/'evaluation/datasets/grounded-rag-open-v1.json'),'--report',str(report)]
            with redirect_stdout(StringIO()):code=main(args)
            self.assertEqual(code,2);self.assertEqual(json.loads(report.read_text())['reason_code'],'fixture_review_required')
            with patch.dict('os.environ',{},clear=True),redirect_stdout(StringIO()):code=main(args+['--reviewed-fixtures'])
            self.assertEqual(code,2);self.assertEqual(json.loads(report.read_text())['reason_code'],'provider_configuration_required')
    def test_provider_failure_stops_run_and_marks_remaining_cases_not_run(self):
        from saturn_ai.evaluation.rag_diagnostic import run_diagnostic
        from saturn_ai.rag.provider import ProviderError
        snapshot,dataset=self.load();service=RetrievalService(PublishedCatalog(lambda:{s.url:s.content_hash for s in snapshot.sources}))
        service.publish(IndexSet(snapshot,BM25Index(snapshot)))
        model=Model([ProviderError('http_429')])
        report=run_diagnostic(Consultant(service,Scorer(),model,mode='lexical'),dataset,'oracle')
        self.assertEqual(report['infrastructure_errors'],1)
        self.assertEqual(len(model.requests),1)
        self.assertEqual(report['cases'][1]['status'],'not_run')
