"""Publish real index instances atomically, then query with current policy gates."""
from dataclasses import dataclass
from threading import RLock
from ..snapshots import KnowledgeSnapshot, SnapshotCatalog, SnapshotBundle, _checked_bundle, build_snapshot
from .contracts import Candidate, SearchTrace
from .lexical import BM25Index
from .dense import QdrantIndex


@dataclass(frozen=True)
class IndexSet:
    snapshot: KnowledgeSnapshot
    lexical: BM25Index
    dense: QdrantIndex | None = None


class RetrievalService:
    def __init__(self, catalog: SnapshotCatalog):
        self.catalog = catalog
        self._active = None
        self._lock = RLock()

    def publish(self, indexes: IndexSet):
        if (not isinstance(indexes, IndexSet) or indexes.snapshot != build_snapshot(indexes.snapshot.ingestion, indexes.snapshot.registry)
                or indexes.lexical.snapshot != indexes.snapshot):
            raise ValueError('Index set snapshot mismatch')
        indexes.lexical.validate()
        if indexes.dense is not None:
            if indexes.dense.snapshot != indexes.snapshot:
                raise ValueError('Dense/lexical snapshots differ')
            indexes.dense.validate()
            _checked_bundle(SnapshotBundle(indexes.snapshot, indexes.dense.descriptor, indexes.lexical.descriptor))
        # Explicit lexical-only publication does not claim a ready dual-index bundle.
        with self._lock:
            self._active = indexes

    def capture(self):
        with self._lock:
            if self._active is None:
                raise LookupError('No active retrieval index')
            return self._active

    def search(self, query, *, mode='lexical', top_k=5):
        if mode not in ('lexical', 'dense', 'hybrid') or type(top_k) is not int or not 1 <= top_k <= 40:
            raise ValueError('Invalid retrieval mode/top_k')
        indexes = self.capture()
        if mode != 'lexical' and indexes.dense is None:
            raise ValueError('Dense index/model unavailable; no automatic fallback')
        allowed = frozenset(c.chunk_id for c in self.catalog.eligible_snapshot_chunks(indexes.snapshot, 'local_index'))
        lexical = indexes.lexical.search(query, allowed, 40) if mode != 'dense' else ()
        dense = indexes.dense.search(query, allowed, 40) if mode != 'lexical' else ()
        # Re-check after queries: a source may have been revoked while an adapter ran.
        current = frozenset(c.chunk_id for c in self.catalog.eligible_snapshot_chunks(indexes.snapshot, 'local_index'))
        lexical = tuple(c for c in lexical if c.chunk_id in current)
        dense = tuple(c for c in dense if c.chunk_id in current)
        if mode == 'hybrid':
            fused, by_id = {}, {}
            for candidates in (lexical, dense):
                for item in candidates:
                    fused[item.chunk_id] = fused.get(item.chunk_id, 0.0) + 1/(60+item.rank)
                    by_id[item.chunk_id] = item
            ranked = sorted(fused, key=lambda cid: (-fused[cid], cid))[:top_k]
            final = tuple(Candidate(cid, by_id[cid].source_id, indexes.snapshot.snapshot_id, fused[cid], rank, 'rrf')
                          for rank, cid in enumerate(ranked, 1))
        else:
            final = (lexical if mode == 'lexical' else dense)[:top_k]
        return SearchTrace(indexes.snapshot.snapshot_id, mode, lexical, dense, final)
