"""
SQLite schema initialization for the xMemory 4-level hierarchy.

Tables:
  messages      — raw conversation turns
  episodes      — session-level summaries of message blocks
  semantics     — reusable facts extracted from episodes
  themes        — topic clusters of semantic nodes
  retrieval_log — audit log of all retrieval queries
"""

import sqlite3
from pathlib import Path
from typing import Union


DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT    NOT NULL,
    content    TEXT    NOT NULL,
    timestamp  TEXT    NOT NULL DEFAULT (datetime('now')),
    episode_id INTEGER REFERENCES episodes(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS episodes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    summary     TEXT NOT NULL,
    message_ids TEXT NOT NULL DEFAULT '[]',   -- JSON array of message IDs
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS semantics (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    fact               TEXT NOT NULL,
    source_episode_ids TEXT NOT NULL DEFAULT '[]',  -- JSON array of episode IDs
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS themes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    label        TEXT NOT NULL,
    semantic_ids TEXT NOT NULL DEFAULT '[]',  -- JSON array of semantic IDs
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS retrieval_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    query         TEXT NOT NULL,
    retrieved_ids TEXT NOT NULL DEFAULT '[]',  -- JSON array of IDs
    level         TEXT NOT NULL,               -- "theme"|"semantic"|"episode"|"message"
    timestamp     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for common lookup patterns
CREATE INDEX IF NOT EXISTS idx_messages_session  ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_episode  ON messages(episode_id);
CREATE INDEX IF NOT EXISTS idx_episodes_session  ON episodes(session_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_log_ts  ON retrieval_log(timestamp);
"""


def init_db(db_path: Union[str, Path] = ":memory:") -> sqlite3.Connection:
    """
    Initialize the SQLite database, create tables if they don't exist, and
    return an open connection.

    Args:
        db_path: Path to the SQLite file, or ':memory:' for an in-memory DB.

    Returns:
        An open sqlite3.Connection with row_factory set to sqlite3.Row.
    """
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    conn.commit()
    return conn
