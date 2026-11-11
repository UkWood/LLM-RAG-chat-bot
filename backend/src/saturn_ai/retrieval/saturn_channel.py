"""Saturn-specific, offline, channel-aware retrieval (stage 4B).

A retrieval bundle owns the exact verified snapshot and *all* of its indexes.
Legacy Registry/approval-based retrieval is intentionally not imported.
"""
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
import json
from math import isfinite, log
from threading import RLock
from types import MappingProxyType
import re
import warnings

from ..ingestion.saturn_contracts import canonical_json, stable_id
from ..saturn_knowledge_contracts import (
    DocumentMatch, SaturnKnowledgeSnapshot, SaturnSnapshotManager,
)

REPRESENTATION_VERSION = "saturn-evidence-representation/0.1.1"
TOKENIZER_VERSION = "saturn-technical-tokenizer/0.2.1"
ALIAS_VERSION = "saturn-explicit-dictionary-alias/0.1.0"
BM25_K1 = 1.2
BM25_B = 0.75
RRF_K = 60
CANDIDATE_LIMIT = 40
MAX_TOP_K = 40
MAX_QUERY_CHARS = 4000
MAX_RECORDS = 10000
MAX_RECORD_CHARS = 20000
MAX_TOTAL_CHARS = 2_000_000
MAX_DIMENSIONS = 8192
MAX_EMBEDDING_BATCH = 16
MAX_VECTOR_VALUES = 2_000_000
# Recognize an explicitly bounded set of directly attached engineering units.
# This is LEXICAL segmentation, not unit conversion or numeric inference.
# An unknown suffix stays an opaque identifier; code-like continuations
# ("12.5V-CTRL", "12.5V2") must not produce a numeric evidence hit.
# The full original evidence text is never rewritten.
_NUMBER = r"[+\-\u2212]?\d+(?:[.,]\d+)*"
_NUMERIC = _NUMBER + r"(?:(?:\.\.|…|–|—|-)\s*" + _NUMBER + r")?"
_ATTACHED_UNIT = (
    r"(?:мпа|кпа|бар|квт|кгц|мгц|mpa|kpa|bar|kv|mv|ma|kw|hz|°c|°f|па|вт|гц|в|а|v|a|w)"
)
# U+2212 in a recognized signed number is normalized to ASCII "-".
# Comma/dot decimals and explicit numeric ranges remain literal tokens.
# Longer unknown alphanumeric decimal designations are opaque, rather than
# silently split into guessed instrument properties.
_OPAQUE_DECIMAL_CODE = (
    r"(?<![\w])[+\-\u2212]?\d+[.,]\d+[^\W_]+(?:[-./][^\W_]+)*(?![\w])"
)
_TOKEN = re.compile(
    rf"(?<![\w])(?P<quantity>{_NUMBER})(?P<unit>{_ATTACHED_UNIT})(?![\w./-])"
    rf"|{_OPAQUE_DECIMAL_CODE}"
    rf"|(?<![\w]){_NUMERIC}(?![\w.,/-])"
    r"|°[cf](?![\w])|[^\W_]+(?:[-./][^\W_]+)*",
    re.UNICODE,
)


def tokenize(text: str) -> tuple[str, ...]:
    if not isinstance(text, str):
        raise TypeError("Search text must be a string")
    terms = []
    for match in _TOKEN.finditer(text.casefold()):
        quantity = match.group("quantity")
        if quantity is not None:
            # An adjacent recognized unit yields BOTH the literal numeric
            # search term and the unit. The source string itself is untouched.
            terms.extend((quantity.replace("\u2212", "-"), match.group("unit")))
        else:
            terms.append(match.group().replace("\u2212", "-"))
    return tuple(terms)


def _hash(value) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _valid_query(query, top_k, mode):
    if not isinstance(query, str) or not query.strip() or "\x00" in query or len(query) > MAX_QUERY_CHARS:
        raise ValueError("Invalid Saturn query")
    if type(top_k) is not int or not 1 <= top_k <= MAX_TOP_K:
        raise ValueError("Invalid top_k")
    if mode not in ("lexical", "dense", "hybrid"):
        raise ValueError("Invalid Saturn retrieval mode")


