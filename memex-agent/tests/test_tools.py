"""
tests/test_tools.py — Integration tests for the high-level tool interface.
Mocks Bedrock so no real AWS calls are made.
"""

import os
import tempfile
import pytest

import memex.tools as tools_module
from memex.tools import compress_experience, read_experience, get_memex_stats, reset_singletons


MOCK_SUMMARY = "Concise mocked summary of the content. Key finding: it works."
ORIGINAL_CONTENT = "This is a detailed research report. " * 200  # ~5600 chars ≈ 1400 tokens


@pytest.fixture(autouse=True)
def isolate(tmp_path):
    """Each test gets its own db/manifest and fresh singletons."""
    reset_singletons()
    tools_module._DEFAULT_DB_PATH = str(tmp_path / "memex.db")
    tools_module._DEFAULT_MANIFEST_PATH = str(tmp_path / "memex_manifest.json")
    yield
    reset_singletons()


def mock_bedrock(content, context=None):
    return MOCK_SUMMARY


def test_compress_and_read_roundtrip(tmp_path):
    """compress then read should return exact original content."""
    db = str(tmp_path / "rt.db")
    mf = str(tmp_path / "rt.json")

    summary = compress_experience(
        content=ORIGINAL_CONTENT,
        index_key="[test:roundtrip]",
        db_path=db,
        manifest_path=mf,
        _bedrock_caller=mock_bedrock,
    )

    assert MOCK_SUMMARY in summary
    assert "[test:roundtrip]" in summary

    recovered = read_experience("[test:roundtrip]", db_path=db, manifest_path=mf)
    assert recovered == ORIGINAL_CONTENT


def test_compress_returns_short_summary(tmp_path):
    """The returned indexed block must be much shorter than original."""
    from memex.utils import estimate_tokens
    db = str(tmp_path / "short.db")
    mf = str(tmp_path / "short.json")

    result = compress_experience(
        ORIGINAL_CONTENT,
        "[test:compression-ratio]",
        db_path=db,
        manifest_path=mf,
        _bedrock_caller=mock_bedrock,
    )

    original_tokens = estimate_tokens(ORIGINAL_CONTENT)
    result_tokens = estimate_tokens(result)
    assert result_tokens < original_tokens * 0.3


def test_read_experience_missing_key_raises(tmp_path):
    db = str(tmp_path / "m.db")
    mf = str(tmp_path / "m.json")
    with pytest.raises(KeyError):
        read_experience("[test:missing]", db_path=db, manifest_path=mf)


def test_get_memex_stats(tmp_path):
    db = str(tmp_path / "stats.db")
    mf = str(tmp_path / "stats.json")

    compress_experience(ORIGINAL_CONTENT, "[test:stats1]", db_path=db, manifest_path=mf, _bedrock_caller=mock_bedrock)
    compress_experience(ORIGINAL_CONTENT, "[test:stats2]", db_path=db, manifest_path=mf, _bedrock_caller=mock_bedrock)

    stats = get_memex_stats(db_path=db, manifest_path=mf)
    assert stats["count"] == 2
    assert stats["total_original_tokens"] > 0
    assert stats["manifest_entries"] == 2


def test_index_key_normalisation(tmp_path):
    """Keys without brackets should be normalised."""
    db = str(tmp_path / "norm.db")
    mf = str(tmp_path / "norm.json")

    compress_experience(
        ORIGINAL_CONTENT,
        "project:no-brackets",
        db_path=db,
        manifest_path=mf,
        _bedrock_caller=mock_bedrock,
    )

    # Should be stored with brackets
    recovered = read_experience("[project:no-brackets]", db_path=db, manifest_path=mf)
    assert recovered == ORIGINAL_CONTENT


def test_multiple_keys_independent(tmp_path):
    """Different keys should store and retrieve independently."""
    db = str(tmp_path / "multi.db")
    mf = str(tmp_path / "multi.json")

    content_a = "Content A unique identifier XYZ123. " * 100
    content_b = "Content B unique identifier ABC456. " * 100

    compress_experience(content_a, "[test:key-a]", db_path=db, manifest_path=mf, _bedrock_caller=mock_bedrock)
    compress_experience(content_b, "[test:key-b]", db_path=db, manifest_path=mf, _bedrock_caller=mock_bedrock)

    assert read_experience("[test:key-a]", db_path=db, manifest_path=mf) == content_a
    assert read_experience("[test:key-b]", db_path=db, manifest_path=mf) == content_b


def test_overwrite_existing_key(tmp_path):
    """Compressing again with same key should update the entry."""
    db = str(tmp_path / "ow.db")
    mf = str(tmp_path / "ow.json")

    compress_experience("old content " * 100, "[test:overwrite]", db_path=db, manifest_path=mf, _bedrock_caller=mock_bedrock)
    compress_experience("new content " * 100, "[test:overwrite]", db_path=db, manifest_path=mf, _bedrock_caller=mock_bedrock)

    recovered = read_experience("[test:overwrite]", db_path=db, manifest_path=mf)
    assert "new content" in recovered
    assert "old content" not in recovered
