"""Checked local Qdrant dense adapter for one exact Saturn retrieval bundle.

No remote endpoints, network embeddings, automatic model downloads or global state.
"""
from dataclasses import FrozenInstanceError
from hashlib import sha256
from math import isfinite, sqrt, isclose
from numbers import Real
from pathlib import Path
from threading import RLock
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from ..ingestion.saturn_contracts import canonical_json, stable_id
from .saturn_channel import (
    CANDIDATE_LIMIT, MAX_DIMENSIONS, MAX_EMBEDDING_BATCH,
    MAX_VECTOR_VALUES, REPRESENTATION_VERSION,
)


def _normalize(vector, dimensions):
    if not hasattr(vector, "__len__") or len(vector) != dimensions:
        raise ValueError("Encoder vector dimensions mismatch")
    values = []
    for item in vector:
        if isinstance(item, bool) or not isinstance(item, Real) or not isfinite(float(item)):
            raise ValueError("Encoder vector contains non-finite/non-real value")
        values.append(float(item))
    norm = sqrt(sum(x*x for x in values))
    if not isfinite(norm) or norm == 0:
        raise ValueError("Encoder vector has zero/invalid norm")
    normalized = tuple(x/norm for x in values)
    if not all(isfinite(x) for x in normalized):
        raise ValueError("Encoder normalization overflow")
    return normalized


class _QdrantLifetime:
    """Active publication and in-flight search refs protect local Qdrant.

    close() is deferred if a published bundle or running reader retains it.
    A retired index closes only after its final reader releases its lease.
    """
    def __init__(self, client):
        self._client = client
        self._lock = RLock()
        self._refs = 0
        self._close_requested = False
        self._closed = False

    def retain(self):
        with self._lock:
            if self._closed:
                raise ValueError("Qdrant index already closed")
            self._refs += 1

    def release(self):
        with self._lock:
            if self._refs <= 0:
                raise RuntimeError("Unbalanced Qdrant index lease")
            self._refs -= 1
            self._maybe_close()

    def close(self):
        with self._lock:
            self._close_requested = True
            self._maybe_close()

    def _maybe_close(self):
        if self._refs == 0 and self._close_requested and not self._closed:
            self._closed = True
            self._client.close()

    def assert_open(self):
        with self._lock:
            if self._closed:
                raise ValueError("Qdrant index closed")

    @property
    def closed(self):
        with self._lock:
            return self._closed


