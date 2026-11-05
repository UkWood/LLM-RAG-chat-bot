"""Immutable parser output, deliberately separate from M1 generation evidence."""
from dataclasses import dataclass
from hashlib import sha256
import json


@dataclass(frozen=True)
class IngestedChunk:
    chunk_id: str
    document_id: str
    source_id: str
    text: str
    text_hash: str
    heading_path: tuple[str, ...]
    field_path: str
    page_start: int | None = None
    page_end: int | None = None


@dataclass(frozen=True)
class Relationship:
    source_id: str
    from_entity_id: str
    target_entity_id: str
    kind: str
    field_path: str


@dataclass(frozen=True)
class DocumentLink:
    title: str
    url: str
    kind: str
    version: str | None
    # A candidate only. No child approval inherited from its parent.
    approval_state: str = 'pending'


@dataclass(frozen=True)
class Document:
    document_id: str
    source_id: str
    content_hash: str
    parser_version: str
    title: str
    entity_id: str
    entity_type: str
    source_commit: str | None
    locator: str
    chunks: tuple[IngestedChunk, ...]
    relationships: tuple[Relationship, ...] = ()
    document_links: tuple[DocumentLink, ...] = ()


@dataclass(frozen=True)
class IngestionResult:
    snapshot_id: str
    registry_revision: str
    documents: tuple[Document, ...]
    skipped_source_ids: tuple[str, ...]
    test_only: bool = True


def identifier(*parts):
    return sha256(json.dumps(parts, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def make_chunk(document_id, source_id, text, heading_path=(), field_path='body', page=None):
    digest = sha256(text.encode()).hexdigest()
    return IngestedChunk(identifier(document_id, heading_path, field_path, page, digest),
                         document_id, source_id, text, digest, tuple(heading_path), field_path, page, page)
