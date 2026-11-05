from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from saturn_ai.ingestion.contracts import identifier
from saturn_ai.ingestion.pipeline import build_fixture
from saturn_ai.ingestion.registry import load_registry
from saturn_ai.snapshots import build_snapshot, IndexDescriptor, SnapshotBundle, SnapshotCatalog

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / 'fixtures/ingestion'


def prepared(data=None, root=FIXTURES):
    raw = (FIXTURES / 'registry.json').read_bytes() if data is None else json.dumps(data).encode()
    registry = load_registry(raw)
    ingestion = build_fixture(root, registry, registry.source_snapshot)
    return registry, ingestion


def bundle(snapshot):
    ids = tuple(c.chunk_id for c in snapshot.chunks)
    return SnapshotBundle(snapshot,
                          IndexDescriptor(snapshot.snapshot_id, 'dense', ids, 'contract-only', 'a'*64),
                          IndexDescriptor(snapshot.snapshot_id, 'lexical', ids, 'contract-only', 'b'*64))


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.registry, self.ingestion = prepared()
        self.snapshot = build_snapshot(self.ingestion, self.registry)

    def test_payload_has_explicit_policy_and_provenance(self):
        self.assertEqual(len(self.snapshot.documents), 3)
        self.assertEqual(len(self.snapshot.chunks), 13)
        for chunk in self.snapshot.chunks:
            self.assertEqual(chunk.visibility, 'PUBLIC')
            self.assertEqual(chunk.approval_state, 'approved')
            self.assertEqual(chunk.policy_revision, self.registry.revision)
            self.assertEqual(chunk.snapshot_id, self.snapshot.snapshot_id)
            self.assertIn('local_index', chunk.allowed_usage)
            self.assertTrue(chunk.source_locator.startswith('src/content/'))
            self.assertEqual(chunk.source_hash, next(d.content_hash for d in self.snapshot.documents
                                                    if d.source_id == chunk.source_id))
        with self.assertRaises(FrozenInstanceError):
            self.snapshot.chunks[0].visibility = 'INTERNAL'

    def test_deterministic_identity_and_input_order(self):
        self.assertEqual(self.snapshot, build_snapshot(self.ingestion, self.registry))
        docs = tuple(reversed(self.ingestion.documents))
        changed = replace(self.ingestion, documents=docs,
                          snapshot_id=identifier(self.registry.revision, tuple(d.document_id for d in docs)))
        self.assertEqual(self.snapshot, build_snapshot(changed, self.registry))

    def test_malformed_ingestion_rejected(self):
        first = self.ingestion.documents[0]
        chunk = first.chunks[0]
        for changed in [replace(self.ingestion, registry_revision='0'*64),
                        replace(self.ingestion, snapshot_id='0'*64),
                        replace(self.ingestion, test_only=False),
                        replace(self.ingestion, documents=self.ingestion.documents[1:]),
                        replace(self.ingestion, documents=self.ingestion.documents+(first,)),
                        replace(self.ingestion, skipped_source_ids=('invented',)),
                        replace(self.ingestion, documents=(replace(first, content_hash='0'*64),)+self.ingestion.documents[1:]),
                        replace(self.ingestion, documents=(replace(first, locator='secret.md'),)+self.ingestion.documents[1:])]:
            with self.subTest(changed=changed.snapshot_id):
                with self.assertRaises(ValueError):
                    build_snapshot(changed, self.registry)
        for bad in [replace(chunk, text=chunk.text+'changed'), replace(chunk, source_id='invented'),
                    replace(chunk, chunk_id='0'*64), replace(chunk, document_id='0'*64),
                    replace(chunk, page_start=1, page_end=1)]:
            changed_doc = replace(first, chunks=(bad,)+first.chunks[1:])
            changed = replace(self.ingestion, documents=(changed_doc,)+self.ingestion.documents[1:])
            with self.subTest(bad=bad.chunk_id):
                with self.assertRaises(ValueError):
                    build_snapshot(changed, self.registry)

    def test_incomplete_or_wrong_index_bundle_cannot_promote(self):
        catalog = SnapshotCatalog(self.registry)
        with self.assertRaises(LookupError):
            catalog.capture()
        current = bundle(self.snapshot)
        catalog.activate(current)
        for bad in [replace(current, dense=replace(current.dense, snapshot_id='0'*64)),
                    replace(current, lexical=replace(current.lexical, chunk_ids=current.lexical.chunk_ids[:-1])),
                    replace(current, lexical=replace(current.lexical, kind='dense')),
                    replace(current, dense=replace(current.dense, chunk_ids=current.dense.chunk_ids+current.dense.chunk_ids[:1])),
                    replace(current, dense=replace(current.dense, implementation='')),
                    replace(current, dense=replace(current.dense, configuration_hash='bad'))]:
            with self.subTest(bad=bad.dense):
                with self.assertRaises(ValueError):
                    catalog.activate(bad)
                self.assertIs(catalog.capture(), current)

    def test_forged_snapshot_metadata_rejected(self):
        changed = replace(self.snapshot, chunks=(replace(self.snapshot.chunks[0], visibility='INTERNAL'),)
                          + self.snapshot.chunks[1:])
        catalog = SnapshotCatalog(self.registry)
        with self.assertRaises(ValueError):
            catalog.activate(bundle(changed))

    def test_deletion_capture_rollback_and_current_policy(self):
        catalog = SnapshotCatalog(self.registry)
        old = bundle(self.snapshot)
        catalog.activate(old)
        captured = catalog.capture()
        data = json.loads((FIXTURES/'registry.json').read_text())
        removed = data['entries'].pop()['source_id']
        new_registry, ingestion = prepared(data)
        new = bundle(build_snapshot(ingestion, new_registry))
        catalog.update_policy(new_registry)
        catalog.activate(new)
        self.assertIs(captured, old)
        self.assertNotEqual(old.snapshot.snapshot_id, new.snapshot.snapshot_id)
        self.assertFalse(any(c.source_id == removed for c in catalog.eligible_chunks(captured, 'local_generate')))
        catalog.activate(old)
        self.assertFalse(any(c.source_id == removed for c in catalog.eligible_chunks(catalog.capture(), 'local_generate')))
        self.assertEqual(catalog.eligible_chunks(old, 'cloud_generate'), ())
        catalog.revoke(self.snapshot.documents[0].source_id)
        catalog.update_policy(self.registry)
        catalog.activate(old)
        self.assertFalse(any(c.source_id == self.snapshot.documents[0].source_id
                             for c in catalog.eligible_chunks(old, 'local_generate')))

    def test_hash_update_invalidates_old_capture(self):
        catalog = SnapshotCatalog(self.registry)
        old = bundle(self.snapshot)
        catalog.activate(old)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'corpus'
            shutil.copytree(FIXTURES, root)
            data = json.loads((root/'registry.json').read_text())
            entry = data['entries'][0]
            path = root/entry['path']
            path.write_bytes(path.read_bytes()+b'\nNew synthetic revision.\n')
            digest = sha256(path.read_bytes()).hexdigest()
            entry.update(observed_content_sha256=digest, approved_content_sha256=digest)
            new_registry, ingestion = prepared(data, root)
            new = bundle(build_snapshot(ingestion, new_registry))
            catalog.update_policy(new_registry)
            catalog.activate(new)
            self.assertNotEqual(old.snapshot.snapshot_id, new.snapshot.snapshot_id)
            self.assertFalse(any(c.source_id == entry['source_id'] for c in catalog.eligible_chunks(old, 'local_index')))

    def test_policy_scope_update_blocks_generation(self):
        catalog = SnapshotCatalog(self.registry)
        current = bundle(self.snapshot)
        data = json.loads((FIXTURES/'registry.json').read_text())
        for entry in data['entries']:
            entry['allowed_usage'] = ['local_index']
        current_registry = load_registry(json.dumps(data).encode())
        catalog.update_policy(current_registry)
        self.assertEqual(catalog.eligible_chunks(current, 'local_generate'), ())
        self.assertEqual(len(catalog.eligible_chunks(current, 'local_index')), 13)
