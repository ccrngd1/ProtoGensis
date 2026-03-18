"""
Incremental update pipeline: process only new messages into the existing hierarchy.

On each call, the updater:
  1. Finds messages not yet assigned to any episode (unprocessed)
  2. Builds new episodes from those messages
  3. Finds episodes not yet referenced by any semantic node
  4. Extracts new semantics from those episodes
  5. Finds semantics not yet assigned to any theme
  6. Clusters those semantics into themes (merging with existing ones)

This ensures the full hierarchy is never rebuilt from scratch — only
incremental additions are processed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from xmemory._llm import HAIKU_MODEL, SONNET_MODEL
from xmemory.episodes import construct_episodes
from xmemory.models import Episode, SemanticNode, Theme
from xmemory.semantics import extract_semantics
from xmemory.store import MemoryStore
from xmemory.themes import cluster_themes


@dataclass
class UpdateResult:
    """Summary of an incremental update run."""

    new_episodes: List[Episode] = field(default_factory=list)
    new_semantics: List[SemanticNode] = field(default_factory=list)
    touched_themes: List[Theme] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (
            f"Update complete: "
            f"{len(self.new_episodes)} new episode(s), "
            f"{len(self.new_semantics)} new semantic node(s), "
            f"{len(self.touched_themes)} theme(s) updated."
        )


class MemoryUpdater:
    """
    Incremental hierarchy update coordinator.

    Processes only new/unassigned items at each level, never performing
    a full rebuild.
    """

    def __init__(
        self,
        store: MemoryStore,
        construction_model: str = HAIKU_MODEL,
        client=None,
        episode_block_size: int = 10,
    ) -> None:
        self.store = store
        self.construction_model = construction_model
        self.client = client
        self.episode_block_size = episode_block_size

    def run(self, session_id: Optional[str] = None) -> UpdateResult:
        """
        Run a full incremental update pass.

        Args:
            session_id: If given, only process messages from this session
                        (episodes, semantics, and themes are still global).

        Returns:
            UpdateResult describing what was created/updated.
        """
        result = UpdateResult()

        # Step 1: Construct episodes from unprocessed messages
        new_eps = construct_episodes(
            self.store,
            session_id=session_id,
            block_size=self.episode_block_size,
            model=self.construction_model,
            client=self.client,
        )
        result.new_episodes = new_eps

        # Step 2: Extract semantics from unprocessed episodes
        new_sems = extract_semantics(
            self.store,
            episodes=None,  # auto-detect unprocessed
            model=self.construction_model,
            client=self.client,
        )
        result.new_semantics = new_sems

        # Step 3: Cluster unthemed semantics
        touched = cluster_themes(
            self.store,
            nodes=None,  # auto-detect unthemed
            model=self.construction_model,
            client=self.client,
        )
        result.touched_themes = touched

        return result
