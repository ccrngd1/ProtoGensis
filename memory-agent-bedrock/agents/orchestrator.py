"""Orchestrator — coordinates Ingest, Consolidate, and Query agents."""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from agents.consolidate import ConsolidateAgent
from agents.ingest import IngestAgent
from agents.query import QueryAgent
from memory.models import Consolidation, Memory
from memory.store import MemoryStore

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        db_path: str = "memory.db",
        consolidation_interval: int = 300,  # seconds
        min_memories_for_consolidation: int = 5,
    ) -> None:
        self.store = MemoryStore(db_path=db_path)
        self.ingest_agent = IngestAgent(store=self.store)
        self.consolidate_agent = ConsolidateAgent(
            store=self.store,
            min_memories=min_memories_for_consolidation,
        )
        self.query_agent = QueryAgent(store=self.store)

        self._consolidation_interval = consolidation_interval
        self._timer_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(self, text: str, source: str = "") -> Memory:
        return self.ingest_agent.ingest(text, source=source)

    def query(self, question: str) -> str:
        return self.query_agent.query(question)

    def consolidate(self) -> Optional[Consolidation]:
        return self.consolidate_agent.run()

    # ------------------------------------------------------------------
    # Background consolidation timer
    # ------------------------------------------------------------------

    def start_background_consolidation(self) -> None:
        if self._timer_thread and self._timer_thread.is_alive():
            return
        self._stop_event.clear()
        self._timer_thread = threading.Thread(
            target=self._consolidation_loop, daemon=True, name="consolidation-timer"
        )
        self._timer_thread.start()
        logger.info(
            "Background consolidation started (interval=%ds).",
            self._consolidation_interval,
        )

    def stop_background_consolidation(self) -> None:
        self._stop_event.set()
        if self._timer_thread:
            self._timer_thread.join(timeout=5)
        logger.info("Background consolidation stopped.")

    def _consolidation_loop(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._consolidation_interval)
            if self._stop_event.is_set():
                break
            try:
                self.consolidate_agent.run()
            except Exception as exc:
                logger.error("Consolidation error: %s", exc)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> dict:
        return {
            "memory_count": self.store.count_memories(),
            "consolidation_count": self.store.count_consolidations(),
            "unconsolidated_count": len(self.store.get_unconsolidated()),
            "background_consolidation_running": bool(
                self._timer_thread and self._timer_thread.is_alive()
            ),
        }
