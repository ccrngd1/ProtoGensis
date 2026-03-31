"""Orchestrator — coordinates Ingest, Consolidate, and Query agents."""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta
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
        daily_consolidation_interval: int = 86400,  # 24 hours in seconds
        enable_startup_consolidation: bool = True,
        enable_daily_consolidation: bool = True,
        max_memories_query: int = 400,
    ) -> None:
        self.store = MemoryStore(db_path=db_path)
        self.ingest_agent = IngestAgent(store=self.store)
        self.consolidate_agent = ConsolidateAgent(
            store=self.store,
            min_memories=min_memories_for_consolidation,
        )
        self.query_agent = QueryAgent(store=self.store, max_memories=max_memories_query)

        self._consolidation_interval = consolidation_interval
        self._daily_consolidation_interval = daily_consolidation_interval
        self._enable_startup_consolidation = enable_startup_consolidation
        self._enable_daily_consolidation = enable_daily_consolidation
        self._timer_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(self, text: str, source: str = "") -> Memory:
        return self.ingest_agent.ingest(text, source=source)

    def query(self, question: str) -> str:
        return self.query_agent.query(question)

    def consolidate(self, force: bool = False) -> Optional[Consolidation]:
        return self.consolidate_agent.run(force=force)

    def _should_run_daily_consolidation(self) -> bool:
        """Check if it's been N seconds since last consolidation and there are unconsolidated memories."""
        # Check if daily consolidation is enabled
        if not self._enable_daily_consolidation:
            return False

        # Check if there are any unconsolidated memories
        if len(self.store.get_unconsolidated()) == 0:
            return False

        # Get last consolidation timestamp
        last_consolidation_str = self.store.get_metadata("last_consolidation")
        if last_consolidation_str is None:
            # No consolidation has run yet, so run it
            return True

        # Parse the timestamp and check if configured interval has passed
        try:
            last_consolidation = datetime.fromisoformat(last_consolidation_str)
            time_since_last = datetime.utcnow() - last_consolidation
            return time_since_last >= timedelta(seconds=self._daily_consolidation_interval)
        except (ValueError, TypeError):
            # If parsing fails, assume we should consolidate
            return True

    # ------------------------------------------------------------------
    # Background consolidation timer
    # ------------------------------------------------------------------

    def start_background_consolidation(self) -> None:
        if self._timer_thread and self._timer_thread.is_alive():
            return
        self._stop_event.clear()

        # Run consolidation at startup if enabled and there are unconsolidated memories
        if self._enable_startup_consolidation:
            unconsolidated_count = len(self.store.get_unconsolidated())
            if unconsolidated_count > 0:
                logger.info(
                    "Running startup consolidation (%d unconsolidated memories)...",
                    unconsolidated_count,
                )
                try:
                    result = self.consolidate(force=True)
                    if result:
                        logger.info("Startup consolidation complete: %s", result.id)
                    else:
                        logger.info("Startup consolidation skipped (not enough memories)")
                except Exception as exc:
                    logger.error("Startup consolidation error: %s", exc)

        self._timer_thread = threading.Thread(
            target=self._consolidation_loop, daemon=True, name="consolidation-timer"
        )
        self._timer_thread.start()

        daily_status = f", daily consolidation every {self._daily_consolidation_interval}s" if self._enable_daily_consolidation else ""
        logger.info(
            "Background consolidation started (check interval=%ds%s).",
            self._consolidation_interval,
            daily_status,
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
                # Check if we should run daily consolidation
                if self._should_run_daily_consolidation():
                    logger.info("Running daily forced consolidation...")
                    self.consolidate(force=True)
                else:
                    # Run normal consolidation (min_memories threshold applies)
                    self.consolidate()
            except Exception as exc:
                logger.error("Consolidation error: %s", exc)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> dict:
        status = {
            "memory_count": self.store.count_memories(),
            "consolidation_count": self.store.count_consolidations(),
            "unconsolidated_count": len(self.store.get_unconsolidated()),
            "background_consolidation_running": bool(
                self._timer_thread and self._timer_thread.is_alive()
            ),
        }

        # Add last consolidation timestamp if available
        last_consolidation_str = self.store.get_metadata("last_consolidation")
        if last_consolidation_str:
            status["last_consolidation"] = last_consolidation_str

        # Add processed files information
        processed_files = self.store.list_processed_files()
        status["processed_files"] = {
            "total_count": len(processed_files),
            "files": processed_files,
        }

        return status
