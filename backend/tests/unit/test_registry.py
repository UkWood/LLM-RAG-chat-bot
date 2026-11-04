from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import unittest

from saturn_ai.ingestion.registry import load_registry

ROOT = Path(__file__).resolve().parents[3]
COMMIT = 'a' * 40
CONTENT = b'synthetic bytes'
HASH = sha256(CONTENT).hexdigest()


def source(**changes):
    item = dict(source_id='synthetic:products/demo-300', source_kind='site_content',
                repository='UkWood/Saturn-Main-Site', source_commit=COMMIT,
                path='src/content/products/demo-300.md', observed_content_sha256=HASH,
                approved_content_sha256=HASH, title='DEMO-300', entity_type='Device',
                canonical_path='/products/demo-300/', visibility='PUBLIC', approval_state='approved',
                approval_id='synthetic-fixture-only', approved_by='synthetic-test-author-not-owner',
                approved_at='2026-11-04T00:00:00Z', publication_verified=True,
                cloud_allowed=False, allowed_usage=['local_index', 'local_generate'], reason='Synthetic test only')
    item.update(changes)
    return item


def manifest(*entries):
    return dict(schema_version=1, registry_status='synthetic_test_only', default_policy='deny',
                source_snapshot=COMMIT, entries=list(entries or [source()]))


def load(data):
    return load_registry(json.dumps(data).encode())


class RegistryTests(unittest.TestCase):
    def test_current_candidates_are_all_denied(self):
        registry = load_registry((ROOT / 'config/knowledge/public-sources.json').read_bytes())
        self.assertEqual(len(registry.entries), 8)
        self.assertTrue(all(not s.permits('local_index', HASH, COMMIT) for s in registry.entries))

    def test_exact_hash_commit_and_scope(self):
        record, = load(manifest()).entries
        self.assertTrue(record.permits('local_index', HASH, COMMIT))
        self.assertFalse(record.permits('local_index', '0'*64, COMMIT))
        self.assertFalse(record.permits('local_index', HASH, 'b'*40))
        self.assertFalse(record.permits('cloud_generate', HASH, COMMIT))
        self.assertFalse(record.permits('arbitrary', HASH, COMMIT))

    def test_closed_states_deny(self):
        for changes in [dict(visibility='INTERNAL', approval_state='pending'),
                        dict(visibility='UNKNOWN', approval_state='pending'),
                        dict(approval_state='pending'), dict(approval_state='revoked')]:
            changes.update(allowed_usage=[])
            record, = load(manifest(source(**changes))).entries
            self.assertFalse(record.permits('local_index', HASH, COMMIT))

    def test_invalid_schema_and_approval(self):
        for changes in [dict(extra='bad'), dict(publication_verified=1), dict(cloud_allowed='false'),
                        dict(visibility='INTERNAL'), dict(approved_content_sha256=None),
                        dict(approved_at='yesterday'), dict(approved_at='2026-11-04'),
                        dict(approval_id=None), dict(approved_by=''),
                        dict(allowed_usage=['local_index', 'local_index']),
                        dict(allowed_usage=[{}]), dict(allowed_usage=['cloud_generate']),
                        dict(observed_content_sha256='b'*64), dict(entity_type='Unknown'),
                        dict(source_commit='bad'), dict(path='src/content/../secret.md'),
                        dict(path='src/content/products/%2e%2e/secret.md'),
                        dict(path='src/content/products/demo.md/extra'),
                        dict(canonical_path='//evil.invalid/path'), dict(canonical_path='/x/../private/'),
                        dict(canonical_path='/x/%2e%2e/private/')]:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    load(manifest(source(**changes)))
        for data in [None, [], True, dict(manifest(), schema_version=True),
                     dict(manifest(), default_policy='allow'), dict(manifest(), entries=[None]),
                     manifest(source(), source())]:
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    load(data)

    def test_duplicate_keys_rejected(self):
        raw = json.dumps(manifest()).replace('"visibility": "PUBLIC"',
                                            '"visibility": "INTERNAL", "visibility": "PUBLIC"')
        with self.assertRaises(ValueError):
            load_registry(raw.encode())

    def test_external_approval_is_separate(self):
        raw = json.loads((ROOT / 'config/knowledge/public-sources.json').read_text())['entries'][4]
        raw.update(visibility='PUBLIC', approval_state='approved', publication_verified=True,
                   approval_id='synthetic-fixture-only', approved_by='synthetic-test-author-not-owner',
                   approved_at='2026-11-04T00:00:00Z', allowed_usage=['local_index'],
                   observed_content_sha256=HASH, approved_content_sha256=HASH, fetch_state='fetched')
        record, = load(manifest(raw)).entries
        self.assertTrue(record.permits('local_index', HASH))
        self.assertFalse(record.permits('local_generate', HASH))
        for url in ['http://www.mnppsaturn.ru/a.pdf', 'https://127.0.0.1/a.pdf',
                    'https://user@www.mnppsaturn.ru/a.pdf',
                    'https://www.mnppsaturn.ru/public/%2e%2e/a.pdf',
                    'https://www.mnppsaturn.ru:444/a.pdf',
                    'https://www.mnppsaturn.ru/public/a.pdf?token=secret']:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    load(manifest(dict(raw, url=url)))
        with self.assertRaises(ValueError):
            load(manifest(dict(raw, fetch_state='not_fetched')))


if __name__ == '__main__':
    unittest.main()
