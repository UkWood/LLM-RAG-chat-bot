from collections import Counter
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import runpy
import tempfile
import unittest

from saturn_ai.ingestion.pipeline import build_fixture
from saturn_ai.ingestion.registry import load_registry
from saturn_ai.snapshots import build_snapshot
from saturn_ai.evaluation.dataset import validate_dataset, run_preflight

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT/'fixtures/evaluation'
DATASET = ROOT/'evaluation/datasets/synthetic-v1.json'
DISTRIBUTION = dict(exact_spec=5, exact_entity=4, paraphrase=4, multi_doc=3,
                    document_lookup=3, typo=2, no_answer=3, unknown_entity=2, injection=2, out_of_domain=2)


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_registry((CORPUS/'registry.json').read_bytes())
        cls.snapshot = build_snapshot(build_fixture(CORPUS, cls.registry, cls.registry.source_snapshot), cls.registry)
        cls.raw = DATASET.read_bytes()

    def test_authored_baseline_and_supported_gold_labels(self):
        dataset = validate_dataset(self.raw, self.snapshot)
        self.assertEqual(len(self.snapshot.documents), 10)
        self.assertEqual(sum(d.parser_version == 'pdf-v1' for d in self.snapshot.documents), 2)
        self.assertEqual(len(dataset.cases), 30)
        self.assertEqual(Counter(c.category for c in dataset.cases), DISTRIBUTION)
        self.assertEqual(Counter(c.split for c in dataset.cases), dict(calibration=20, held_out=10))
        self.assertEqual(Counter(c.expected_status for c in dataset.cases), dict(answered=20, refused=8, clarification=2))
        self.assertEqual({source for case in dataset.cases for source in case.expected_sources},
                         {d.source_id for d in self.snapshot.documents})
        self.assertTrue(all(not c.expected_sources for c in dataset.cases if c.expected_status != 'answered'))

    def test_duplicate_keys_and_malformed_root_rejected(self):
        for raw in [b'null', b'[]', self.raw.replace(b'"schema_version": 1', b'"schema_version": 1, "schema_version": 1')]:
            with self.subTest(raw=raw[:20]):
                with self.assertRaises(ValueError):
                    validate_dataset(raw, self.snapshot)

    def test_duplicate_cases_distribution_and_split_rejected(self):
        for mutate in [lambda d: d['cases'].append(d['cases'][0]),
                       lambda d: d['cases'].pop(),
                       lambda d: d['cases'][1].update(id='q001'),
                       lambda d: d['cases'][0].update(category='typo'),
                       lambda d: d['cases'][0].update(split='held_out'),
                       lambda d: d.update(registry_revision='0'*64),
                       lambda d: d.update(profile='real'),
                       lambda d: d.update(unexpected=True)]:
            data = json.loads(self.raw)
            mutate(data)
            with self.subTest(mutate=mutate):
                with self.assertRaises(ValueError):
                    validate_dataset(json.dumps(data).encode(), self.snapshot)

    def test_contradictory_and_unsupported_expectations_rejected(self):
        for change in [dict(must_answer=False), dict(must_refuse=True), dict(must_answer=1),
                       dict(expected_status='refused'), dict(expected_sources=['synthetic:invented']),
                       dict(expected_sources=['saturn:products/bkd-pk-rf-2']),
                       dict(expected_facts=['Invented Ethernet']), dict(expected_evidence=[]),
                       dict(tags=[{}]), dict(question=''), dict(unexpected='bad')]:
            data = json.loads(self.raw)
            data['cases'][0].update(change)
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    validate_dataset(json.dumps(data).encode(), self.snapshot)
        data = json.loads(self.raw)
        case = next(c for c in data['cases'] if c['expected_status']=='refused')
        case.update(expected_sources=['synthetic:products/edu-410'], expected_facts=['24 В'])
        with self.assertRaises(ValueError):
            validate_dataset(json.dumps(data).encode(), self.snapshot)

    def test_fact_page_and_field_must_match_actual_chunk(self):
        for change in [dict(page=99), dict(page=True), dict(field_path='invented'),
                       dict(text='Invented support for BACnet'), dict(source_id='synthetic:pdf:invented')]:
            data = json.loads(self.raw)
            case = next(c for c in data['cases'] if any(e['page'] is not None for e in c['expected_evidence']))
            case['expected_evidence'][0].update(change)
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    validate_dataset(json.dumps(data).encode(), self.snapshot)

    def test_forged_snapshot_rejected(self):
        snapshot = replace(self.snapshot, chunks=(replace(self.snapshot.chunks[0], visibility='INTERNAL'),)
                           + self.snapshot.chunks[1:])
        with self.assertRaises(ValueError):
            validate_dataset(self.raw, snapshot)

    def test_preflight_is_reproducible_and_does_not_claim_quality(self):
        first = run_preflight(CORPUS, DATASET)
        self.assertEqual(first, run_preflight(CORPUS, DATASET))
        self.assertEqual(first['document_count'], 10)
        self.assertEqual(first['case_count'], 30)
        self.assertEqual(first['quality_evaluation'], dict(retrieval='not_run', reranking='not_run',
                                                          grounding='not_run', source_hit_at_5=None))
        self.assertEqual(len(first['case_labels']), 30)
        self.assertNotIn('question', json.dumps(first['case_labels']))

    def test_pdf_source_fixtures_reproduce_from_authored_pages(self):
        from hashlib import sha256
        render = runpy.run_path(str(ROOT/'scripts/generate_synthetic_pdfs.py'))['render_manual']
        for manual in json.loads((CORPUS/'manuals.json').read_text())['manuals']:
            sid = 'synthetic:pdf:'+manual['slug']
            self.assertEqual((CORPUS/'pdf'/(sha256(sid.encode()).hexdigest()+'.pdf')).read_bytes(),
                             render(manual['pages']))


if __name__ == '__main__':
    unittest.main()
