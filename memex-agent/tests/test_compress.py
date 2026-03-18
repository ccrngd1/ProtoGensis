"""
tests/test_compress.py — Tests for the compression engine.
Uses mocked Bedrock calls — no real AWS needed.
"""

import tempfile
import pytest
from unittest.mock import patch, MagicMock

from memex.store import ExperienceStore
from memex.manifest import IndexManifest
from memex.compress import CompressionEngine


FAKE_SUMMARY = "Evaluated 3 OAuth2 libraries. Recommend authlib: async, JWT built-in. PKCE required."
LONG_CONTENT = "OAuth research content. " * 200  # ~3200 chars ≈ 800 tokens


@pytest.fixture
def engine(tmp_path):
    store = ExperienceStore(str(tmp_path / "test.db"))
    manifest = IndexManifest(str(tmp_path / "manifest.json"))

    def mock_llm(content, context=None):
        return FAKE_SUMMARY

    return CompressionEngine(store, manifest, bedrock_caller=mock_llm)


@pytest.fixture
def engine_with_store(tmp_path):
    store = ExperienceStore(str(tmp_path / "test.db"))
    manifest = IndexManifest(str(tmp_path / "manifest.json"))

    def mock_llm(content, context=None):
        return FAKE_SUMMARY

    ce = CompressionEngine(store, manifest, bedrock_caller=mock_llm)
    return ce, store, manifest


def test_compress_returns_indexed_summary(engine):
    result = engine.compress(LONG_CONTENT, "[test:oauth]")
    assert "[test:oauth]" in result
    assert FAKE_SUMMARY in result
    assert "Archived:" in result
    assert "Tokens saved:" in result


def test_compress_archives_to_store(engine_with_store):
    ce, store, _ = engine_with_store
    ce.compress(LONG_CONTENT, "[test:store-check]")
    record = store.retrieve("[test:store-check]")
    assert record is not None
    assert record["full_content"] == LONG_CONTENT
    assert record["summary"] == FAKE_SUMMARY


def test_compress_updates_manifest(engine_with_store):
    ce, _, manifest = engine_with_store
    ce.compress(LONG_CONTENT, "[test:manifest-check]")
    entry = manifest.get_entry("[test:manifest-check]")
    assert entry is not None
    assert entry["summary"] == FAKE_SUMMARY
    assert entry["tokens_saved"] > 0


def test_compress_with_context(engine_with_store):
    ce, store, _ = engine_with_store
    ce.compress(LONG_CONTENT, "[test:ctx]", context="OAuth2 comparison")
    record = store.retrieve("[test:ctx]")
    assert record["metadata"].get("context") == "OAuth2 comparison"


def test_compress_token_counts(engine_with_store):
    ce, store, _ = engine_with_store
    ce.compress(LONG_CONTENT, "[test:tokens]")
    record = store.retrieve("[test:tokens]")
    # Original should be more than summary
    assert record["token_count_original"] > record["token_count_summary"]
    assert record["token_count_original"] > 0
    assert record["token_count_summary"] > 0


def test_compress_summary_is_short(engine):
    """The returned indexed block should be much shorter than the original content."""
    result = engine.compress(LONG_CONTENT, "[test:ratio]")
    from memex.utils import estimate_tokens
    original_tokens = estimate_tokens(LONG_CONTENT)
    result_tokens = estimate_tokens(result)
    assert result_tokens < original_tokens * 0.3, (
        f"Expected significant compression but got {result_tokens} vs {original_tokens}"
    )


def test_compress_lossless_recovery(engine_with_store):
    """After compression, the store must return exact original content."""
    ce, store, _ = engine_with_store
    unique_content = "UNIQUE_MARKER_XYZ: " + "detailed content. " * 150
    ce.compress(unique_content, "[test:lossless]")
    recovered = store.get_full_content("[test:lossless]")
    assert recovered == unique_content


def test_bedrock_error_propagates(tmp_path):
    """If the LLM call fails, the error should propagate."""
    store = ExperienceStore(str(tmp_path / "test.db"))
    manifest = IndexManifest(str(tmp_path / "manifest.json"))

    def failing_llm(content, context=None):
        raise RuntimeError("Bedrock unavailable")

    ce = CompressionEngine(store, manifest, bedrock_caller=failing_llm)
    with pytest.raises(RuntimeError, match="Bedrock unavailable"):
        ce.compress(LONG_CONTENT, "[test:fail]")
