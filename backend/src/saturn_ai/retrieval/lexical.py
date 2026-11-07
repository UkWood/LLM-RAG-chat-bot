"""Deterministic local BM25. No dataset/gold-label access or model downloads."""
from collections import Counter
from math import log
import re
from ..ingestion.contracts import identifier
from ..snapshots import IndexDescriptor, build_snapshot
from .contracts import Candidate, FIELD_ALIASES, REPRESENTATION_VERSION, passage_text


def tokenize(text):
    return re.findall(r'[^\W_]+(?:[-./][^\W_]+)*', text.casefold(), re.UNICODE)


def bm25_term_score(tf, df, count, length, average, k1=1.2, b=0.75):
    return log(1+(count-df+0.5)/(df+0.5)) * tf*(k1+1)/(tf+k1*(1-b+b*length/average))


class BM25Index:
    def __init__(self, snapshot):
        from .validation import checked_snapshot
        checked_snapshot(snapshot)
        self.snapshot = snapshot
        self._documents = self._expected_documents()
        self._descriptor = IndexDescriptor(snapshot.snapshot_id, 'lexical',
            tuple(c.chunk_id for c in snapshot.chunks), 'bm25-v1',
            identifier('bm25-v1', 1.2, 0.75, REPRESENTATION_VERSION, FIELD_ALIASES))

    def _expected_documents(self):
        return tuple((c.chunk_id, tuple(tokenize(passage_text(self.snapshot, c)))) for c in self.snapshot.chunks)

    @property
    def descriptor(self):
        return self._descriptor

    def validate(self):
        if (self._documents != self._expected_documents()
                or self.descriptor.snapshot_id != self.snapshot.snapshot_id
                or self.descriptor.chunk_ids != tuple(c.chunk_id for c in self.snapshot.chunks)):
            raise ValueError('BM25 artifact coverage/content mismatch')

    def search(self, query, allowed_ids, limit=40):
        self.validate()
        if not isinstance(query, str) or not query.strip() or len(query) > 4000 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Invalid query/limit')
        documents = [(cid, tokens) for cid, tokens in self._documents if cid in allowed_ids]
        if not documents:
            return ()
        terms = set(tokenize(query))
        frequencies = Counter(term for _, tokens in documents for term in set(tokens))
        average = sum(len(tokens) for _, tokens in documents)/len(documents)
        mapping = {c.chunk_id: c for c in self.snapshot.chunks}
        scored = []
        for cid, tokens in documents:
            counts = Counter(tokens)
            score = sum(bm25_term_score(counts[t], frequencies[t], len(documents), len(tokens), average)
                        for t in sorted(terms) if counts[t])
            if score > 0:
                scored.append((cid, float(score)))
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return tuple(Candidate(cid, mapping[cid].source_id, self.snapshot.snapshot_id, score, rank, 'lexical')
                     for rank, (cid, score) in enumerate(scored[:limit], 1))
