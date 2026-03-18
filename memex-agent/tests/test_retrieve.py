"""
tests/test_retrieve.py — Tests for the retrieval engine.
"""

import tempfile
import pytest

from memex.store import ExperienceStore
from memex.manifest import IndexManifest
from memex.retrieve import RetrievalEngine


@pytest.fixture
def setup(tmp_path):
    store = ExperienceStore(str(tmp_path / "test.db"))
    manifest = IndexManifest(str(tmp_path / "manifest.json"))
    engine = RetrievalEngine(store, manifest)
    return store, manifest, engine


def test_retrieve_exact_content(setup):
    store, manifest, engine = setup
    original = "This is the exact original content. " * 100
    store.archive(
        key="[test:exact]",
        full_content=original,
        summary="Archived content",
        token_count_original=900,
        token_count_summary=50,
    )
    manifest.add_entry("[test:exact]", "Archived content", tokens_saved=850)

    recovered = engine.retrieve("[test:exact]")
    assert recovered == original


def test_retrieve_missing_key_raises(setup):
    _, _, engine = setup
    with pytest.raises(KeyError, match="no-such-key"):
        engine.retrieve("[test:no-such-key]")


def test_get_summary(setup):
    store, manifest, engine = setup
    store.archive(key="[test:sum]", full_content="full", summary="short")
    manifest.add_entry("[test:sum]", "short summary text", tokens_saved=100)

    summary = engine.get_summary("[test:sum]")
    assert summary == "short summary text"


def test_get_summary_missing(setup):
    _, _, engine = setup
    assert engine.get_summary("[test:ghost]") is None


def test_get_record(setup):
    store, manifest, engine = setup
    store.archive(
        key="[test:rec]",
        full_content="content",
        summary="summary",
        token_count_original=200,
        token_count_summary=20,
        metadata={"tag": "demo"},
    )
    record = engine.get_record("[test:rec]")
    assert record is not None
    assert record["full_content"] == "content"
    assert record["summary"] == "summary"
    assert record["metadata"]["tag"] == "demo"


def test_list_available(setup):
    store, _, engine = setup
    store.archive(key="[test:la1]", full_content="a")
    store.archive(key="[test:la2]", full_content="b")
    available = engine.list_available()
    assert "[test:la1]" in available
    assert "[test:la2]" in available


def test_lossless_unicode(setup):
    """Unicode content should round-trip perfectly."""
    store, _, engine = setup
    unicode_content = "日本語テスト 🎉 Ñoño ✓ <>&\" " * 50
    store.archive(key="[test:unicode]", full_content=unicode_content)
    recovered = engine.retrieve("[test:unicode]")
    assert recovered == unicode_content


def test_lossless_binary_edge_cases(setup):
    """Content with newlines, tabs, backslashes should survive."""
    store, _, engine = setup
    tricky = "line1\nline2\n\ttabbed\n\\backslash\\ \"quotes\" 'apostrophe'"
    store.archive(key="[test:tricky]", full_content=tricky)
    assert engine.retrieve("[test:tricky]") == tricky
