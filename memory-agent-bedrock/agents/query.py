"""Query Agent — reads all memories, synthesizes answer with citations."""
from __future__ import annotations

import logging
from typing import List

from agents.bedrock_client import invoke
from memory.models import Consolidation, Memory
from memory.store import MemoryStore

logger = logging.getLogger(__name__)

SYSTEM = """You are a memory retrieval assistant. You will be given a user question followed by a list of stored memories and any consolidation insights. Your job is to:
1. Synthesize a clear, concise answer to the question
2. Cite the specific memory IDs that support your answer (use the format [memory:ID])
3. If relevant consolidation insights exist, mention them and cite their source

Be honest: if the memories don't contain enough information to answer, say so."""


def _build_prompt(question: str, memories: List[Memory], consolidations: List[Consolidation]) -> str:
    mem_block = "\n".join(
        f"[memory:{m.id}] {m.summary}  (entities: {m.entities}, topics: {m.topics}, importance: {m.importance:.2f})"
        for m in memories
    )
    cons_block = "\n".join(
        f"[consolidation:{c.id}]\n  Connections: {c.connections}\n  Insights: {c.insights}"
        for c in consolidations
    )
    sections = [f"Question: {question}", "", "=== Memories ===", mem_block or "(none)"]
    if cons_block:
        sections += ["", "=== Consolidation Insights ===", cons_block]
    return "\n".join(sections)


class QueryAgent:
    def __init__(self, store: MemoryStore, max_memories: int = 50) -> None:
        self.store = store
        self.max_memories = max_memories

    def query(self, question: str) -> str:
        """Answer *question* using stored memories and consolidations.

        Limits to max_memories (default 50) to avoid exceeding context window.
        At ~300 tokens/memory, 200K context holds ~650 memories max, but we keep
        a safe margin for the prompt structure and consolidations.
        """
        memories = self.store.list_memories(limit=self.max_memories)
        consolidations = self.store.list_consolidations(limit=50)

        if not memories:
            return "No memories stored yet. Please ingest some information first."

        prompt = _build_prompt(question, memories, consolidations)
        logger.info("Querying with %d memories, %d consolidations.", len(memories), len(consolidations))
        answer = invoke(prompt, system=SYSTEM, max_tokens=2048)
        return answer