@dataclass(frozen=True)
class SearchRecord:
    evidence_id: str
    evidence_type: str
    snapshot_id: str
    source_revision_id: str
    entity_id: str | None
    locator: str
    url: str | None
    text: str
    text_hash: str
    pdf_bytes_sha256: str | None = None
    pdf_parser_version: str | None = None
    physical_page: int | None = None
    pdf_document_id: str | None = None
    pdf_link_source_revisions: tuple[str, ...] = ()
    pdf_owner_entity_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class DocumentRecord:
    match: DocumentMatch
    snapshot_id: str
    text: str
    text_hash: str


@dataclass(frozen=True)
class SaturnIndexManifest:
    snapshot_id: str
    corpus_hash: str
    representation_version: str
    tokenizer_version: str
    lexical_config_hash: str
    dictionary_fingerprints: tuple[tuple[str, str], ...]
    dense_encoder_hash: str | None
    qdrant_config: str | None
    evidence_count: int
    document_count: int
    evidence_coverage_hash: str
    document_coverage_hash: str
    lexical_content_hash: str
    document_content_hash: str
    dense_content_hash: str | None
    bundle_id: str


@dataclass(frozen=True)
class SaturnCandidate:
    evidence_id: str
    evidence_type: str
    entity_id: str | None
    source_revision_id: str
    locator: str
    canonical_url: str | None
    snapshot_id: str
    score: float
    rank: int
    channel: str


@dataclass(frozen=True)
class RankedDocument:
    match: DocumentMatch
    snapshot_id: str
    score: float
    rank: int


@dataclass(frozen=True)
class SaturnRetrievalResult:
    snapshot_id: str
    bundle_id: str
    query: str
    mode: str
    answer_evidence: tuple[SaturnCandidate, ...]
    document_matches: tuple[RankedDocument, ...]
    lexical_trace: tuple[SaturnCandidate, ...]
    dense_trace: tuple[SaturnCandidate, ...]
    fusion_trace: tuple[SaturnCandidate, ...]
    index_manifest: SaturnIndexManifest
    status: str = "ok"


@dataclass(frozen=True)
class SaturnOperationalPolicy:
    """One immutable operational state, supplied on demand (not source approval)."""
    revision: str
    blocked_source_revision_ids: frozenset[str] = frozenset()
    blocked_evidence_ids: frozenset[str] = frozenset()
    blocked_document_ids: frozenset[str] = frozenset()
    blocked_pdf_revision_ids: frozenset[str] = frozenset()
    blocked_entity_ids: frozenset[str] = frozenset()

    def __post_init__(self):
        if not isinstance(self.revision, str) or not self.revision.strip():
            raise ValueError("Policy revision required")
        for name in ("blocked_source_revision_ids", "blocked_evidence_ids",
                     "blocked_document_ids", "blocked_pdf_revision_ids",
                     "blocked_entity_ids"):
            value = getattr(self, name)
            if type(value) is not frozenset or not all(isinstance(x, str) and x for x in value):
                raise ValueError("Invalid policy set: " + name)


class SaturnPolicyProvider:
    """Thread-safe in-process policy publisher. Errors at capture fail closed."""
    def __init__(self, initial: SaturnOperationalPolicy | None = None):
        self._lock = RLock()
        self._active = initial or SaturnOperationalPolicy("initial")

    def activate(self, policy: SaturnOperationalPolicy):
        if not isinstance(policy, SaturnOperationalPolicy):
            raise ValueError("Invalid Saturn operational policy")
        with self._lock:
            self._active = policy

    def capture(self) -> SaturnOperationalPolicy:
        with self._lock:
            if not isinstance(self._active, SaturnOperationalPolicy):
                raise RuntimeError("Operational policy unavailable")
            return self._active


class SaturnPolicyCaptureError(RuntimeError):
    """Only a failed operational-policy CAPTURE, not backend/retrieval errors."""


