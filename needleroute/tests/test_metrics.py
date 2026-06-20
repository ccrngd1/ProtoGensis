"""Tests for metrics collection."""

import pytest
import tempfile
from pathlib import Path

from needleroute.config import MetricsConfig
from needleroute.metrics import MetricsCollector


@pytest.fixture
def temp_metrics_db():
    """Create temporary metrics database."""
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


def test_metrics_collector_initialization(temp_metrics_db):
    """Test metrics collector initialization."""
    config = MetricsConfig(enabled=True, db_path=temp_metrics_db)
    collector = MetricsCollector(config)

    assert collector.config == config
    assert Path(temp_metrics_db).exists()


def test_metrics_record_event(temp_metrics_db):
    """Test recording a metrics event."""
    config = MetricsConfig(enabled=True, db_path=temp_metrics_db)
    collector = MetricsCollector(config)

    collector.record(
        event_type="route",
        query="test query",
        selected_tool="read_file",
        confidence=0.85,
        escalated=False,
        latency_ms=12.5,
    )

    # Verify event was recorded
    stats = collector.get_stats(hours=1)
    assert stats["total_routes"] == 1


def test_metrics_disabled(temp_metrics_db):
    """Test that disabled metrics don't record."""
    config = MetricsConfig(enabled=False, db_path=temp_metrics_db)
    collector = MetricsCollector(config)

    collector.record(
        event_type="route",
        query="test",
        selected_tool="test_tool",
    )

    # Stats should return error
    stats = collector.get_stats(hours=1)
    assert "error" in stats


def test_metrics_get_stats(temp_metrics_db):
    """Test getting statistics."""
    config = MetricsConfig(enabled=True, db_path=temp_metrics_db)
    collector = MetricsCollector(config)

    # Record several events
    collector.record(
        event_type="route",
        query="query1",
        selected_tool="tool1",
        confidence=0.9,
        escalated=False,
        latency_ms=10.0,
        tokens_saved=100,
    )

    collector.record(
        event_type="route",
        query="query2",
        selected_tool="tool2",
        confidence=0.5,
        escalated=True,
        escalation_reason="low_confidence",
        latency_ms=50.0,
        tokens_used=200,
    )

    collector.record(
        event_type="route",
        query="query3",
        selected_tool="tool1",
        confidence=0.95,
        escalated=False,
        latency_ms=8.0,
        tokens_saved=120,
    )

    stats = collector.get_stats(hours=1)

    assert stats["total_routes"] == 3
    assert stats["escalated_count"] == 1
    assert stats["escalation_rate"] == pytest.approx(1/3)
    assert stats["total_tokens_saved"] == 220
    assert stats["total_tokens_used"] == 200
    assert "low_confidence" in stats["escalation_reasons"]


def test_metrics_top_tools(temp_metrics_db):
    """Test top tools tracking."""
    config = MetricsConfig(enabled=True, db_path=temp_metrics_db)
    collector = MetricsCollector(config)

    # Record multiple calls to same tool
    for _ in range(5):
        collector.record(
            event_type="route",
            selected_tool="read_file",
        )

    for _ in range(3):
        collector.record(
            event_type="route",
            selected_tool="write_file",
        )

    stats = collector.get_stats(hours=1)

    assert "top_tools" in stats
    assert stats["top_tools"]["read_file"] == 5
    assert stats["top_tools"]["write_file"] == 3


def test_metrics_escalation_reasons(temp_metrics_db):
    """Test escalation reasons tracking."""
    config = MetricsConfig(enabled=True, db_path=temp_metrics_db)
    collector = MetricsCollector(config)

    collector.record(
        event_type="route",
        escalated=True,
        escalation_reason="low_confidence",
    )

    collector.record(
        event_type="route",
        escalated=True,
        escalation_reason="destructive_hint",
    )

    collector.record(
        event_type="route",
        escalated=True,
        escalation_reason="low_confidence",
    )

    stats = collector.get_stats(hours=1)

    reasons = stats["escalation_reasons"]
    assert reasons["low_confidence"] == 2
    assert reasons["destructive_hint"] == 1


def test_metrics_get_recent_events(temp_metrics_db):
    """Test getting recent events."""
    config = MetricsConfig(enabled=True, db_path=temp_metrics_db)
    collector = MetricsCollector(config)

    # Record events
    for i in range(10):
        collector.record(
            event_type="route",
            query=f"query{i}",
            selected_tool=f"tool{i}",
        )

    events = collector.get_recent_events(limit=5)

    assert len(events) == 5
    # Should be in reverse chronological order
    assert events[0]["query"] == "query9"


def test_metrics_average_confidence(temp_metrics_db):
    """Test average confidence calculation."""
    config = MetricsConfig(enabled=True, db_path=temp_metrics_db)
    collector = MetricsCollector(config)

    collector.record(
        event_type="route",
        confidence=0.8,
        escalated=False,
    )

    collector.record(
        event_type="route",
        confidence=0.9,
        escalated=False,
    )

    collector.record(
        event_type="route",
        confidence=0.3,  # Escalated, shouldn't count
        escalated=True,
    )

    stats = collector.get_stats(hours=1)

    # Average should only include non-escalated
    assert stats["avg_confidence"] == pytest.approx(0.85)


def test_metrics_average_latency(temp_metrics_db):
    """Test average latency calculation."""
    config = MetricsConfig(enabled=True, db_path=temp_metrics_db)
    collector = MetricsCollector(config)

    collector.record(event_type="route", latency_ms=10.0)
    collector.record(event_type="route", latency_ms=20.0)
    collector.record(event_type="route", latency_ms=30.0)

    stats = collector.get_stats(hours=1)

    assert stats["avg_latency_ms"] == pytest.approx(20.0)
