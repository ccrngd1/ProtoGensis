"""File watcher for automatic ingestion and compilation."""

import time
from pathlib import Path
from typing import Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from .config import Config
from .db import Database
from .ingestion import Ingester, detect_source_type


class RawDirectoryHandler(FileSystemEventHandler):
    """Handle file system events in raw/ directory."""

    def __init__(
        self,
        config: Config,
        db: Database,
        on_new_file: Optional[Callable[[str], None]] = None,
    ):
        """Initialize handler.

        Args:
            config: Configuration object
            db: Database connection
            on_new_file: Optional callback for new files (receives file path)
        """
        super().__init__()
        self.config = config
        self.db = db
        self.ingester = Ingester(config.raw_dir)
        self.on_new_file = on_new_file

    def on_created(self, event):
        """Handle file creation events.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Ignore hidden files and temp files
        if file_path.name.startswith(".") or file_path.name.endswith("~"):
            return

        # Ignore non-content files
        if file_path.suffix.lower() not in [".pdf", ".md", ".markdown", ".txt"]:
            return

        # Wait a moment for file to be fully written
        time.sleep(0.5)

        try:
            # Add to database
            relative_path = str(file_path.relative_to(self.config.kb_root))
            source_type = detect_source_type(file_path)

            source_id = self.db.add_source(
                path=relative_path,
                source_type=source_type,
                original_url=None,
                status="pending",
            )

            # Call callback if provided
            if self.on_new_file:
                self.on_new_file(relative_path)

            print(f"Ingested: {file_path.name} (ID: {source_id})")

        except Exception as e:
            print(f"Failed to ingest {file_path}: {e}")


class KnowledgeBaseWatcher:
    """Watch raw/ directory for new files."""

    def __init__(
        self,
        config: Config,
        db: Database,
        on_new_file: Optional[Callable[[str], None]] = None,
    ):
        """Initialize watcher.

        Args:
            config: Configuration object
            db: Database connection
            on_new_file: Optional callback for new files
        """
        self.config = config
        self.db = db
        self.on_new_file = on_new_file
        self.observer = Observer()

        # Ensure raw directory exists
        self.config.raw_dir.mkdir(parents=True, exist_ok=True)

    def start(self):
        """Start watching the raw/ directory."""
        handler = RawDirectoryHandler(self.config, self.db, self.on_new_file)
        self.observer.schedule(handler, str(self.config.raw_dir), recursive=False)
        self.observer.start()
        print(f"Watching {self.config.raw_dir} for new files...")

    def stop(self):
        """Stop watching."""
        self.observer.stop()
        self.observer.join()

    def run(self):
        """Run watcher until interrupted."""
        self.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping watcher...")
            self.stop()


def watch_and_compile(config: Config, db: Database, compiler):
    """Watch raw/ and auto-compile new files.

    Args:
        config: Configuration object
        db: Database connection
        compiler: Compiler instance
    """

    def on_new_file(file_path: str):
        """Compile newly ingested files."""
        print(f"Auto-compiling: {file_path}")
        try:
            # Get the most recent pending source
            pending = db.get_pending_sources()
            if pending:
                source = pending[-1]  # Most recent
                compiler.compile_source(source["id"])
                print(f"Compiled: {file_path}")
        except Exception as e:
            print(f"Compilation failed: {e}")

    watcher = KnowledgeBaseWatcher(config, db, on_new_file=on_new_file)
    watcher.run()