def _capture_retrieval_policy(provider):
    try:
        policy = provider.capture()
        if not isinstance(policy, SaturnOperationalPolicy):
            raise ValueError("Policy provider returned an invalid state")
        policy.__post_init__()  # validate even after reflective corruption
        return policy
    except Exception:
        raise SaturnPolicyCaptureError("Policy capture unavailable") from None


def _valid_snapshot(snapshot):
    # Reuse 4A's *strict structural replay*, not merely its content seal.
    if not isinstance(snapshot, SaturnKnowledgeSnapshot) or not snapshot.ready_for_promotion:
        raise ValueError("Validated, promotable Saturn snapshot required")
    SaturnSnapshotManager().activate(snapshot)


def _evidence_records(snapshot):
    pointer_map = {p.evidence_id: p for p in snapshot.evidence_pointers}
    if len(pointer_map) != len(snapshot.evidence_pointers):
        raise ValueError("Duplicate canonical pointer")
    owner = {e.entity_id: e for e in snapshot.entities}
    relation = {r.relation_id: r for r in snapshot.relations}
    pdf = {stable_id("saturn-pdf-revision-v1", p.document_id, p.url, p.bytes_sha256,
                     p.parser_version): p for p in snapshot.pdf_revisions}
    document_matches = {m.document.document_id: m for m in snapshot.document_matches}
    evidence_ids = set()
    result = []
    for evidence in snapshot.answer_evidence:
        if evidence.evidence_id in evidence_ids or evidence.evidence_type == "document_metadata":
            raise ValueError("Invalid answer evidence coverage")
        evidence_ids.add(evidence.evidence_id)
        pointer = pointer_map.get(evidence.evidence_id)
        if pointer is None or pointer.canonical_url is None:
            # canonical URLs are source-backed; None remains legitimate for
            # a source without an exposed public route.
            if pointer is None:
                raise ValueError("Missing evidence pointer")
        text = evidence.text
        if evidence.entity_id is not None:
            entity = owner.get(evidence.entity_id)
            if entity is None:
                raise ValueError("Dangling evidence entity")
            text = entity.title + "\n" + text
        if evidence.evidence_type == "relation":
            rel = relation.get(pointer.canonical_id)
            if rel is None or rel.object_entity_id not in owner:
                raise ValueError("Dangling relation")
            text += "\n" + owner[rel.object_entity_id].title
        pdf_revision = pdf.get(evidence.source_revision_id) if evidence.evidence_type == "pdf_passage" else None
        if evidence.evidence_type == "pdf_passage" and (pdf_revision is None or
                pdf_revision.extraction_state != "extracted"):
            raise ValueError("Unverified PDF passage")
        pdf_match = document_matches.get(pdf_revision.document_id) if pdf_revision else None
        if pdf_revision and pdf_match is None:
            raise ValueError("PDF passage has no verified owner metadata")
        if len(text) > MAX_RECORD_CHARS:
            raise ValueError("Evidence search text exceeds limit")
        result.append(SearchRecord(
            evidence.evidence_id, evidence.evidence_type, snapshot.snapshot_id,
            evidence.source_revision_id, evidence.entity_id, evidence.locator,
            pointer.canonical_url, text, sha256(text.encode("utf-8")).hexdigest(),
            pdf_revision.bytes_sha256 if pdf_revision else None,
            pdf_revision.parser_version if pdf_revision else None,
            evidence.page_number,
            pdf_revision.document_id if pdf_revision else None,
            tuple(sorted(set(o.source_revision_id for o in pdf_match.occurrences)))
                if pdf_match else (),
            pdf_match.document.owner_entity_ids if pdf_match else (),
        ))
    if evidence_ids != set(pointer_map):
        raise ValueError("Canonical evidence-pointer coverage mismatch")
    return tuple(sorted(result, key=lambda x: x.evidence_id))


