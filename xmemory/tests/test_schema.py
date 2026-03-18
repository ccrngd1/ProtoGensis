"""Tests for SQLite schema initialization."""

import sqlite3
import pytest
from xmemory.schema import init_db


def test_init_creates_all_tables():
    conn = init_db(":memory:")
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "messages" in tables
    assert "episodes" in tables
    assert "semantics" in tables
    assert "themes" in tables
    assert "retrieval_log" in tables


def test_messages_schema():
    conn = init_db(":memory:")
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(messages)").fetchall()
    }
    assert "id" in cols
    assert "session_id" in cols
    assert "content" in cols
    assert "timestamp" in cols
    assert "episode_id" in cols


def test_episodes_schema():
    conn = init_db(":memory:")
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(episodes)").fetchall()
    }
    assert "id" in cols
    assert "session_id" in cols
    assert "summary" in cols
    assert "message_ids" in cols
    assert "created_at" in cols


def test_semantics_schema():
    conn = init_db(":memory:")
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(semantics)").fetchall()
    }
    assert "id" in cols
    assert "fact" in cols
    assert "source_episode_ids" in cols
    assert "created_at" in cols


def test_themes_schema():
    conn = init_db(":memory:")
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(themes)").fetchall()
    }
    assert "id" in cols
    assert "label" in cols
    assert "semantic_ids" in cols
    assert "created_at" in cols


def test_retrieval_log_schema():
    conn = init_db(":memory:")
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(retrieval_log)").fetchall()
    }
    assert "id" in cols
    assert "query" in cols
    assert "retrieved_ids" in cols
    assert "level" in cols
    assert "timestamp" in cols


def test_idempotent_init():
    """Calling init_db twice on the same connection should not fail."""
    conn = init_db(":memory:")
    init_db.__wrapped__ if hasattr(init_db, "__wrapped__") else None
    # Re-run DDL — should be idempotent (CREATE TABLE IF NOT EXISTS)
    from xmemory.schema import DDL
    conn.executescript(DDL)
    conn.commit()

    count = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
    ).fetchone()[0]
    assert count >= 5
