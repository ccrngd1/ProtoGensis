"""File watcher for automatic ingestion of files dropped in a directory."""
from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from threading import Thread
from typing import TYPE_CHECKING, List, Set

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

DEFAULT_IGNORE_DIRS = {".obsidian", ".git", "node_modules", ".venv", "__pycache__"}


class FileWatcher:
    """Watches a directory for new files and automatically ingests them.

    Supports recursive scanning, change detection via content hashing,
    and re-ingestion of modified files.
    """

    def __init__(
        self,
        orchestrator: Orchestrator,
        watch_dir: Path,
        poll_interval: int = 60,
        recursive: bool = False,
        track_changes: bool = True,
        change_detection_interval: int = 1800,
        ignore_dirs: Set[str] = None,
    ):
        """Initialize file watcher.

        Args:
            orchestrator: Orchestrator instance with ingest_agent
            watch_dir: Directory to watch
            poll_interval: Seconds between directory scans for new files (default 1 min)
            recursive: If True, scan subdirectories recursively
            track_changes: If True, detect and re-ingest modified files
            change_detection_interval: Seconds between change detection scans (default 30 min)
            ignore_dirs: Set of directory names to ignore (e.g., {".git", ".obsidian"})
        """
        self.orchestrator = orchestrator
        self.watch_dir = watch_dir
        self.poll_interval = poll_interval
        self.recursive = recursive
        self.track_changes = track_changes
        self.change_detection_interval = change_detection_interval
        self.ignore_dirs = ignore_dirs or DEFAULT_IGNORE_DIRS
        self._running = False
        self._thread = None
        self._last_change_detection = 0  # Timestamp of last change detection scan

        # Ensure watch directory exists
        self.watch_dir.mkdir(parents=True, exist_ok=True)

    def start(self):
        """Start watching the directory in a background thread."""
        if self._running:
            logger.warning("File watcher already running")
            return

        self._running = True
        mode = "recursive" if self.recursive else "single-level"
        logger.info(
            f"File watcher started: {self.watch_dir}/ ({mode})"
        )
        logger.info(
            f"New file check: every {self.poll_interval}s, "
            f"Change detection: every {self.change_detection_interval}s"
        )
        if self.ignore_dirs:
            logger.info(f"Ignoring directories: {', '.join(sorted(self.ignore_dirs))}")

        # Run initial full scan on startup
        logger.info("Running initial scan...")
        self._scan_directory(check_changes=True)

        self._thread = Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

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
                # Check if it's time for change detection
                current_time = time.time()
                time_since_last_check = current_time - self._last_change_detection

                if time_since_last_check >= self.change_detection_interval:
                    # Full scan with change detection
                    logger.info("Running change detection scan...")
                    self._scan_directory(check_changes=True)
                    self._last_change_detection = current_time
                else:
                    # Quick scan for new files only (no hash calculation)
                    self._scan_directory(check_changes=False)

            except Exception as e:
                logger.error(f"Error in watch loop: {e}")

            time.sleep(self.poll_interval)

    def _scan_directory(self, check_changes: bool = False):
        """Scan directory for new files and optionally check for changes.

        Args:
            check_changes: If True, calculate hashes and check for modifications.
                          If False, only check for new files (faster).
        """
        try:
            # Choose scanning method based on recursive setting
            if self.recursive:
                file_paths = self._get_files_recursive()
            else:
                file_paths = [
                    f for f in self.watch_dir.iterdir()
                    if f.is_file() and not f.name.startswith(".")
                ]

            for file_path in sorted(file_paths):
                try:
                    self._process_file(file_path, check_changes=check_changes)
                except Exception as e:
                    logger.error(f"Error processing {file_path.name}: {e}")

        except Exception as e:
            logger.error(f"Error scanning directory: {e}")

    def _get_files_recursive(self) -> List[Path]:
        """Get all files recursively, respecting ignore_dirs."""
        files = []
        for item in self.watch_dir.rglob("*"):
            # Skip if not a file
            if not item.is_file():
                continue

            # Skip hidden files
            if item.name.startswith("."):
                continue

            # Skip if any parent directory is in ignore list
            if any(part in self.ignore_dirs for part in item.parts):
                continue

            files.append(item)

        return files

    def _process_file(self, file_path: Path, check_changes: bool = False):
        """Process a single file: check if new or modified, and ingest accordingly.

        Args:
            file_path: Path to file to process
            check_changes: If True, calculate hash and check for modifications.
                          If False, only check if file is new (faster).
        """
        # Skip unsupported file types
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return

        file_key = str(file_path.absolute())

        # Check if file has been processed before
        store = self.orchestrator.store
        processed = store.get_processed_file(file_key)

        if processed is None:
            # New file - ingest it
            logger.info(f"New file detected: {file_path.relative_to(self.watch_dir)}")
            content_hash = self._calculate_hash(file_path)
            self._ingest_and_track(file_path, content_hash)

        elif check_changes and self.track_changes:
            # Check if file has been modified (only during change detection scans)
            content_hash = self._calculate_hash(file_path)
            if processed["content_hash"] != content_hash:
                # Modified file - re-ingest
                logger.info(f"Modified file detected: {file_path.relative_to(self.watch_dir)}")
                self._reingest_and_update(file_path, content_hash, processed["memory_ids"])

    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file contents."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _ingest_and_track(self, file_path: Path, content_hash: str):
        """Ingest a new file and track it in the database."""
        try:
            memory = self.orchestrator.ingest_agent.ingest_file(file_path)
            logger.info(f"Ingested: {memory.summary[:80]}...")

            # Track the file
            file_key = str(file_path.absolute())
            self.orchestrator.store.add_processed_file(
                file_key, content_hash, [memory.id]
            )

        except Exception as e:
            logger.error(f"Failed to ingest {file_path.name}: {e}")

    def _reingest_and_update(
        self, file_path: Path, content_hash: str, old_memory_ids: List[str]
    ):
        """Re-ingest a modified file and replace old memories."""
        try:
            store = self.orchestrator.store

            # Delete consolidations that reference the old memories
            deleted_consolidations = store.delete_consolidations_referencing(old_memory_ids)
            if deleted_consolidations > 0:
                logger.info(
                    f"Deleted {deleted_consolidations} consolidation(s) referencing old memories"
                )

            # Delete old memories
            store.delete_memories(old_memory_ids)
            logger.info(f"Replaced {len(old_memory_ids)} old memory/memories")

            # Ingest the new version
            memory = self.orchestrator.ingest_agent.ingest_file(file_path)
            logger.info(f"Re-ingested: {memory.summary[:80]}...")

            # Update file tracking
            file_key = str(file_path.absolute())
            store.update_processed_file(file_key, content_hash, [memory.id])

        except Exception as e:
            logger.error(f"Failed to re-ingest {file_path.name}: {e}")