def _document_records(snapshot):
    entities = {x.entity_id: x for x in snapshot.entities}
    result = []
    ids = set()
    for match in snapshot.document_matches:
        doc = match.document
        if doc.document_id in ids:
            raise ValueError("Duplicate document ID")
        ids.add(doc.document_id)
        if any(owner not in entities for owner in doc.owner_entity_ids):
            raise ValueError("Dangling document owner")
        text = "\n".join(filter(None, (
            doc.title, doc.kind, doc.version, doc.date, doc.url,
            *[entities[i].title for i in doc.owner_entity_ids],
            *[entities[i].slug for i in doc.owner_entity_ids],
        )))
        if len(text) > MAX_RECORD_CHARS:
            raise ValueError("Document metadata too long")
        result.append(DocumentRecord(match, snapshot.snapshot_id, text,
                                     sha256(text.encode("utf-8")).hexdigest()))
    return tuple(sorted(result, key=lambda r: r.match.document.document_id))


def _limit_records(records, documents):
    count = len(records) + len(documents)
    if count > MAX_RECORDS or sum(len(r.text) for r in (*records, *documents)) > MAX_TOTAL_CHARS:
        raise ValueError("Offline index resource limit exceeded")


def _dictionary_aliases(snapshot):
    """Only explicit dictionary 'code' + 'aliases' declarations may expand query.

    Arbitrary dictionary labels, values, properties or engineering claims are
    NOT automatically treated as synonyms. No external model/normalization.
    """
    pairs = set()
    for dictionary in snapshot.dictionaries:
        value = json.loads(dictionary.raw_value_json) if dictionary.raw_value_json else None
        rows = value if isinstance(value, list) else (
            value.get("entries", ()) if isinstance(value, dict) else ())
        if not isinstance(rows, (list, tuple)):
            continue
        for row in rows[:256]:
            if not isinstance(row, dict):
                continue
            code, aliases = row.get("code"), row.get("aliases")
            if not isinstance(code, str) or not isinstance(aliases, list):
                continue
            base = tokenize(code)
            if len(base) != 1 or len(code) > 128:
                continue
            for alias in aliases[:8]:
                if not isinstance(alias, str) or len(alias) > 128:
                    continue
                expanded = tokenize(alias)
                if len(expanded) == 1 and expanded != base:
                    pairs.add((base[0], expanded[0]))
                    if len(pairs) > 256:
                        raise ValueError("Dictionary alias expansion limit exceeded")
    result = {}
    for a, b in sorted(pairs):
        result.setdefault(a, set()).add(b)
        result.setdefault(b, set()).add(a)
    return {key: tuple(sorted(values)) for key, values in sorted(result.items())}


def _expanded_terms(query, aliases=None):
    terms = set(tokenize(query))
    if aliases:
        additions = []
        for term in sorted(terms):
            additions.extend(aliases.get(term, ())[:8])
            if len(additions) >= 32:
                break
        terms.update(additions[:32])
    return terms


def _score_prepared(query, prepared, allowed, limit, aliases=None):
    """BM25 using precomputed (id, sorted term frequencies, length).

    Document-frequency, N and average length are recalculated only from
    policy-eligible records, preserving the previous filtered-corpus semantics.
    Search never tokenizes unchanged document text or reads evaluation labels.
    """
    terms = _expanded_terms(query, aliases)
    if not terms:
        return ()
    corpus = [(cid, freqs, length) for cid, freqs, length in prepared if cid in allowed]
    if not corpus:
        return ()
    n = len(corpus)
    average = sum(length for _, _, length in corpus) / n
    if not average:
        return ()
    frequencies = Counter(term for _, freq, _ in corpus for term, count in freq if count)
    scored = []
    for cid, freq, length in corpus:
        counts = dict(freq)
        score = 0.
        for term in sorted(terms):
            tf = counts.get(term, 0)
            if not tf:
                continue
            score += log(1 + (n - frequencies[term] + 0.5) / (frequencies[term] + 0.5)) * (
                tf * (BM25_K1 + 1) /
                (tf + BM25_K1 * (1 - BM25_B + BM25_B * length / average)))
        if not isfinite(score):
            raise ValueError("Non-finite lexical score")
        if score > 0:
            scored.append((cid, score))
    return tuple(sorted(scored, key=lambda pair: (-pair[1], pair[0]))[:limit])


