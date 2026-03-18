"""
tests/test_store.py — Tests for the SQLite experience store.
"""

import os
import tempfile
import pytest

from memex.store import ExperienceStore


@pytest.fixture
def store(tmp_path):
    db_path = str(tmp_path / "test_memex.db")
    return ExperienceStore(db_path)


def test_archive_and_retrieve(store):
    store.archive(
        key="[test:foo]",
        full_content="Hello world content",
        summary="Summary here",
        token_count_original=100,
        token_count_summary=10,
    )
    record = store.retrieve("[test:foo]")
    assert record is not None
    assert record["full_content"] == "Hello world content"
    assert record["summary"] == "Summary here"
    assert record["token_count_original"] == 100
    assert record["token_count_summary"] == 10
    assert record["archived_at"] is not None


def test_retrieve_missing_key_returns_none(store):
    result = store.retrieve("[test:does-not-exist]")
    assert result is None


def test_get_full_content(store):
    store.archive(key="[test:bar]", full_content="bar content")
    assert store.get_full_content("[test:bar]") == "bar content"
    assert store.get_full_content("[test:missing]") is None


def test_archive_overwrite(store):
    store.archive(key="[test:ow]", full_content="original")
    store.archive(key="[test:ow]", full_content="updated")
    assert store.get_full_content("[test:ow]") == "updated"


def test_list_keys(store):
    store.archive(key="[test:k1]", full_content="a")
    store.archive(key="[test:k2]", full_content="b")
    keys = store.list_keys()
    assert "[test:k1]" in keys
    assert "[test:k2]" in keys


def test_delete(store):
    store.archive(key="[test:del]", full_content="to delete")
    assert store.delete("[test:del]") is True
    assert store.retrieve("[test:del]") is None
    assert store.delete("[test:del]") is False  # already gone


def test_stats(store):
    store.archive(key="[test:s1]", full_content="x", token_count_original=500, token_count_summary=50)
    store.archive(key="[test:s2]", full_content="y", token_count_original=300, token_count_summary=30)
    stats = store.stats()
    assert stats["count"] == 2
    assert stats["total_original_tokens"] == 800
    assert stats["total_summary_tokens"] == 80
    assert stats["total_tokens_saved"] == 720


def test_metadata_roundtrip(store):
    meta = {"project": "demo", "tags": ["auth", "oauth"]}
    store.archive(key="[test:meta]", full_content="content", metadata=meta)
    record = store.retrieve("[test:meta]")
    assert record["metadata"] == meta


def test_large_content(store):
    big = "A" * 100_000
    store.archive(key="[test:large]", full_content=big)
    assert store.get_full_content("[test:large]") == big
