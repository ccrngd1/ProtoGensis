"""Ingest Agent — converts raw text to a structured Memory record."""
from __future__ import annotations

import logging
from typing import Optional

from agents.bedrock_client import invoke
from agents.utils import parse_json
from memory.models import Memory
from memory.store import MemoryStore

logger = logging.getLogger(__name__)

SYSTEM = """You are a memory extraction assistant. Given a piece of text, extract structured information.
Always respond with a single JSON object (no markdown fences) containing:
- summary: string (1-3 sentence distillation)
- entities: list of strings (people, places, organizations, products, concepts)
- topics: list of strings (broad thematic categories, e.g. "machine learning", "personal finance")
- importance: float between 0.0 and 1.0 (how significant/noteworthy is this information)
"""


class IngestAgent:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def ingest(self, text: str, source: str = "") -> Memory:
        """Extract structured memory from *text* and persist it."""
        prompt = f"Extract structured memory from the following text:\n\n{text}"
        try:
            raw = invoke(prompt, system=SYSTEM, max_tokens=1024)
            data = parse_json(raw)
        except Exception as exc:
            logger.warning("LLM extraction failed (%s); using fallback.", exc)
            data = {}

        # Clamp importance to valid range [0.0, 1.0] to handle LLM errors
        try:
            importance = float(data.get("importance", 0.5))
            importance = max(0.0, min(1.0, importance))
        except (ValueError, TypeError):
            importance = 0.5

        memory = Memory(
            summary=data.get("summary", text[:500]),
            entities=data.get("entities", []),
            topics=data.get("topics", []),
            importance=importance,
            source=source,
        )
        return self.store.add_memory(memory)