def _bm25(query: str, texts, limit: int, aliases=None):
    """Reference implementation for parity tests; NOT the query-time index."""
    texts = tuple(texts)
    prepared = []
    for cid, text in texts:
        words = tokenize(text)
        prepared.append((cid, tuple(sorted(Counter(words).items())), len(words)))
    return _score_prepared(query, prepared, {cid for cid, _ in texts}, limit, aliases)


@dataclass(frozen=True)
class SaturnBM25Index:
    tokens: tuple[tuple[str, tuple[str, ...]], ...]
    _prepared: tuple[tuple[str, tuple[tuple[str, int], ...], int], ...]
    coverage_hash: str

    def __init__(self, records):
        tokens = tuple((r.evidence_id, tokenize(r.text)) for r in records)
        prepared = tuple((cid, tuple(sorted(Counter(words).items())), len(words))
                         for cid, words in tokens)
        object.__setattr__(self, "tokens", tokens)
        object.__setattr__(self, "_prepared", prepared)
        object.__setattr__(self, "coverage_hash", _hash((tokens, prepared)))

    def validate(self, records):
        expected = tuple((r.evidence_id, tokenize(r.text)) for r in records)
        prepared = tuple((cid, tuple(sorted(Counter(words).items())), len(words))
                         for cid, words in expected)
        if (expected != self.tokens or prepared != self._prepared or
                self.coverage_hash != _hash((self.tokens, self._prepared))):
            raise ValueError("Tampered Saturn BM25 index")

    def search(self, query, records, allowed, aliases=None):
        if len(records) != len(self._prepared):
            raise ValueError("Prepared BM25 record cardinality mismatch")
        return _score_prepared(query, self._prepared, allowed, CANDIDATE_LIMIT, aliases)


@dataclass(frozen=True)
class SaturnMetadataIndex:
    tokens: tuple[tuple[str, tuple[str, ...]], ...]
    _prepared: tuple[tuple[str, tuple[tuple[str, int], ...], int], ...]
    coverage_hash: str

    def __init__(self, records):
        tokens = tuple((r.match.document.document_id, tokenize(r.text)) for r in records)
        prepared = tuple((cid, tuple(sorted(Counter(words).items())), len(words))
                         for cid, words in tokens)
        object.__setattr__(self, "tokens", tokens)
        object.__setattr__(self, "_prepared", prepared)
        object.__setattr__(self, "coverage_hash", _hash((tokens, prepared)))

    def validate(self, records):
        expected = tuple((r.match.document.document_id, tokenize(r.text)) for r in records)
        prepared = tuple((cid, tuple(sorted(Counter(words).items())), len(words))
                         for cid, words in expected)
        if (self.tokens != expected or self._prepared != prepared or
                self.coverage_hash != _hash((self.tokens, self._prepared))):
            raise ValueError("Tampered Saturn document index")

    def search(self, query, records, allowed, aliases=None):
        if len(records) != len(self._prepared):
            raise ValueError("Prepared metadata record cardinality mismatch")
        return _score_prepared(query, self._prepared, allowed, CANDIDATE_LIMIT, aliases)


