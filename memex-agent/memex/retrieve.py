"""
retrieve.py — Retrieval engine: dereferences an index key to return the
full archived content from SQLite. Lossless by design.
"""

import logging
from typing import Optional

from .store import ExperienceStore
from .manifest import IndexManifest

logger = logging.getLogger(__name__)


class RetrievalEngine:
    """
    Handles read_experience operations: look up the index key in the
    manifest (for metadata), then fetch full content from SQLite.
    """

    def __init__(self, store: ExperienceStore, manifest: IndexManifest):
        self.store = store
        self.manifest = manifest

    def retrieve(self, index_key: str) -> str:
        """
        Dereference an index key and return the full archived content.

        Args:
            index_key: The index key (e.g. "[research:oauth-libs]").

        Returns:
            The exact full content that was originally archived.

        Raises:
            KeyError: If the index key is not found in the store.
        """
        logger.info("Retrieving experience: %s", index_key)

        full_content = self.store.get_full_content(index_key)
        if full_content is None:
            raise KeyError(f"No archived experience found for key: {index_key!r}")

        return full_content

    def get_summary(self, index_key: str) -> Optional[str]:
        """Return just the summary for a key without fetching full content."""
        return self.manifest.summary_for(index_key)

    def get_record(self, index_key: str) -> Optional[dict]:
        """Return the full metadata record (summary + content + stats)."""
        return self.store.retrieve(index_key)

    def list_available(self) -> list[str]:
        """Return all available index keys."""
        return self.store.list_keys()
