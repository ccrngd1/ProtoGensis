"""Tiny sqlite-backed note store."""

import sqlite3


def connect(path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, title TEXT, body TEXT)"
    )
    return conn


def save_note(conn: sqlite3.Connection, title: str, body: str) -> int:
    cur = conn.execute(
        "INSERT INTO notes (title, body) VALUES (?, ?)", (title, body)
    )
    conn.commit()
    return int(cur.lastrowid)


def get_note(conn: sqlite3.Connection, note_id: int):
    cur = conn.execute("SELECT title, body FROM notes WHERE id = ?", (note_id,))
    return cur.fetchone()


def delete_note(conn: sqlite3.Connection, note_id: int) -> bool:
    cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    return cur.rowcount > 0
