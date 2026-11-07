"""Explicit snapshot type dispatch; legacy synthetic byte checks stay unchanged."""
from ..snapshots import KnowledgeSnapshot,build_snapshot


def checked_snapshot(snapshot):
    if isinstance(snapshot,KnowledgeSnapshot):
        if snapshot!=build_snapshot(snapshot.ingestion,snapshot.registry):raise ValueError('Invalid synthetic snapshot')
    else:
        from ..publication.snapshot import PublishedSnapshot
        if not isinstance(snapshot,PublishedSnapshot):raise ValueError('Unknown snapshot type')
        snapshot.validate()
    return snapshot
