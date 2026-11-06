"""Publish real index instances atomically, then query with current policy gates."""
from dataclasses import dataclass, replace
from threading import RLock
import json
from math import isfinite
from time import perf_counter
from ..snapshots import KnowledgeSnapshot, SnapshotCatalog, SnapshotBundle, _checked_bundle, build_snapshot
from .contracts import Candidate, SearchTrace, passage_text
from .reranking import RerankTrace, validate_pairs, checked_scores
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
        return self._search(self.capture(),query,mode=mode,top_k=top_k)

    def _search(self, indexes, query, *, mode, top_k):
        if mode not in ('lexical', 'dense', 'hybrid') or type(top_k) is not int or not 1 <= top_k <= 40:
            raise ValueError('Invalid retrieval mode/top_k')
        if mode != 'lexical' and indexes.dense is None:
            raise ValueError('Dense index/model unavailable; no automatic fallback')
        allowed = frozenset(c.chunk_id for c in self.catalog.eligible_snapshot_chunks(indexes.snapshot, 'local_index'))
        lexical = indexes.lexical.search(query, allowed, 40) if mode != 'dense' else ()
        dense = indexes.dense.search(query, allowed, 40) if mode != 'lexical' else ()
        # Validate raw channels before RRF can replace scores/identity or collapse IDs.
        mapping={c.chunk_id:c for c in indexes.snapshot.chunks}
        for channel,candidates in (('lexical',lexical),('dense',dense)):
            if not isinstance(candidates,(tuple,list)) or len(candidates)>40:
                raise ValueError('Invalid bounded retrieval channel')
            seen=set()
            for rank,candidate in enumerate(candidates,1):
                if (not isinstance(candidate,Candidate) or candidate.chunk_id not in mapping
                        or candidate.chunk_id in seen or candidate.source_id!=mapping[candidate.chunk_id].source_id
                        or candidate.snapshot_id!=indexes.snapshot.snapshot_id or candidate.channel!=channel
                        or type(candidate.rank) is not int or candidate.rank!=rank
                        or type(candidate.score) not in (int,float) or not isfinite(candidate.score)):
                    raise ValueError('Invalid raw retrieval channel identity/rank/score')
                seen.add(candidate.chunk_id)
        # Re-check after queries: a source may have been revoked while an adapter ran.
        current = frozenset(c.chunk_id for c in self.catalog.eligible_snapshot_chunks(indexes.snapshot, 'local_index'))
        lexical = tuple(replace(c,rank=rank) for rank,c in enumerate((c for c in lexical if c.chunk_id in current),1))
        dense = tuple(replace(c,rank=rank) for rank,c in enumerate((c for c in dense if c.chunk_id in current),1))
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

    def rerank(self, query, reranker, *, mode='hybrid'):
        validate_pairs(query,[])
        indexes=self.capture()
        trace=self._search(indexes,query,mode=mode,top_k=30)
        mapping={c.chunk_id:c for c in indexes.snapshot.chunks}
        seen=set()
        for rank,candidate in enumerate(trace.final,1):
            if (not isinstance(candidate,Candidate) or candidate.chunk_id not in mapping
                    or candidate.chunk_id in seen or candidate.source_id!=mapping[candidate.chunk_id].source_id
                    or candidate.snapshot_id!=indexes.snapshot.snapshot_id or candidate.rank!=rank
                    or not isfinite(candidate.score)):
                raise ValueError('Invalid reranking candidate identity/rank/score')
            seen.add(candidate.chunk_id)
        current=frozenset(c.chunk_id for c in self.catalog.eligible_snapshot_chunks(indexes.snapshot,'local_index'))
        candidates=tuple(replace(c,rank=rank) for rank,c in enumerate(
            (c for c in trace.final if c.chunk_id in current),1))
        passages=[passage_text(indexes.snapshot,mapping[c.chunk_id]) for c in candidates]
        validate_pairs(query,passages)
        identity=json.loads(json.dumps(reranker.identity,allow_nan=False))
        if not isinstance(identity,dict):raise ValueError('Invalid reranker identity')
        started=perf_counter()
        scores=checked_scores(reranker.score_pairs(query,passages),len(passages)) if passages else []
        scoring_seconds=perf_counter()-started
        current=frozenset(c.chunk_id for c in self.catalog.eligible_snapshot_chunks(indexes.snapshot,'local_index'))
        ordered=sorted(((c,float(score)) for c,score in zip(candidates,scores) if c.chunk_id in current),
                       key=lambda pair:(-pair[1],pair[0].rank,pair[0].chunk_id))
        scored=tuple(replace(c,score=score,rank=rank,channel='reranker') for rank,(c,score) in enumerate(ordered,1))
        baseline=replace(trace,final=trace.final[:5])
        return RerankTrace(indexes.snapshot.snapshot_id,mode,baseline,candidates,scored,scored[:5],identity,scoring_seconds)