@dataclass(frozen=True)
class SaturnRetrievalBundle:
    """Frozen snapshot + exact index bindings, swapped as ONE active pointer."""
    snapshot: SaturnKnowledgeSnapshot
    records: tuple[SearchRecord, ...]
    documents: tuple[DocumentRecord, ...]
    lexical: SaturnBM25Index
    metadata: SaturnMetadataIndex
    dense: object | None
    manifest: SaturnIndexManifest
    aliases: object

    def __init__(self, snapshot, records, documents, lexical, metadata, dense, manifest):
        object.__setattr__(self, "snapshot", snapshot)
        object.__setattr__(self, "records", tuple(records))
        object.__setattr__(self, "documents", tuple(documents))
        object.__setattr__(self, "lexical", lexical)
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "dense", dense)
        object.__setattr__(self, "manifest", manifest)
        # Read-only mapping; no shared mutable dict escapes into a published bundle.
        object.__setattr__(self, "aliases", MappingProxyType(_dictionary_aliases(snapshot)))

    def validate(self):
        if not isinstance(self.snapshot, SaturnKnowledgeSnapshot):
            raise ValueError("Retrieval snapshot invalid")
        if self.records != _evidence_records(self.snapshot) or self.documents != _document_records(self.snapshot):
            raise ValueError("Retrieval source/provenance mismatch")
        self.lexical.validate(self.records)
        self.metadata.validate(self.documents)
        if self.aliases != _dictionary_aliases(self.snapshot):
            raise ValueError("Dictionary rules were tampered with")
        if self.dense is not None:
            if self.dense.snapshot_id != self.snapshot.snapshot_id:
                raise ValueError("Dense snapshot mismatch")
            self.dense.validate(self.records)
        expected = _make_manifest(self.snapshot, self.records, self.documents,
                                  self.lexical, self.metadata, self.dense)
        if expected != self.manifest:
            raise ValueError("Retrieval manifest/index identity mismatch")


def _make_manifest(snapshot, records, documents, lexical, metadata, dense):
    fields = dict(
        snapshot_id=snapshot.snapshot_id,
        corpus_hash=snapshot.manifest.corpus_hash,
        representation_version=REPRESENTATION_VERSION,
        tokenizer_version=TOKENIZER_VERSION,
        lexical_config_hash=_hash((BM25_K1, BM25_B, CANDIDATE_LIMIT, TOKENIZER_VERSION, ALIAS_VERSION)),
        dictionary_fingerprints=tuple(sorted((d.path, sha256(d.content).hexdigest())
                                             for d in snapshot.dictionaries)),
        dense_encoder_hash=dense.encoder_hash if dense else None,
        qdrant_config=("local-"+dense.backend_mode+"/cosine/dim="+str(dense.dimensions)) if dense else None,
        evidence_count=len(records), document_count=len(documents),
        evidence_coverage_hash=_hash(tuple(r.evidence_id for r in records)),
        document_coverage_hash=_hash(tuple(d.match.document.document_id for d in documents)),
        lexical_content_hash=lexical.coverage_hash,
        document_content_hash=metadata.coverage_hash,
        dense_content_hash=dense.content_hash if dense else None,
    )
    return SaturnIndexManifest(**fields, bundle_id=stable_id("saturn-retrieval-bundle-v1", fields))


def build_saturn_retrieval_bundle(snapshot: SaturnKnowledgeSnapshot, *, encoder=None,
                                  qdrant_path=None) -> SaturnRetrievalBundle:
    """Strict input check, bounded offline index build, no active-pointer mutation."""
    _valid_snapshot(snapshot)
    records = _evidence_records(snapshot)
    documents = _document_records(snapshot)
    _limit_records(records, documents)
    lexical = SaturnBM25Index(records)
    metadata = SaturnMetadataIndex(documents)
    dense = None
    if encoder is not None:
        from .saturn_qdrant import SaturnQdrantIndex
        dense = SaturnQdrantIndex(snapshot.snapshot_id, records, encoder, path=qdrant_path)
    manifest = _make_manifest(snapshot, records, documents, lexical, metadata, dense)
    bundle = SaturnRetrievalBundle(snapshot, records, documents, lexical, metadata, dense, manifest)
    bundle.validate()
    return bundle


def _allowed_record(record, policy):
    return (record.evidence_id not in policy.blocked_evidence_ids and
            (record.pdf_document_id is None or record.pdf_document_id not in policy.blocked_document_ids) and
            not any(s in policy.blocked_source_revision_ids for s in record.pdf_link_source_revisions) and
            not any(i in policy.blocked_entity_ids for i in record.pdf_owner_entity_ids) and
            record.source_revision_id not in policy.blocked_source_revision_ids and
            record.source_revision_id not in policy.blocked_pdf_revision_ids and
            (record.entity_id is None or record.entity_id not in policy.blocked_entity_ids))


