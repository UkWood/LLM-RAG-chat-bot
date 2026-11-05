"""Synthetic offline orchestration; production ingestion is intentionally disabled."""
from hashlib import sha256
from pathlib import Path
from .contracts import IngestionResult, identifier
from .registry import Registry
from .site import parse_site


def build_fixture(root: Path, registry: Registry, commit: str) -> IngestionResult:
    documents, skipped = [], []
    for record in registry.entries:
        # Policy decision uses pinned expected hash first; denied bytes are never read.
        if not record.permits('local_index', record.approved_content_sha256, record.source_commit):
            skipped.append(record.source_id)
            continue
        if registry.registry_status != 'synthetic_test_only' or not record.source_id.startswith('synthetic:'):
            raise ValueError('Real source ingestion is disabled in fixture runner')
        if record.source_kind == 'site_content':
            if commit != record.source_commit:
                raise ValueError('Snapshot commit drift')
            rel = record.path
        else:
            if not record.url.startswith('https://example.invalid/synthetic/'):
                raise ValueError('Only synthetic PDF fixtures allowed')
            rel = 'pdf/' + sha256(record.source_id.encode()).hexdigest() + '.pdf'
        base = root.resolve()
        path = (base / rel).resolve()
        if not path.is_relative_to(base) or not path.is_file():
            raise ValueError('Missing or escaping fixture')
        # Bounded reads including growth between stat/read. Exact hash checked by adapter.
        with path.open('rb') as file:
            content = file.read(1_000_001)
        if len(content) > 1_000_000:
            raise ValueError('Fixture byte limit')
        if record.source_kind == 'site_content':
            document = parse_site(record, content)
        else:
            from .pdf import parse_pdf
            document = parse_pdf(record, content)
        documents.append(document)
    return IngestionResult(identifier(registry.revision, tuple(d.document_id for d in documents)),
                           registry.revision, tuple(documents), tuple(skipped))
