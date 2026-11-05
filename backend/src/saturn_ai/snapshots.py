"""Synthetic snapshot/index metadata contracts; no persistent indexes or ranking."""
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from pathlib import PurePosixPath
from threading import RLock

from .ingestion.contracts import Document, IngestedChunk, IngestionResult, SourceBlob, identifier
from .ingestion.registry import Registry, load_registry, _hash


def _checked_registry(registry):
    if (not isinstance(registry, Registry) or type(registry.raw_bytes) is not bytes
            or not registry.raw_bytes or type(registry.entries) is not tuple
            or registry != load_registry(registry.raw_bytes)):
        raise ValueError('Registry fields/revision do not match original JSON bytes')
    return registry


@dataclass(frozen=True)
class IndexedChunk:
    chunk: IngestedChunk
    snapshot_id: str
    policy_revision: str
    source_hash: str
    source_commit: str | None
    source_locator: str
    source_title: str
    visibility: str
    approval_state: str
    allowed_usage: tuple[str, ...]

    @property
    def chunk_id(self):
        return self.chunk.chunk_id

    @property
    def source_id(self):
        return self.chunk.source_id


@dataclass(frozen=True)
class KnowledgeSnapshot:
    snapshot_id: str
    registry: Registry
    ingestion: IngestionResult
    chunks: tuple[IndexedChunk, ...]
    test_only: bool = True

    @property
    def documents(self):
        return self.ingestion.documents


def build_snapshot(ingestion: IngestionResult, registry: Registry) -> KnowledgeSnapshot:
    _checked_registry(registry)
    if (registry.registry_status != 'synthetic_test_only'
            or any(not r.source_id.startswith('synthetic:') for r in registry.entries)
            or not isinstance(ingestion, IngestionResult) or ingestion.test_only is not True
            or type(ingestion.documents) is not tuple or type(ingestion.skipped_source_ids) is not tuple
            or ingestion.registry_revision != registry.revision):
        raise ValueError('Only revision-bound immutable synthetic ingestion accepted')
    records = {r.source_id: r for r in registry.entries}
    allowed = {r.source_id for r in registry.entries
               if r.permits('local_index', r.approved_content_sha256, r.source_commit)}
    ids = [d.source_id for d in ingestion.documents]
    if (len(ids) != len(set(ids)) or set(ids) != allowed
            or len(ingestion.skipped_source_ids) != len(set(ingestion.skipped_source_ids))
            or set(ingestion.skipped_source_ids) != set(records) - allowed
            or ingestion.snapshot_id != identifier(registry.revision,
                                                  tuple(d.document_id for d in ingestion.documents))):
        raise ValueError('Missing/duplicate/extra documents or inconsistent ingestion identity')
    if (type(ingestion.source_blobs) is not tuple
            or any(not isinstance(blob, SourceBlob) or type(blob.content) is not bytes
                   or len(blob.content) > 1_000_000 for blob in ingestion.source_blobs)):
        raise ValueError('Missing or malformed source-byte receipts')
    blobs = {blob.source_id: blob.content for blob in ingestion.source_blobs}
    if len(blobs) != len(ingestion.source_blobs) or set(blobs) != allowed:
        raise ValueError('Missing/extra/duplicate source-byte receipts')
    seen_chunks = set()
    for document in ingestion.documents:
        record = records[document.source_id]
        site = record.source_kind == 'site_content'
        locator = record.path if site else record.url
        parser = 'site-v1' if site else 'pdf-v1'
        expected_id = (identifier(record.source_id, document.content_hash, record.source_commit, locator, parser)
                       if site else identifier(record.source_id, document.content_hash, locator, parser))
        entity_id = '/'.join(PurePosixPath(locator).parts[-2:]).removesuffix('.md') if site else record.discovered_from
        if (not isinstance(document, Document) or document.content_hash != record.approved_content_sha256
                or document.title != record.title or document.locator != locator
                or document.source_commit != record.source_commit or document.parser_version != parser
                or document.document_id != expected_id or document.entity_id != entity_id
                or document.entity_type != (record.entity_type if site else 'Document')
                or type(document.chunks) is not tuple or not document.chunks
                or type(document.relationships) is not tuple or type(document.document_links) is not tuple):
            raise ValueError('Document provenance mismatch')
        content = blobs[record.source_id]
        if sha256(content).hexdigest() != document.content_hash:
            raise ValueError('Source-byte receipt hash mismatch')
        # Caller-supplied hashes alone cannot attest derived text. Reparse approved
        # original bytes and compare the complete canonical extraction.
        if site:
            from .ingestion.site import parse_site
            canonical = parse_site(record, content)
        else:
            from .ingestion.pdf import parse_pdf
            canonical = parse_pdf(record, content)
        if document != canonical:
            raise ValueError('Document/chunks differ from approved-byte parser output')
        for chunk in document.chunks:
            if (not isinstance(chunk, IngestedChunk) or chunk.source_id != record.source_id
                    or chunk.document_id != document.document_id or not isinstance(chunk.text, str)
                    or not chunk.text.strip() or not isinstance(chunk.field_path, str) or not chunk.field_path
                    or type(chunk.heading_path) is not tuple
                    or any(not isinstance(h, str) or not h.strip() for h in chunk.heading_path)
                    or chunk.text_hash != sha256(chunk.text.encode()).hexdigest()
                    or chunk.chunk_id != identifier(document.document_id, chunk.heading_path,
                                                    chunk.field_path, chunk.page_start, chunk.text_hash)
                    or chunk.chunk_id in seen_chunks):
                raise ValueError('Chunk identity/provenance mismatch')
            if (site and (chunk.page_start is not None or chunk.page_end is not None)) or (
                    not site and (type(chunk.page_start) is not int or chunk.page_start < 1
                                  or chunk.page_end != chunk.page_start)):
                raise ValueError('Invalid physical page provenance')
            seen_chunks.add(chunk.chunk_id)
        if any(r.source_id != record.source_id or r.from_entity_id != document.entity_id
               for r in document.relationships):
            raise ValueError('Relationship provenance mismatch')
        if any(link.approval_state != 'pending' for link in document.document_links):
            raise ValueError('Document approval cannot be inherited')
    documents = tuple(sorted(ingestion.documents, key=lambda d: d.source_id))
    normalized = replace(ingestion, documents=documents, skipped_source_ids=tuple(sorted(ingestion.skipped_source_ids)),
                         snapshot_id=identifier(registry.revision, tuple(d.document_id for d in documents)),
                         source_blobs=tuple(sorted(ingestion.source_blobs, key=lambda b: b.source_id)))
    sid = identifier('knowledge-snapshot-v1', registry.revision, [asdict(d) for d in documents])
    indexed = tuple(IndexedChunk(chunk, sid, registry.revision, doc.content_hash, doc.source_commit,
                                doc.locator, doc.title, records[doc.source_id].visibility,
                                records[doc.source_id].approval_state, records[doc.source_id].allowed_usage)
                    for doc in documents for chunk in doc.chunks)
    return KnowledgeSnapshot(sid, registry, normalized, indexed)


