"""Tests for gating engine."""

import pytest
from toolgate.config import GatingConfig
from toolgate.gating import GatingEngine


def test_gating_initialization():
    """Test GatingEngine initialization."""
    config = GatingConfig()
    engine = GatingEngine(config)

    assert engine.config == config
    assert len(engine.session_history) == 0


def test_matches_pattern_exact():
    """Test exact pattern matching."""
    config = GatingConfig()
    engine = GatingEngine(config)

    assert engine._matches_pattern("read_file", "read_file")
    assert not engine._matches_pattern("read_file", "write_file")


def test_matches_pattern_wildcard():
    """Test wildcard pattern matching."""
    config = GatingConfig()
    engine = GatingEngine(config)

    assert engine._matches_pattern("read_file", "read_*")
    assert engine._matches_pattern("read_directory", "read_*")
    assert not engine._matches_pattern("write_file", "read_*")


def test_matches_pattern_git():
    """Test git pattern matching."""
    config = GatingConfig()
    engine = GatingEngine(config)

    assert engine._matches_pattern("git_status", "git_*")
    assert engine._matches_pattern("git_commit", "git_*")
    assert not engine._matches_pattern("read_file", "git_*")


def test_forced_includes():
    """Test forced include patterns."""
    config = GatingConfig(always_include=["git_*", "read_file"])
    engine = GatingEngine(config)

    tools = ["read_file", "write_file", "git_status", "git_commit", "other"]
    forced = engine._get_forced_includes(tools)

    assert "read_file" in forced
    assert "git_status" in forced
    assert "git_commit" in forced
    assert "write_file" not in forced


def test_forced_excludes():
    """Test forced exclude patterns."""
    config = GatingConfig(always_exclude=["dangerous_*", "delete_*"])
    engine = GatingEngine(config)

    tools = ["read_file", "dangerous_operation", "delete_all", "safe_tool"]
    forced = engine._get_forced_excludes(tools)

    assert "dangerous_operation" in forced
    assert "delete_all" in forced
    assert "read_file" not in forced


def test_apply_gating_basic():
    """Test basic gating application."""
    config = GatingConfig(top_k=3)
    engine = GatingEngine(config)

    scores = {
        "tool1": 0.9,
        "tool2": 0.8,
        "tool3": 0.7,
        "tool4": 0.6,
        "tool5": 0.5,
    }
    available = list(scores.keys())

    result = engine.apply_gating(scores, available)

    assert len(result.tools) == 3
    assert "tool1" in result.tools
    assert "tool2" in result.tools
    assert "tool3" in result.tools


def test_apply_gating_with_forced_include():
    """Test gating with forced includes."""
    config = GatingConfig(top_k=2, always_include=["tool5"])
    engine = GatingEngine(config)

    scores = {
        "tool1": 0.9,
        "tool2": 0.8,
        "tool3": 0.7,
        "tool5": 0.1,  # Low score but forced
    }
    available = list(scores.keys())

    result = engine.apply_gating(scores, available)

    assert "tool5" in result.tools
    assert "tool5" in result.forced_include


def test_apply_gating_with_forced_exclude():
    """Test gating with forced excludes."""
    config = GatingConfig(top_k=5, always_exclude=["tool2"])
    engine = GatingEngine(config)

    scores = {
        "tool1": 0.9,
        "tool2": 0.8,  # High score but excluded
        "tool3": 0.7,
        "tool4": 0.6,
    }
    available = list(scores.keys())

    result = engine.apply_gating(scores, available)

    assert "tool2" not in result.tools
    assert "tool2" in result.forced_exclude


def test_session_boost():
    """Test session boost for recently used tools."""
    config = GatingConfig(top_k=3, session_boost=0.2)
    engine = GatingEngine(config)

    # Record some tool calls
    engine.record_tool_call("tool3")
    engine.record_tool_call("tool3")

    scores = {
        "tool1": 0.9,
        "tool2": 0.85,
        "tool3": 0.7,  # Should get boosted to 0.9
        "tool4": 0.6,
    }
    available = list(scores.keys())

    result = engine.apply_gating(scores, available)

    assert "tool3" in result.tools
    assert "tool3" in result.boosted


def test_record_tool_call():
    """Test recording tool calls."""
    config = GatingConfig(session_window=3)
    engine = GatingEngine(config)

    engine.record_tool_call("tool1")
    engine.record_tool_call("tool2")
    engine.record_tool_call("tool3")

    assert len(engine.session_history) == 3


def test_session_window_limit():
    """Test session window limits history."""
    config = GatingConfig(session_window=2)
    engine = GatingEngine(config)

    engine.record_tool_call("tool1")
    engine.record_tool_call("tool2")
    engine.record_tool_call("tool3")

    # Should only keep last 2
    assert len(engine.session_history) == 2
    assert "tool2" in engine.session_history
    assert "tool3" in engine.session_history


def test_get_session_stats():
    """Test getting session statistics."""
    config = GatingConfig()
    engine = GatingEngine(config)

    engine.record_tool_call("tool1")
    engine.record_tool_call("tool2")
    engine.record_tool_call("tool1")

    stats = engine.get_session_stats()

    assert stats["total_calls"] == 3
    assert stats["unique_tools"] == 2
