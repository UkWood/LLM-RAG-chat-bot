from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from unit.test_snapshots import prepared
from saturn_ai.snapshots import build_snapshot, SnapshotCatalog
from saturn_ai.retrieval.lexical import BM25Index, tokenize, bm25_term_score
from saturn_ai.retrieval.dense import QdrantIndex
from saturn_ai.retrieval.service import RetrievalService, IndexSet


class TestEncoder:
    """Known vectors for actual Qdrant contract tests, never semantic evaluation."""
    dimensions = 3
    identity = dict(kind='test_only', model='known-vectors-v1', revision='1', dimensions=3)

    def encode_documents(self, texts):
        return [[1.0, float('rs-485' in text.casefold()), float('usb' in text.casefold())] for text in texts]

    def encode_query(self, text):
        return [1.0, float('rs-485' in text.casefold()), float('usb' in text.casefold())]


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry, ingestion = prepared()
        cls.snapshot = build_snapshot(ingestion, cls.registry)

    def test_tokenization_preserves_designation_variants(self):
        self.assertEqual(tokenize('RS-485 DEMO-300.5 demo-300/999'), ['rs-485', 'demo-300.5', 'demo-300/999'])
        self.assertNotEqual(tokenize('БКД-ПК-РФ.2'), tokenize('БКД-ПК-RF.2'))

    def test_bm25_formula_and_ranking(self):
        self.assertAlmostEqual(bm25_term_score(2, 1, 3, 10, 10), 1.348640222891123, places=6)
        index = BM25Index(self.snapshot)
        allowed = frozenset(c.chunk_id for c in self.snapshot.chunks)
        candidates = index.search('RS-485', allowed, 5)
        self.assertTrue(candidates)
        self.assertEqual(candidates[0].source_id, 'synthetic:products/demo-300')
        self.assertEqual(candidates[0].rank, 1)
        self.assertEqual(candidates[0].channel, 'lexical')
        self.assertEqual(index.search('no_such_unique_vocabulary_zzzz', allowed, 5), ())
        self.assertEqual(index.search('RS-485', frozenset(), 5), ())
        self.assertEqual(candidates, index.search('RS-485', allowed, 5))

    def test_real_qdrant_query_filtered_to_allowed_point(self):
        dense = QdrantIndex(self.snapshot, TestEncoder())
        try:
            target = self.snapshot.chunks[0].chunk_id
            result = dense.search('RS-485', frozenset({target}), 5)
            self.assertEqual([c.chunk_id for c in result], [target])
            self.assertEqual(result[0].snapshot_id, self.snapshot.snapshot_id)
            self.assertEqual(dense.search('RS-485', frozenset(), 5), ())
            dense.validate()
        finally:
            dense.close()

    def test_qdrant_persistence_reopen_validates_same_artifacts(self):
        with tempfile.TemporaryDirectory() as path:
            first = QdrantIndex(self.snapshot, TestEncoder(), path=Path(path))
            expected = first.search('RS-485', frozenset(c.chunk_id for c in self.snapshot.chunks), 5)
            first.close()
            reopened = QdrantIndex(self.snapshot, TestEncoder(), path=Path(path))
            try:
                actual = reopened.search('RS-485', frozenset(c.chunk_id for c in self.snapshot.chunks), 5)
                self.assertEqual([(c.chunk_id, c.rank) for c in expected], [(c.chunk_id, c.rank) for c in actual])
                for before, after in zip(expected, actual):
                    self.assertAlmostEqual(before.score, after.score, places=6)
            finally:
                reopened.close()

    def test_malformed_embedding_outputs_fail(self):
        for vectors in [[], [[1, 2]], [[float('nan'), 0, 1]]*13, [[0, 0, 0]]*13]:
            class Broken(TestEncoder):
                def encode_documents(self, texts):
                    return vectors
            with self.subTest(vectors=str(vectors)[:30]):
                with self.assertRaises(ValueError):
                    QdrantIndex(self.snapshot, Broken())

    def test_partial_promotion_and_runtime_corruption_do_not_pass(self):
        from qdrant_client import models
        lexical = BM25Index(self.snapshot)
        dense = QdrantIndex(self.snapshot, TestEncoder())
        service = RetrievalService(SnapshotCatalog(self.registry))
        current = IndexSet(self.snapshot, lexical, dense)
        service.publish(current)
        try:
            dense._client.delete(dense.collection, points_selector=models.PointIdsList(points=[dense.point_ids[0]]), wait=True)
            with self.assertRaises(ValueError):
                service.publish(current)
            with self.assertRaises(ValueError):
                service.search('RS-485', mode='hybrid')
        finally:
            dense.close()

    def test_lexical_mode_does_not_silently_fake_dense(self):
        service = RetrievalService(SnapshotCatalog(self.registry))
        current = IndexSet(self.snapshot, BM25Index(self.snapshot))
        service.publish(current)
        trace = service.search('RS-485', mode='lexical')
        self.assertTrue(trace.final)
        self.assertEqual(trace.dense, ())
        self.assertEqual(trace.mode, 'lexical')
        with self.assertRaises(ValueError):
            service.search('RS-485', mode='hybrid')

    def test_revocation_applies_before_and_after_search(self):
        catalog = SnapshotCatalog(self.registry)
        service = RetrievalService(catalog)
        index = BM25Index(self.snapshot)
        service.publish(IndexSet(self.snapshot, index))
        target = 'synthetic:products/demo-300'
        self.assertTrue(any(c.source_id == target for c in service.search('RS-485').final))
        original = index.search
        def revoking(query, allowed, limit):
            result = original(query, allowed, limit)
            catalog.revoke(target)
            return result
        index.search = revoking
        self.assertFalse(any(c.source_id == target for c in service.search('RS-485').final))
        self.assertFalse(any(c.source_id == target for c in service.search('RS-485').lexical))

    def test_rrf_uses_ranks_and_is_deterministic(self):
        lexical = BM25Index(self.snapshot)
        dense = QdrantIndex(self.snapshot, TestEncoder())
        service = RetrievalService(SnapshotCatalog(self.registry))
        service.publish(IndexSet(self.snapshot, lexical, dense))
        try:
            result = service.search('RS-485', mode='hybrid')
            self.assertTrue(result.lexical and result.dense and result.final)
            first = result.final[0]
            ranks = [next((c.rank for c in channel if c.chunk_id == first.chunk_id), None)
                     for channel in (result.lexical, result.dense)]
            self.assertAlmostEqual(first.score, sum(1/(60+r) for r in ranks if r is not None))
            self.assertEqual(result, service.search('RS-485', mode='hybrid'))
        finally:
            dense.close()