class SaturnQdrantIndex:
    """Sealed local Qdrant adapter with deferred close and reader leases."""

    def __setattr__(self, name, value):
        if self.__dict__.get("_sealed", False):
            raise FrozenInstanceError("Published Qdrant index fields are immutable: "+name)
        object.__setattr__(self, name, value)

    def __init__(self, snapshot_id, records, encoder, *, path=None):
        self.snapshot_id = snapshot_id
        self.encoder = encoder
        self.backend_mode = "memory" if path is None else "path"
        self.dimensions = getattr(encoder, "dimensions", None)
        if type(self.dimensions) is not int or not 1 <= self.dimensions <= MAX_DIMENSIONS:
            raise ValueError("Invalid local embedding dimensions")
        if len(records)*self.dimensions > MAX_VECTOR_VALUES:
            raise ValueError("Local vector memory baseline exceeded")
        try:
            identity = canonical_json(encoder.identity)
        except (AttributeError, ValueError, TypeError):
            raise ValueError("Encoder must have canonical identity") from None
        if not isinstance(encoder.identity, dict) or not identity or len(identity) > 8000:
            raise ValueError("Invalid encoder identity")
        self._identity = identity
        self.encoder_hash = sha256(identity.encode("utf-8")).hexdigest()
        self._records = tuple(records)
        self.ids = tuple(r.evidence_id for r in records)
        if len(set(self.ids)) != len(self.ids) or any(r.snapshot_id != snapshot_id for r in records):
            raise ValueError("Dense snapshot/evidence identity mismatch")
        self.point_ids = tuple(str(uuid5(NAMESPACE_URL, "saturn-evidence-v1:"+i)) for i in self.ids)
        self._payloads = tuple(tuple(sorted({
            "snapshot_id": snapshot_id, "evidence_id": r.evidence_id,
            "evidence_type": r.evidence_type, "source_revision_id": r.source_revision_id,
            "entity_id": r.entity_id, "locator": r.locator, "canonical_url": r.url,
            "text_hash": r.text_hash, "encoder_hash": self.encoder_hash,
            "payload_hash": stable_id("saturn-qdrant-payload-v1",
                                       snapshot_id, r.evidence_id, r.text_hash, r.locator,
                                       r.source_revision_id, r.url),
        }.items())) for r in records)
        vectors = []
        for start in range(0, len(records), MAX_EMBEDDING_BATCH):
            texts = [r.text for r in records[start:start+MAX_EMBEDDING_BATCH]]
            encoded = encoder.encode_documents(texts)
            if not isinstance(encoded, (list, tuple)) or len(encoded) != len(texts):
                raise ValueError("Dense document encoding cardinality mismatch")
            vectors.extend(_normalize(v, self.dimensions) for v in encoded)
        self._vectors = tuple(vectors)
        self.content_hash = stable_id("saturn-dense-content-v1",
                                      snapshot_id, self.encoder_hash, self._payloads,
                                      self._vectors, REPRESENTATION_VERSION)
        self.collection = "saturn_"+snapshot_id[:16]+"_"+self.encoder_hash[:12]
        self._client = QdrantClient(":memory:") if path is None else QdrantClient(path=str(Path(path)))
        self._lifetime = _QdrantLifetime(self._client)
        try:
            if not self._client.collection_exists(self.collection):
                self._client.create_collection(self.collection, vectors_config=models.VectorParams(
                    size=self.dimensions, distance=models.Distance.COSINE))
                if self.point_ids:
                    for start in range(0, len(self.point_ids), 256):
                        self._client.upsert(
                            self.collection,
                            points=[models.PointStruct(
                                id=self.point_ids[i],
                                vector=list(self._vectors[i]),
                                payload=dict(self._payloads[i]),
                            ) for i in range(start, min(start+256, len(self.ids)))],
                            wait=True)
            self.validate()
        except Exception:
            self._client.close()
            raise
        object.__setattr__(self, "_sealed", True)

    def validate(self, records=None):
        self._lifetime.assert_open()
        # Independently bind every Qdrant point/payload to the canonical
        # SearchRecord corpus, not merely to an internally cached checksum.
        expected = self._records if records is None else tuple(records)
        if (expected != self._records or
                tuple(r.evidence_id for r in expected) != self.ids or
                any(r.snapshot_id != self.snapshot_id for r in expected)):
            raise ValueError("Qdrant/evidence canonical coverage mismatch")
        if self.point_ids != tuple(
                str(uuid5(NAMESPACE_URL, "saturn-evidence-v1:"+r.evidence_id))
                for r in expected):
            raise ValueError("Qdrant point IDs are not canonical")
        rebuilt_payloads = tuple(tuple(sorted({
            "snapshot_id": self.snapshot_id, "evidence_id": r.evidence_id,
            "evidence_type": r.evidence_type, "source_revision_id": r.source_revision_id,
            "entity_id": r.entity_id, "locator": r.locator, "canonical_url": r.url,
            "text_hash": r.text_hash, "encoder_hash": self.encoder_hash,
            "payload_hash": stable_id("saturn-qdrant-payload-v1",
                                       self.snapshot_id, r.evidence_id, r.text_hash, r.locator,
                                       r.source_revision_id, r.url),
        }.items())) for r in expected)
        if self._payloads != rebuilt_payloads:
            raise ValueError("Qdrant payloads differ from canonical evidence")
        if (canonical_json(self.encoder.identity) != self._identity or
                self.encoder.dimensions != self.dimensions or
                sha256(self._identity.encode("utf-8")).hexdigest() != self.encoder_hash):
            raise ValueError("Encoder identity or dimensions changed")
        if self.content_hash != stable_id("saturn-dense-content-v1",
                self.snapshot_id, self.encoder_hash, self._payloads,
                self._vectors, REPRESENTATION_VERSION):
            raise ValueError("Dense artifact identity drift")
        config = self._client.get_collection(self.collection).config.params.vectors
        if config.size != self.dimensions or config.distance != models.Distance.COSINE:
            raise ValueError("Qdrant collection vector configuration mismatch")
        found = {}
        offset = None
        while True:
            points, offset = self._client.scroll(
                self.collection, limit=256, offset=offset, with_payload=True,
                with_vectors=True)
            for point in points:
                key = str(point.id)
                if key in found:
                    raise ValueError("Duplicate Qdrant point")
                found[key] = point
            if len(found) > len(self.point_ids):
                raise ValueError("Qdrant has extra points")
            if offset is None:
                break
        if set(found) != set(self.point_ids):
            raise ValueError("Qdrant missing/extra stored points")
        for pid, payload, expected in zip(self.point_ids, self._payloads, self._vectors):
            actual = found[pid]
            if actual.payload != dict(payload):
                raise ValueError("Qdrant payload identity/hash mismatch")
            v = _normalize(actual.vector, self.dimensions)
            if not all(isclose(x, y, abs_tol=1e-6, rel_tol=1e-6)
                       for x, y in zip(v, expected)):
                raise ValueError("Qdrant stored vectors differ from manifest")

    def search(self, query, allowed):
        self.validate()
        allowed_points = [pid for pid, eid in zip(self.point_ids, self.ids) if eid in allowed]
        if not allowed_points:
            return ()
        q = _normalize(self.encoder.encode_query(query), self.dimensions)
        filt = models.Filter(must=[
            models.HasIdCondition(has_id=allowed_points),
            models.FieldCondition(key="snapshot_id",
                                  match=models.MatchValue(value=self.snapshot_id)),
            models.FieldCondition(key="encoder_hash",
                                  match=models.MatchValue(value=self.encoder_hash)),
        ])
        points = self._client.query_points(
            self.collection, query=list(q), query_filter=filt,
            limit=len(allowed_points), with_payload=True).points
        # Qdrant performs the actual filtered nearest-neighbor lookup and
        # returns the canonical IDs. Validate complete bounded coverage first.
        # Its float32 scores may drift across equal queries near a rounding
        # boundary, so compute stable cosine from the already-validated
        # *expected* normalized vectors instead of exposing Qdrant float32.
        by_id = dict(zip(self.ids, self._vectors))
        point_by_id = dict(zip(self.ids, self.point_ids))
        eligible = set(allowed) & set(by_id)
        seen = set()
        scored = []
        for point in points:
            payload = point.payload
            eid = payload.get("evidence_id") if isinstance(payload, dict) else None
            if (eid not in eligible or eid in seen or
                    str(point.id) != point_by_id[eid] or
                    not isfinite(float(point.score))):
                raise ValueError("Invalid Qdrant query candidate")
            seen.add(eid)
            cosine = round(sum(a * b for a, b in zip(q, by_id[eid])), 12)
            if not isfinite(cosine):
                raise ValueError("Non-finite deterministic cosine")
            scored.append((eid, cosine))
        if seen != eligible:
            raise ValueError("Qdrant query result coverage mismatch")
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return tuple(scored[:CANDIDATE_LIMIT])

    def _retain(self):
        self._lifetime.retain()

    def _release(self):
        self._lifetime.release()

    def close(self):
        """Request close; never interrupt active bundle or in-flight query."""
        self._lifetime.close()
