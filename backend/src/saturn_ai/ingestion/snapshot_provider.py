"""Provider-neutral boundary for trusted, immutable Saturn site snapshots."""
from typing import Protocol

from .saturn_site_adapter import PinnedSiteSnapshot


class SnapshotProvider(Protocol):
    """Return one complete pinned snapshot or raise; never return partial data."""

    def fetch_snapshot(self) -> PinnedSiteSnapshot:
        """Fetch the configured trusted source revision as an immutable snapshot."""