@dataclass(frozen=True)
class IndexDescriptor:
    snapshot_id: str
    kind: str
    chunk_ids: tuple[str, ...]
    implementation: str
    configuration_hash: str


@dataclass(frozen=True)
class SnapshotBundle:
    snapshot: KnowledgeSnapshot
    dense: IndexDescriptor
    lexical: IndexDescriptor


def _checked_bundle(bundle):
    if (not isinstance(bundle, SnapshotBundle) or not isinstance(bundle.snapshot, KnowledgeSnapshot)
            or bundle.snapshot != build_snapshot(bundle.snapshot.ingestion, bundle.snapshot.registry)):
        raise ValueError('Invalid snapshot payload')
    expected = {c.chunk_id for c in bundle.snapshot.chunks}
    for descriptor, kind in ((bundle.dense, 'dense'), (bundle.lexical, 'lexical')):
        if (not isinstance(descriptor, IndexDescriptor) or descriptor.kind != kind
                or descriptor.snapshot_id != bundle.snapshot.snapshot_id
                or type(descriptor.chunk_ids) is not tuple or len(descriptor.chunk_ids) != len(set(descriptor.chunk_ids))
                or set(descriptor.chunk_ids) != expected or not isinstance(descriptor.implementation, str)
                or not descriptor.implementation.strip() or not _hash(descriptor.configuration_hash)):
            raise ValueError('Index declaration snapshot/coverage/config mismatch')
    return bundle


class SnapshotCatalog:
    """Process-local atomic pointer, with policy/revocations independent of rollback.

    Declarations do not inspect actual index artifacts. Captures are immutable;
    callers must check eligible_chunks again before egress/result publication.
    No persistence or multi-process synchronization is provided.
    """
    def __init__(self, registry: Registry):
        self._registry = _checked_registry(registry)
        self._revoked = set()
        self._active = None
        self._lock = RLock()

    def activate(self, bundle: SnapshotBundle):
        _checked_bundle(bundle)
        with self._lock:
            self._active = bundle

    def capture(self) -> SnapshotBundle:
        with self._lock:
            if self._active is None:
                raise LookupError('No active snapshot')
            return self._active

    def update_policy(self, registry: Registry):
        _checked_registry(registry)
        with self._lock:
            self._registry = registry

    def revoke(self, source_id: str):
        if not isinstance(source_id, str) or not source_id:
            raise ValueError('Invalid source ID')
        with self._lock:
            self._revoked.add(source_id)

    def eligible_chunks(self, bundle: SnapshotBundle, usage: str) -> tuple[IndexedChunk, ...]:
        _checked_bundle(bundle)
        if not isinstance(usage, str):
            raise ValueError('Invalid scope')
        with self._lock:
            records = {r.source_id: r for r in self._registry.entries}
            return tuple(c for c in bundle.snapshot.chunks
                         if c.source_id in records and c.source_id not in self._revoked
                         and records[c.source_id].permits(usage, c.source_hash, c.source_commit)
                         and (records[c.source_id].path or records[c.source_id].url) == c.source_locator
                         and records[c.source_id].title == c.source_title)