def _allowed_doc(record, policy, entities):
    doc = record.match.document
    if doc.document_id in policy.blocked_document_ids or (
            record.match.pdf_revision_id in policy.blocked_pdf_revision_ids):
        return False
    if any(i in policy.blocked_entity_ids or
           entities[i].source_revision_id in policy.blocked_source_revision_ids
           for i in doc.owner_entity_ids):
        return False
    return not any(occ.source_revision_id in policy.blocked_source_revision_ids
                   for occ in record.match.occurrences)


def _candidate(record, score, rank, channel):
    return SaturnCandidate(
        record.evidence_id, record.evidence_type, record.entity_id,
        record.source_revision_id, record.locator, record.url,
        record.snapshot_id, float(score), rank, channel)


def _check_channel(raw, records, snapshot_id, channel):
    if not isinstance(raw, (tuple, list)) or len(raw) > CANDIDATE_LIMIT:
        raise ValueError("Invalid retrieval channel cardinality")
    seen = set()
    for rank, candidate in enumerate(raw, 1):
        if (not isinstance(candidate, SaturnCandidate) or
                candidate.evidence_id not in records or candidate.evidence_id in seen or
                candidate.snapshot_id != snapshot_id or candidate.channel != channel or
                type(candidate.rank) is not int or candidate.rank != rank or
                type(candidate.score) not in (float, int) or not isfinite(candidate.score) or
                candidate != _candidate(records[candidate.evidence_id], candidate.score, rank, channel)):
            raise ValueError("Invalid retrieval channel candidate/provenance")
        seen.add(candidate.evidence_id)


def _rerank_after_policy(candidates, eligible):
    return tuple(replace(item, rank=i) for i, item in enumerate(
        (c for c in candidates if c.evidence_id in eligible), 1))


