"""Consolidation Agent — timer-driven, finds connections, generates insights."""
from __future__ import annotations

import logging
from typing import List

from agents.bedrock_client import invoke
from agents.utils import parse_json
from memory.models import Consolidation, Memory
from memory.store import MemoryStore

logger = logging.getLogger(__name__)

MIN_MEMORIES = 5  # Require at least this many unconsolidated memories to run.
MAX_BATCH_SIZE = 50  # Max memories to consolidate per cycle to avoid context overflow.

SYSTEM = """You are a memory consolidation assistant. You receive a list of memory summaries and your job is to:
1. Identify meaningful connections between them (shared entities, related topics, causal chains, patterns)
2. Generate cross-cutting insights that wouldn't be obvious from any single memory

Always respond with a single JSON object (no markdown fences) containing:
- connections: string describing the key connections found between memories
- insights: string containing cross-cutting insights and synthesis
"""


def _build_prompt(memories: List[Memory]) -> str:
    items = "\n".join(
        f"[{i+1}] ID={m.id}\n  Summary: {m.summary}\n  Entities: {m.entities}\n  Topics: {m.topics}"
        for i, m in enumerate(memories)
    )
    return f"Consolidate the following memories:\n\n{items}"


class ConsolidateAgent:
    def __init__(self, store: MemoryStore, min_memories: int = MIN_MEMORIES, max_batch_size: int = MAX_BATCH_SIZE) -> None:
        self.store = store
        self.min_memories = min_memories
        self.max_batch_size = max_batch_size

    def run(self, force: bool = False) -> Consolidation | None:
        """Run one consolidation cycle.

        Args:
            force: If True, bypass min_memories check and consolidate if any memories exist

        Returns the Consolidation record created, or None if not enough memories.
        Processes at most max_batch_size memories per cycle to avoid context overflow.
        """
        all_unconsolidated = self.store.get_unconsolidated()

        # Check if we have enough memories to consolidate
        if not force and len(all_unconsolidated) < self.min_memories:
            logger.info(
                "Consolidation skipped: only %d unconsolidated memories (need %d).",
                len(all_unconsolidated),
                self.min_memories,
            )
            return None

        # If forced, require at least 1 memory
        if force and len(all_unconsolidated) == 0:
            logger.info("Consolidation skipped: no unconsolidated memories.")
            return None

        # Batch to avoid exceeding context window
        memories = all_unconsolidated[:self.max_batch_size]
        logger.info("Consolidating %d memories (of %d unconsolidated)…", len(memories), len(all_unconsolidated))
        prompt = _build_prompt(memories)
        try:
            raw = invoke(prompt, system=SYSTEM, max_tokens=2048)
            data = parse_json(raw)
        except Exception as exc:
            logger.warning("Consolidation LLM call failed (%s).", exc)
            data = {}

        consolidation = Consolidation(
            memory_ids=[m.id for m in memories],
            connections=data.get("connections", ""),
            insights=data.get("insights", ""),
        )
        # Wrap all operations in a single transaction for atomicity
        with self.store.conn:
            self.store.add_consolidation(consolidation)
            self.store.mark_consolidated([m.id for m in memories])
            # Update last consolidation timestamp
            self.store.set_metadata("last_consolidation", consolidation.timestamp.isoformat())
        logger.info("Consolidation complete: %s", consolidation.id)
        return consolidation
