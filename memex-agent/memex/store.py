"""
store.py — SQLite KV experience store.

Schema:
    experiences(
        key TEXT PRIMARY KEY,
        full_content TEXT,
        summary TEXT,
        token_count_original INT,
        token_count_summary INT,
        metadata JSON,
        archived_at TIMESTAMP
    )
"""

import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import Optional


class ExperienceStore:
    """SQLite-backed key-value store for archived agent experiences."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS experiences (
        key TEXT PRIMARY KEY,
        full_content TEXT NOT NULL,
        summary TEXT,
        token_count_original INTEGER DEFAULT 0,
        token_count_summary INTEGER DEFAULT 0,
        metadata TEXT DEFAULT '{}',
        archived_at TEXT NOT NULL
    );
    """

    def __init__(self, db_path: str = "memex.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database and create tables if needed."""
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else ".", exist_ok=True)
        with self._connect() as conn:
            conn.execute(self.SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def archive(
        self,
        key: str,
        full_content: str,
        summary: str = "",
        token_count_original: int = 0,
        token_count_summary: int = 0,
        metadata: Optional[dict] = None,
    ) -> None:
        """Archive full content under the given key."""
        if metadata is None:
            metadata = {}
        archived_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO experiences
                    (key, full_content, summary, token_count_original, token_count_summary, metadata, archived_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    full_content,
                    summary,
                    token_count_original,
                    token_count_summary,
                    json.dumps(metadata),
                    archived_at,
                ),
            )
            conn.commit()

    def retrieve(self, key: str) -> Optional[dict]:
        """Retrieve a full experience record by key. Returns None if not found."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM experiences WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        record = dict(row)
        record["metadata"] = json.loads(record["metadata"] or "{}")
        return record

    def get_full_content(self, key: str) -> Optional[str]:
        """Return just the full_content for the given key, or None."""
        record = self.retrieve(key)
        return record["full_content"] if record else None

    def list_keys(self) -> list[str]:
        """Return all stored keys."""
        with self._connect() as conn:
            rows = conn.execute("SELECT key FROM experiences ORDER BY archived_at").fetchall()
        return [row["key"] for row in rows]

    def delete(self, key: str) -> bool:
        """Delete an experience. Returns True if a row was deleted."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM experiences WHERE key = ?", (key,))
            conn.commit()
        return cursor.rowcount > 0

    def stats(self) -> dict:
        """Return aggregate stats about the store."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) as count,
                    SUM(token_count_original) as total_original_tokens,
                    SUM(token_count_summary) as total_summary_tokens,
                    SUM(token_count_original - token_count_summary) as total_tokens_saved
                FROM experiences
                """
            ).fetchone()
        return dict(row) if row else {}
