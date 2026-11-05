"""Validate a registry, optionally summarize a synthetic-only ingestion run."""
import argparse
import json
from pathlib import Path
from .pipeline import build_fixture
from .registry import load_registry


def main():
    parser = argparse.ArgumentParser(description='Offline registry validation / synthetic ingestion')
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--fixture-root', type=Path)
    parser.add_argument('--source-commit')
    args = parser.parse_args()
    try:
        registry = load_registry(args.registry.read_bytes())
        summary = {'registry_revision': registry.revision, 'source_count': len(registry.entries),
                   'permitted_local_index': sum(s.permits('local_index', s.approved_content_sha256,
                                                          s.source_commit) for s in registry.entries)}
        if args.fixture_root:
            result = build_fixture(args.fixture_root, registry, args.source_commit)
            summary.update(test_only=True, snapshot_id=result.snapshot_id,
                           document_count=len(result.documents),
                           chunk_count=sum(len(d.chunks) for d in result.documents),
                           document_ids=[d.document_id for d in result.documents],
                           skipped_source_ids=result.skipped_source_ids)
    except (ValueError, OSError, RecursionError):
        parser.exit(2, 'Registry or synthetic ingestion rejected.\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
