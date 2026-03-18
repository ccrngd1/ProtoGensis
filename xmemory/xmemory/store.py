"""
CRUD store for all hierarchy levels in xMemory.

All writes return the newly created/updated object with its database ID.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import List, Optional

from xmemory.models import Episode, Message, RetrievalResult, SemanticNode, Theme


class MemoryStore:
    """Low-level CRUD interface to the xMemory SQLite database."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def add_message(self, msg: Message) -> Message:
        cur = self.conn.execute(
            "INSERT INTO messages (session_id, content, timestamp, episode_id) "
            "VALUES (?, ?, ?, ?)",
            (
                msg.session_id,
                msg.content,
                msg.timestamp.isoformat(),
                msg.episode_id,
            ),
        )
        self.conn.commit()
        msg.id = cur.lastrowid
        return msg

    def add_messages(self, messages: List[Message]) -> List[Message]:
        """Batch insert messages in a single transaction."""
        if not messages:
            return []

        try:
            # Prepare data for batch insert
            data = [
                (m.session_id, m.content, m.timestamp.isoformat(), m.episode_id)
                for m in messages
            ]

            # Execute batch insert
            cursor = self.conn.cursor()
            cursor.executemany(
                "INSERT INTO messages (session_id, content, timestamp, episode_id) "
                "VALUES (?, ?, ?, ?)",
                data
            )

            # Assign IDs to the message objects
            # SQLite doesn't support RETURNING, so we get the starting ID and increment
            start_id = cursor.lastrowid - len(messages) + 1
            for i, msg in enumerate(messages):
                msg.id = start_id + i

            self.conn.commit()
            return messages
        except Exception:
            self.conn.rollback()
            raise

    def get_message(self, message_id: int) -> Optional[Message]:
        row = self.conn.execute(
            "SELECT * FROM messages WHERE id = ?", (message_id,)
        ).fetchone()
        return self._row_to_message(row) if row else None

    def get_messages_by_session(self, session_id: str) -> List[Message]:
        rows = self.conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,),
        ).fetchall()
        return [self._row_to_message(r) for r in rows]

    def get_unprocessed_messages(self) -> List[Message]:
        """Return messages not yet assigned to an episode."""
        rows = self.conn.execute(
            "SELECT * FROM messages WHERE episode_id IS NULL ORDER BY timestamp ASC"
        ).fetchall()
        return [self._row_to_message(r) for r in rows]

    def get_messages_by_ids(self, ids: List[int]) -> List[Message]:
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        rows = self.conn.execute(
            f"SELECT * FROM messages WHERE id IN ({placeholders})", ids
        ).fetchall()
        return [self._row_to_message(r) for r in rows]

    def assign_episode(self, message_ids: List[int], episode_id: int) -> None:
        placeholders = ",".join("?" * len(message_ids))
        self.conn.execute(
            f"UPDATE messages SET episode_id = ? WHERE id IN ({placeholders})",
            [episode_id] + message_ids,
        )
        self.conn.commit()

    def _row_to_message(self, row: sqlite3.Row) -> Message:
        return Message(
            id=row["id"],
            session_id=row["session_id"],
            content=row["content"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            episode_id=row["episode_id"],
        )

    # ------------------------------------------------------------------
    # Episodes
    # ------------------------------------------------------------------

    def add_episode(self, ep: Episode) -> Episode:
        cur = self.conn.execute(
            "INSERT INTO episodes (session_id, summary, message_ids, created_at) "
            "VALUES (?, ?, ?, ?)",
            (
                ep.session_id,
                ep.summary,
                json.dumps(ep.message_ids),
                ep.created_at.isoformat(),
            ),
        )
        self.conn.commit()
        ep.id = cur.lastrowid
        return ep

    def get_episode(self, episode_id: int) -> Optional[Episode]:
        row = self.conn.execute(
            "SELECT * FROM episodes WHERE id = ?", (episode_id,)
        ).fetchone()
        return self._row_to_episode(row) if row else None

    def get_all_episodes(self) -> List[Episode]:
        rows = self.conn.execute(
            "SELECT * FROM episodes ORDER BY created_at ASC"
        ).fetchall()
        return [self._row_to_episode(r) for r in rows]

    def get_episodes_by_ids(self, ids: List[int]) -> List[Episode]:
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        rows = self.conn.execute(
            f"SELECT * FROM episodes WHERE id IN ({placeholders})", ids
        ).fetchall()
        return [self._row_to_episode(r) for r in rows]

    def get_unprocessed_episodes(self) -> List[Episode]:
        """Return episodes not yet referenced by any semantic node."""
        processed_ids = set()
        for row in self.conn.execute("SELECT source_episode_ids FROM semantics").fetchall():
            processed_ids.update(json.loads(row["source_episode_ids"]))
        all_eps = self.get_all_episodes()
        return [e for e in all_eps if e.id not in processed_ids]

    def _row_to_episode(self, row: sqlite3.Row) -> Episode:
        return Episode(
            id=row["id"],
            session_id=row["session_id"],
            summary=row["summary"],
            message_ids=json.loads(row["message_ids"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # ------------------------------------------------------------------
    # Semantics
    # ------------------------------------------------------------------

    def add_semantic(self, node: SemanticNode) -> SemanticNode:
        cur = self.conn.execute(
            "INSERT INTO semantics (fact, source_episode_ids, created_at) "
            "VALUES (?, ?, ?)",
            (
                node.fact,
                json.dumps(node.source_episode_ids),
                node.created_at.isoformat(),
            ),
        )
        self.conn.commit()
        node.id = cur.lastrowid
        return node

    def add_semantics(self, nodes: List[SemanticNode]) -> List[SemanticNode]:
        """Batch insert semantic nodes in a single transaction."""
        if not nodes:
            return []

        try:
            # Prepare data for batch insert
            data = [
                (n.fact, json.dumps(n.source_episode_ids), n.created_at.isoformat())
                for n in nodes
            ]

            # Execute batch insert
            cursor = self.conn.cursor()
            cursor.executemany(
                "INSERT INTO semantics (fact, source_episode_ids, created_at) "
                "VALUES (?, ?, ?)",
                data
            )

            # Assign IDs to the node objects
            start_id = cursor.lastrowid - len(nodes) + 1
            for i, node in enumerate(nodes):
                node.id = start_id + i

            self.conn.commit()
            return nodes
        except Exception:
            self.conn.rollback()
            raise

    def update_semantic(self, node: SemanticNode) -> SemanticNode:
        """Update an existing semantic node (e.g., to merge source_episode_ids)."""
        self.conn.execute(
            "UPDATE semantics SET fact = ?, source_episode_ids = ? WHERE id = ?",
            (node.fact, json.dumps(node.source_episode_ids), node.id),
        )
        self.conn.commit()
        return node

    def get_all_semantics(self) -> List[SemanticNode]:
        rows = self.conn.execute(
            "SELECT * FROM semantics ORDER BY created_at ASC"
        ).fetchall()
        return [self._row_to_semantic(r) for r in rows]

    def get_semantics_by_ids(self, ids: List[int]) -> List[SemanticNode]:
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        rows = self.conn.execute(
            f"SELECT * FROM semantics WHERE id IN ({placeholders})", ids
        ).fetchall()
        return [self._row_to_semantic(r) for r in rows]

    def get_unthemed_semantics(self) -> List[SemanticNode]:
        """Return semantic nodes not yet assigned to any theme."""
        themed_ids: set = set()
        for row in self.conn.execute("SELECT semantic_ids FROM themes").fetchall():
            themed_ids.update(json.loads(row["semantic_ids"]))
        return [s for s in self.get_all_semantics() if s.id not in themed_ids]

    def _row_to_semantic(self, row: sqlite3.Row) -> SemanticNode:
        return SemanticNode(
            id=row["id"],
            fact=row["fact"],
            source_episode_ids=json.loads(row["source_episode_ids"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # ------------------------------------------------------------------
    # Themes
    # ------------------------------------------------------------------

    def add_theme(self, theme: Theme) -> Theme:
        cur = self.conn.execute(
            "INSERT INTO themes (label, semantic_ids, created_at) VALUES (?, ?, ?)",
            (
                theme.label,
                json.dumps(theme.semantic_ids),
                theme.created_at.isoformat(),
            ),
        )
        self.conn.commit()
        theme.id = cur.lastrowid
        return theme

    def update_theme(self, theme: Theme) -> Theme:
        self.conn.execute(
            "UPDATE themes SET label = ?, semantic_ids = ? WHERE id = ?",
            (theme.label, json.dumps(theme.semantic_ids), theme.id),
        )
        self.conn.commit()
        return theme

    def get_all_themes(self) -> List[Theme]:
        rows = self.conn.execute(
            "SELECT * FROM themes ORDER BY created_at ASC"
        ).fetchall()
        return [self._row_to_theme(r) for r in rows]

    def get_theme(self, theme_id: int) -> Optional[Theme]:
        row = self.conn.execute(
            "SELECT * FROM themes WHERE id = ?", (theme_id,)
        ).fetchone()
        return self._row_to_theme(row) if row else None

    def _row_to_theme(self, row: sqlite3.Row) -> Theme:
        return Theme(
            id=row["id"],
            label=row["label"],
            semantic_ids=json.loads(row["semantic_ids"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # ------------------------------------------------------------------
    # Retrieval log
    # ------------------------------------------------------------------

    def log_retrieval(
        self,
        query: str,
        retrieved_ids: List[int],
        level: str,
    ) -> None:
        self.conn.execute(
            "INSERT INTO retrieval_log (query, retrieved_ids, level) VALUES (?, ?, ?)",
            (query, json.dumps(retrieved_ids), level),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "messages": self.conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
            "episodes": self.conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0],
            "semantics": self.conn.execute("SELECT COUNT(*) FROM semantics").fetchone()[0],
            "themes": self.conn.execute("SELECT COUNT(*) FROM themes").fetchone()[0],
        }
