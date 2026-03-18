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
