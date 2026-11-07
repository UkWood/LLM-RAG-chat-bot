"""Actual Qdrant local index, with explicit external encoder and checked payloads."""
from math import isfinite, sqrt
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_URL
import numpy as np
from qdrant_client import QdrantClient, models
from ..ingestion.contracts import identifier
from ..snapshots import IndexDescriptor, build_snapshot
from .contracts import Candidate, REPRESENTATION_VERSION, passage_text


def normalized(vector, dimensions):
    if not isinstance(vector, (list, tuple, np.ndarray)) or len(vector) != dimensions:
        raise ValueError('Embedding dimension mismatch')
    if any(isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, float, np.number)) or not isfinite(float(v)) for v in vector):
        raise ValueError('Embedding must contain finite real numbers')
    length = sqrt(sum(float(v)**2 for v in vector))
    if not isfinite(length) or length == 0:
        raise ValueError('Embedding has invalid norm')
    return tuple(float(v)/length for v in vector)


class QdrantIndex:
    def __init__(self, snapshot, encoder, *, path: Path | None = None):
        from .validation import checked_snapshot
        checked_snapshot(snapshot)
        self.snapshot, self.encoder = snapshot, encoder
        if len(snapshot.chunks) > 10000:
            raise ValueError('Local baseline chunk limit')
        self.dimensions = encoder.dimensions
        if type(self.dimensions) is not int or not 1 <= self.dimensions <= 8192:
            raise ValueError('Invalid encoder dimensions')
        self._encoder_hash = identifier(encoder.identity)
        texts = [passage_text(snapshot, c) for c in snapshot.chunks]
        vectors = encoder.encode_documents(texts)
        if not isinstance(vectors, (list, tuple, np.ndarray)) or len(vectors) != len(texts):
            raise ValueError('Embedding batch cardinality mismatch')
        self._vectors = tuple(normalized(v, self.dimensions) for v in vectors)
        self.point_ids = tuple(str(uuid5(NAMESPACE_URL, c.chunk_id)) for c in snapshot.chunks)
        self._expected_payloads = tuple(dict(chunk_id=c.chunk_id, source_id=c.source_id, snapshot_id=snapshot.snapshot_id,
            source_hash=c.source_hash, policy_revision=c.policy_revision, visibility=c.visibility,
            approval_state=c.approval_state, allowed_usage=list(c.allowed_usage), text_hash=c.chunk.text_hash,
            encoder_hash=self._encoder_hash) for c in snapshot.chunks)
        self._descriptor = IndexDescriptor(snapshot.snapshot_id, 'dense', tuple(c.chunk_id for c in snapshot.chunks),
            'qdrant-local-v1', identifier('qdrant-local-v1', encoder.identity, REPRESENTATION_VERSION, 'tie-round-6', self._vectors))
        self.collection = 'snapshot_'+snapshot.snapshot_id[:16]+'_'+self._encoder_hash[:12]
        self._client = QdrantClient(path=str(path)) if path is not None else QdrantClient(':memory:')
        try:
            if not self._client.collection_exists(self.collection):
                self._client.create_collection(self.collection, vectors_config=models.VectorParams(
                    size=self.dimensions, distance=models.Distance.COSINE))
                if self.point_ids:
                    self._client.upsert(self.collection, points=[models.PointStruct(id=pid, vector=list(vector), payload=payload)
                        for pid, vector, payload in zip(self.point_ids, self._vectors, self._expected_payloads)], wait=True)
            self.validate()
        except Exception:
            self._client.close()
            raise

    @property
    def descriptor(self):
        return self._descriptor

    def validate(self):
        if identifier(self.encoder.identity) != self._encoder_hash or self.encoder.dimensions != self.dimensions:
            raise ValueError('Encoder configuration drift')
        config = self._client.get_collection(self.collection).config.params.vectors
        if config.size != self.dimensions or config.distance != models.Distance.COSINE:
            raise ValueError('Qdrant collection config mismatch')
        found, offset = [], None
        while True:
            points, offset = self._client.scroll(self.collection, limit=256, offset=offset, with_payload=True, with_vectors=True)
            found.extend(points)
            if len(found) > len(self.point_ids):
                raise ValueError('Qdrant contains extra points')
            if offset is None:
                break
        mapping = {str(p.id): p for p in found}
        if set(mapping) != set(self.point_ids):
            raise ValueError('Qdrant point coverage mismatch')
        for pid, expected, vector in zip(self.point_ids, self._expected_payloads, self._vectors):
            point = mapping[pid]
            actual = normalized(point.vector, self.dimensions)
            if point.payload != expected or not np.allclose(actual, vector, rtol=1e-6, atol=1e-6):
                raise ValueError('Qdrant payload/vector content mismatch')

    def search(self, query, allowed_ids, limit=40):
        self.validate()
        if not isinstance(query, str) or not query.strip() or len(query) > 4000 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Invalid query/limit')
        allowed = [pid for pid, c in zip(self.point_ids, self.snapshot.chunks) if c.chunk_id in allowed_ids]
        if not allowed:
            return ()
        vector = normalized(self.encoder.encode_query(query), self.dimensions)
        query_filter = models.Filter(must=[models.HasIdCondition(has_id=allowed),
            models.FieldCondition(key='snapshot_id', match=models.MatchValue(value=self.snapshot.snapshot_id)),
            models.FieldCondition(key='visibility', match=models.MatchValue(value='PUBLIC')),
            models.FieldCondition(key='approval_state', match=models.MatchValue(value='approved')),
            models.FieldCondition(key='policy_revision', match=models.MatchValue(value=self.snapshot.registry.revision))])
        points = self._client.query_points(self.collection, query=list(vector), query_filter=query_filter,
                                           limit=len(allowed), with_payload=True).points
        # Qdrant float32 serialization can shift near-ties by ~1e-7 on reopen.
        # Fetch the bounded allowed set before deterministic six-decimal tie ordering.
        scored = sorted(points, key=lambda p: (-round(float(p.score), 6), p.payload['chunk_id']))[:limit]
        return tuple(Candidate(p.payload['chunk_id'], p.payload['source_id'], self.snapshot.snapshot_id,
                               float(p.score), rank, 'dense') for rank, p in enumerate(scored, 1))

    def close(self):
        self._client.close()
