"""File watcher for automatic ingestion of files dropped in a directory."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from threading import Thread
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    # Text
    ".txt", ".md", ".json", ".csv", ".log", ".yaml", ".yml",
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    # Documents
    ".pdf",
}


class FileWatcher:
    """Watches a directory for new files and automatically ingests them."""

    def __init__(self, orchestrator: Orchestrator, watch_dir: Path, poll_interval: int = 5):
        """Initialize file watcher.

        Args:
            orchestrator: Orchestrator instance with ingest_agent
            watch_dir: Directory to watch
            poll_interval: Seconds between directory scans
        """
        self.orchestrator = orchestrator
        self.watch_dir = watch_dir
        self.poll_interval = poll_interval
        self.processed_files = set()
        self._running = False
        self._thread = None

        # Ensure watch directory exists
        self.watch_dir.mkdir(parents=True, exist_ok=True)

    def start(self):
        """Start watching the directory in a background thread."""
        if self._running:
            logger.warning("File watcher already running")
            return

        self._running = True
        self._thread = Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info(f"File watcher started: {self.watch_dir}/ (poll interval: {self.poll_interval}s)")

    def stop(self):
        """Stop the file watcher."""
        if not self._running:
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("File watcher stopped")

    def _watch_loop(self):
        """Main watch loop that runs in background thread."""
        logger.info(f"Watching: {self.watch_dir}/ for new files (supported: text, images, PDFs)")

        while self._running:
            try:
                self._scan_directory()
            except Exception as e:
                logger.error(f"Error in watch loop: {e}")

            time.sleep(self.poll_interval)

    def _scan_directory(self):
        """Scan directory for new files and ingest them."""
        try:
            for file_path in sorted(self.watch_dir.iterdir()):
                # Skip directories and hidden files
                if file_path.is_dir() or file_path.name.startswith("."):
                    continue

                # Skip unsupported file types
                if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue

                # Skip already processed files
                file_key = str(file_path.absolute())
                if file_key in self.processed_files:
                    continue

                # Ingest the file
                self._ingest_file(file_path)
                self.processed_files.add(file_key)

        except Exception as e:
            logger.error(f"Error scanning directory: {e}")

    def _ingest_file(self, file_path: Path):
        """Ingest a single file."""
        try:
            logger.info(f"New file detected: {file_path.name}")
            memory = self.orchestrator.ingest_agent.ingest_file(file_path)
            logger.info(f"Ingested: {memory.summary[:80]}...")
        except Exception as e:
            logger.error(f"Failed to ingest {file_path.name}: {e}")
