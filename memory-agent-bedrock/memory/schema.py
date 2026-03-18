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


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    cur = conn.cursor()
    cur.execute(CREATE_MEMORIES)
    cur.execute(CREATE_CONSOLIDATIONS)
    conn.commit()
