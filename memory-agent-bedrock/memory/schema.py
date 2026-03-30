"""SQLite schema initialization."""
import sqlite3


CREATE_MEMORIES = """
CREATE TABLE IF NOT EXISTS memories (
    id          TEXT PRIMARY KEY,
    summary     TEXT NOT NULL,
    entities    TEXT NOT NULL DEFAULT '[]',
    topics      TEXT NOT NULL DEFAULT '[]',
    importance  REAL NOT NULL DEFAULT 0.5,
    source      TEXT NOT NULL DEFAULT '',
    timestamp   TEXT NOT NULL,
    consolidated INTEGER NOT NULL DEFAULT 0
);
"""

CREATE_CONSOLIDATIONS = """
CREATE TABLE IF NOT EXISTS consolidations (
    id          TEXT PRIMARY KEY,
    memory_ids  TEXT NOT NULL DEFAULT '[]',
    connections TEXT NOT NULL DEFAULT '',
    insights    TEXT NOT NULL DEFAULT '',
    timestamp   TEXT NOT NULL
);
"""

CREATE_PROCESSED_FILES = """
CREATE TABLE IF NOT EXISTS processed_files (
    path            TEXT PRIMARY KEY,
    last_modified   TEXT NOT NULL,
    last_processed  TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    memory_ids      TEXT NOT NULL DEFAULT '[]'
);
"""

CREATE_METADATA = """
CREATE TABLE IF NOT EXISTS metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    cur = conn.cursor()
    cur.execute(CREATE_MEMORIES)
    cur.execute(CREATE_CONSOLIDATIONS)
    cur.execute(CREATE_PROCESSED_FILES)
    cur.execute(CREATE_METADATA)
    conn.commit()