class SaturnRetrievalService:
    """Only authoritative active pointer is a complete snapshot+index bundle."""
    __slots__ = ("_active", "_lock", "policy_provider")

    def __setattr__(self, name, value):
        # No ordinary assignment can bypass publish() or replace its lock.
        if name in self.__slots__ and hasattr(self, name):
            raise AttributeError("Retrieval service bindings require controlled methods: "+name)
        object.__setattr__(self, name, value)

    def __init__(self, policy_provider=None):
        self._active = None
        self._lock = RLock()
        self.policy_provider = policy_provider or SaturnPolicyProvider()

    def capture(self):
        with self._lock:
            if self._active is None:
                raise LookupError("No active Saturn retrieval bundle")
            return self._active

    def open_answer_session(self):
        """Open one pinned session using the internal retain-under-lock factory.

        The session factory performs capture AND Qdrant retain atomically under
        this service's publication lock. No unlocked bundle/lease handoff.
        """
        from ..grounding.saturn_context import SaturnAnswerSession
        return SaturnAnswerSession._from_service(self)

    def publish(self, bundle: SaturnRetrievalBundle):
        if not isinstance(bundle, SaturnRetrievalBundle):
            raise ValueError("Invalid Saturn retrieval bundle")
        dense = bundle.dense
        if dense is not None:
            # Pin the candidate before validation; a concurrent close()
            # cannot destroy it between validation and pointer publication.
            dense._retain()
        try:
            _valid_snapshot(bundle.snapshot)
            bundle.validate()
        except BaseException:
            if dense is not None:
                dense._release()
            raise
        # Exactly one authoritative pointer is swapped under this lock.
        # No reader can capture partially replaced snapshot/index bindings.
        with self._lock:
            previous = self._active
            if previous is bundle:
                if dense is not None:
                    dense._release()  # already retained as active
                return bundle.manifest.bundle_id
            object.__setattr__(self, "_active", bundle)
        if previous is not None and previous.dense is not None:
            # Close is deferred until the old active retain AND all in-flight
            # query retains have been released. The pointer is ALREADY committed:
            # cleanup errors must not turn a successful publish into a reported
            # failure, and never roll the active pointer back.
            try:
                try:
                    previous.dense.close()
                finally:
                    previous.dense._release()
            except Exception as exc:
                warnings.warn("Retired Qdrant cleanup error: " +
                              type(exc).__name__, RuntimeWarning)
        return bundle.manifest.bundle_id

    def search_saturn(self, query: str, *, mode="lexical", top_k=5):
        _valid_query(query, top_k, mode)
        # Capture under the same publication lock and retain an in-flight
        # Qdrant lease BEFORE the old active bundle can be retired.
        with self._lock:
            bundle = self._active
            if bundle is None:
                raise LookupError("No active Saturn retrieval bundle")
            dense = bundle.dense
            if dense is not None:
                dense._retain()
        try:
            return self._search_captured(bundle, query, mode, top_k)
        finally:
            if dense is not None:
                dense._release()

    def _search_captured(self, bundle, query, mode, top_k):
        # Indexes were structurally validated on publication and thereafter
        # sealed. No repeated full-corpus tokenization per query.
        if mode != "lexical" and bundle.dense is None:
            raise RuntimeError("Dense index/encoder unavailable; no hidden lexical fallback")

        # Provider must support atomic, immutable snapshots; failure is fail-closed.
        before = _capture_retrieval_policy(self.policy_provider)
        records = {r.evidence_id: r for r in bundle.records}
        documents = {r.match.document.document_id: r for r in bundle.documents}
        entities = {e.entity_id: e for e in bundle.snapshot.entities}
        allowed_e = {k for k, v in records.items() if _allowed_record(v, before)}
        allowed_d = {k for k, v in documents.items() if _allowed_doc(v, before, entities)}
        lexical_pairs = bundle.lexical.search(query, bundle.records, allowed_e, bundle.aliases) if mode != "dense" else ()
        dense_pairs = bundle.dense.search(query, allowed_e) if mode != "lexical" else ()
        doc_pairs = bundle.metadata.search(query, bundle.documents, allowed_d, bundle.aliases)
        lexical = tuple(_candidate(records[eid], score, rank, "lexical")
                        for rank, (eid, score) in enumerate(lexical_pairs, 1))
        dense = tuple(_candidate(records[eid], score, rank, "dense")
                      for rank, (eid, score) in enumerate(dense_pairs, 1))
        for name, candidates in (("lexical", lexical), ("dense", dense)):
            _check_channel(candidates, records, bundle.snapshot.snapshot_id, name)
        # At a minimum the final eligibility decision sees the latest available
        # policy snapshot. This intentionally may trim a result while a query runs.
        after = _capture_retrieval_policy(self.policy_provider)
        current_e = {k for k, v in records.items() if _allowed_record(v, after)}
        current_d = {k for k, v in documents.items() if _allowed_doc(v, after, entities)}
        lexical = _rerank_after_policy(lexical, current_e)
        dense = _rerank_after_policy(dense, current_e)
        if mode == "hybrid":
            fused = {}
            for group in (lexical, dense):
                for c in group:
                    fused[c.evidence_id] = fused.get(c.evidence_id, 0.) + 1. / (RRF_K + c.rank)
            ranked = sorted(fused, key=lambda eid: (-fused[eid], eid))[:top_k]
            fusion = tuple(_candidate(records[eid], fused[eid], i, "rrf")
                           for i, eid in enumerate(ranked, 1))
            final = fusion
        else:
            fusion = ()
            final = (lexical if mode == "lexical" else dense)[:top_k]
        docs = tuple(RankedDocument(documents[k].match, bundle.snapshot.snapshot_id,
                                     score, i)
                     for i, (k, score) in enumerate(
                         ((eid, score) for eid, score in doc_pairs if eid in current_d), 1)
                     if i <= top_k)
        return SaturnRetrievalResult(bundle.snapshot.snapshot_id, bundle.manifest.bundle_id,
                                      query, mode, final, docs, lexical, dense, fusion,
                                      bundle.manifest)


def search_saturn(service: SaturnRetrievalService, query: str, *,
                  mode="lexical", top_k=5) -> SaturnRetrievalResult:
    """Convenience API; the service captures its one authoritative active bundle."""
    return service.search_saturn(query, mode=mode, top_k=top_k)
