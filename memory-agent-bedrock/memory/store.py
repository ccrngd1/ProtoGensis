"""SQLite CRUD layer for memories and consolidations."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import List, Optional

from memory.models import Consolidation, Memory
from memory.schema import init_db


class MemoryStore:
    def __init__(self, db_path: str = "memory.db") -> None:
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            init_db(self._conn)
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Memories
    # ------------------------------------------------------------------

    def add_memory(self, memory: Memory) -> Memory:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO memories (id, summary, entities, topics, importance, source, timestamp, consolidated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory.id,
                memory.summary,
                json.dumps(memory.entities),
                json.dumps(memory.topics),
                memory.importance,
                memory.source,
                memory.timestamp.isoformat(),
                int(memory.consolidated),
            ),
        )
        self.conn.commit()
        return memory

    def get_memory(self, memory_id: str) -> Optional[Memory]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = cur.fetchone()
        return self._row_to_memory(row) if row else None

    def list_memories(self, limit: int = 500) -> List[Memory]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM memories ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [self._row_to_memory(r) for r in cur.fetchall()]

    def get_unconsolidated(self) -> List[Memory]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM memories WHERE consolidated = 0 ORDER BY timestamp ASC"
        )
        return [self._row_to_memory(r) for r in cur.fetchall()]

    def mark_consolidated(self, memory_ids: List[str]) -> None:
        cur = self.conn.cursor()
        placeholders = ",".join("?" * len(memory_ids))
        cur.execute(
            f"UPDATE memories SET consolidated = 1 WHERE id IN ({placeholders})",
            memory_ids,
        )
        self.conn.commit()

    def count_memories(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM memories")
        return cur.fetchone()[0]

    # ------------------------------------------------------------------
    # Consolidations
    # ------------------------------------------------------------------

    def add_consolidation(self, consolidation: Consolidation) -> Consolidation:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO consolidations (id, memory_ids, connections, insights, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                consolidation.id,
                json.dumps(consolidation.memory_ids),
                consolidation.connections,
                consolidation.insights,
                consolidation.timestamp.isoformat(),
            ),
        )
        self.conn.commit()
        return consolidation

    def list_consolidations(self, limit: int = 100) -> List[Consolidation]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM consolidations ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [self._row_to_consolidation(r) for r in cur.fetchall()]

    def count_consolidations(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM consolidations")
        return cur.fetchone()[0]

    def delete_consolidations_referencing(self, memory_ids: List[str]) -> int:
        """Delete consolidations that reference any of the given memory IDs.

        Returns the number of consolidations deleted.
        """
        if not memory_ids:
            return 0

        cur = self.conn.cursor()
        # Get all consolidations
        cur.execute("SELECT id, memory_ids FROM consolidations")
        to_delete = []

        for row in cur.fetchall():
            consolidation_memory_ids = json.loads(row["memory_ids"])
            # Check if any of the memory_ids to delete are in this consolidation
            if any(mid in consolidation_memory_ids for mid in memory_ids):
                to_delete.append(row["id"])

        # Delete the consolidations
        if to_delete:
            placeholders = ",".join("?" * len(to_delete))
            cur.execute(f"DELETE FROM consolidations WHERE id IN ({placeholders})", to_delete)
            self.conn.commit()

        return len(to_delete)

    # ------------------------------------------------------------------
    # File Tracking
    # ------------------------------------------------------------------

    def get_processed_file(self, path: str) -> Optional[dict]:
        """Get processed file record by path."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM processed_files WHERE path = ?", (path,))
        row = cur.fetchone()
        if row:
            return {
                "path": row["path"],
                "last_modified": row["last_modified"],
                "last_processed": row["last_processed"],
                "content_hash": row["content_hash"],
                "memory_ids": json.loads(row["memory_ids"]),
            }
        return None

    def add_processed_file(
        self, path: str, content_hash: str, memory_ids: List[str]
    ) -> None:
        """Track a newly processed file."""
        cur = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT INTO processed_files (path, last_modified, last_processed, content_hash, memory_ids)
            VALUES (?, ?, ?, ?, ?)
            """,
            (path, now, now, content_hash, json.dumps(memory_ids)),
        )
        self.conn.commit()

    def update_processed_file(
        self, path: str, content_hash: str, memory_ids: List[str]
    ) -> None:
        """Update processed file record after re-ingestion."""
        cur = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute(
            """
            UPDATE processed_files
            SET last_modified = ?, last_processed = ?, content_hash = ?, memory_ids = ?
            WHERE path = ?
            """,
            (now, now, content_hash, json.dumps(memory_ids), path),
        )
        self.conn.commit()

    def list_processed_files(self) -> List[dict]:
        """Get all processed files with their metadata."""
        from pathlib import Path
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM processed_files ORDER BY last_processed DESC"
        )
        files = []
        for row in cur.fetchall():
            file_path = Path(row["path"])
            memory_ids = json.loads(row["memory_ids"])
            files.append({
                "filename": file_path.name,
                "path": row["path"],
                "last_modified": row["last_modified"],
                "last_processed": row["last_processed"],
                "content_hash": row["content_hash"][:16] + "...",  # Truncate hash for readability
                "memory_ids": memory_ids,
                "memory_count": len(memory_ids),
            })
        return files

    def count_processed_files(self) -> int:
        """Get total count of processed files."""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM processed_files")
        return cur.fetchone()[0]

    def delete_memories(self, memory_ids: List[str]) -> int:
        """Delete memories by ID. Returns the number deleted."""
        if not memory_ids:
            return 0

        cur = self.conn.cursor()
        placeholders = ",".join("?" * len(memory_ids))
        cur.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", memory_ids)
        self.conn.commit()
        return len(memory_ids)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_metadata(self, key: str) -> Optional[str]:
        """Get metadata value by key."""
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM metadata WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row else None

    def set_metadata(self, key: str, value: str) -> None:
        """Set or update metadata key-value pair."""
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO metadata (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_memory(row: sqlite3.Row) -> Memory:
        return Memory(
            id=row["id"],
            summary=row["summary"],
            entities=json.loads(row["entities"]),
            topics=json.loads(row["topics"]),
            importance=row["importance"],
            source=row["source"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            consolidated=bool(row["consolidated"]),
        )

    @staticmethod
    def _row_to_consolidation(row: sqlite3.Row) -> Consolidation:
        return Consolidation(
            id=row["id"],
            memory_ids=json.loads(row["memory_ids"]),
            connections=row["connections"],
            insights=row["insights"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )
