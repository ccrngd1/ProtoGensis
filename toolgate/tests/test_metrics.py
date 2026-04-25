"""Tests for metrics collection."""

import pytest
import time
from pathlib import Path

from toolgate.config import MetricsConfig
from toolgate.metrics import MetricsCollector
from toolgate.schemas import MCPTool, ToolInputSchema


def test_metrics_initialization(temp_dir):
    """Test MetricsCollector initialization."""
    config = MetricsConfig(
        enabled=True,
        db_path=str(temp_dir / "metrics.db")
    )
    metrics = MetricsCollector(config)

    assert metrics.enabled is True
    assert metrics.db_path.exists()


def test_metrics_disabled():
    """Test metrics with disabled config."""
    config = MetricsConfig(enabled=False)
    metrics = MetricsCollector(config)

    # Should not create DB
    assert metrics.enabled is False


def test_count_tokens():
    """Test token counting."""
    config = MetricsConfig(enabled=False)
    metrics = MetricsCollector(config)

    text = "This is a test string"
    tokens = metrics.count_tokens(text)

    assert tokens > 0
    assert isinstance(tokens, int)


def test_count_tokens_empty():
    """Test counting tokens in empty string."""
    config = MetricsConfig(enabled=False)
    metrics = MetricsCollector(config)

    tokens = metrics.count_tokens("")

    assert tokens == 0


def test_count_tool_tokens():
    """Test counting tokens in a tool."""
    config = MetricsConfig(enabled=False)
    metrics = MetricsCollector(config)

    tool = MCPTool(
        name="test_tool",
        description="A test tool with a description",
        inputSchema=ToolInputSchema(
            type="object",
            properties={"param": {"type": "string"}}
        )
    )

    tokens = metrics.count_tool_tokens(tool)

    assert tokens > 0


def test_calculate_tokens_saved(sample_tools):
    """Test calculating token savings."""
    config = MetricsConfig(enabled=False)
    metrics = MetricsCollector(config)

    # Return only 2 of 8 tools
    returned_tools = ["read_file", "write_file"]

    tokens_saved = metrics.calculate_tokens_saved(sample_tools, returned_tools)

    assert tokens_saved > 0


def test_record_event(temp_dir):
    """Test recording a metrics event."""
    config = MetricsConfig(
        enabled=True,
        db_path=str(temp_dir / "metrics.db")
    )
    metrics = MetricsCollector(config)

    metrics.record(
        event_type="list_tools",
        tools_returned=5,
        tokens_saved=1000,
        latency_ms=50.5,
        query_text="test query"
    )

    # Verify event was recorded
    events = metrics.get_recent_events(limit=1)
    assert len(events) == 1
    assert events[0]["event_type"] == "list_tools"


def test_record_tool_call(temp_dir):
    """Test recording a tool call event."""
    config = MetricsConfig(
        enabled=True,
        db_path=str(temp_dir / "metrics.db")
    )
    metrics = MetricsCollector(config)

    metrics.record(
        event_type="call_tool",
        tool_name="read_file",
        latency_ms=25.0
    )

    events = metrics.get_recent_events(limit=1, event_type="call_tool")
    assert len(events) == 1
    assert events[0]["tool_name"] == "read_file"


def test_get_stats_empty(temp_dir):
    """Test getting stats from empty database."""
    config = MetricsConfig(
        enabled=True,
        db_path=str(temp_dir / "metrics.db")
    )
    metrics = MetricsCollector(config)

    stats = metrics.get_stats()

    assert stats["count"] == 0


def test_get_stats_with_data(temp_dir):
    """Test getting aggregated statistics."""
    config = MetricsConfig(
        enabled=True,
        db_path=str(temp_dir / "metrics.db")
    )
    metrics = MetricsCollector(config)

    # Record some events
    metrics.record(
        event_type="list_tools",
        tools_returned=5,
        tokens_saved=1000,
        latency_ms=50.0
    )
    metrics.record(
        event_type="list_tools",
        tools_returned=3,
        tokens_saved=800,
        latency_ms=40.0
    )

    stats = metrics.get_stats(event_type="list_tools")

    assert stats["count"] == 2
    assert stats["total_tokens_saved"] == 1800
    assert stats["avg_latency_ms"] is not None


def test_get_stats_filtered_by_time(temp_dir):
    """Test getting stats filtered by time."""
    config = MetricsConfig(
        enabled=True,
        db_path=str(temp_dir / "metrics.db")
    )
    metrics = MetricsCollector(config)

    # Record an event
    metrics.record(event_type="test", latency_ms=10.0)

    # Get stats from future time (should be 0)
    future_time = time.time() + 1000
    stats = metrics.get_stats(since=future_time)

    assert stats["count"] == 0


def test_get_recent_events(temp_dir):
    """Test getting recent events."""
    config = MetricsConfig(
        enabled=True,
        db_path=str(temp_dir / "metrics.db")
    )
    metrics = MetricsCollector(config)

    # Record multiple events
    for i in range(5):
        metrics.record(
            event_type="test",
            tool_name=f"tool{i}"
        )

    events = metrics.get_recent_events(limit=3)

    assert len(events) == 3


def test_get_recent_events_filtered(temp_dir):
    """Test getting filtered recent events."""
    config = MetricsConfig(
        enabled=True,
        db_path=str(temp_dir / "metrics.db")
    )
    metrics = MetricsCollector(config)

    metrics.record(event_type="list_tools", latency_ms=10.0)
    metrics.record(event_type="call_tool", tool_name="test")
    metrics.record(event_type="list_tools", latency_ms=20.0)

    events = metrics.get_recent_events(event_type="list_tools")

    assert len(events) == 2
    assert all(e["event_type"] == "list_tools" for e in events)
