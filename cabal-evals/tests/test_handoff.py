"""
Tests for handoff delivery reliability.

Validates handoff JSON structure, delivery, and timing SLAs.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from evaluators.handoff import HandoffEvaluator, HandoffSchema


def test_valid_handoff_schema(sample_handoff_data):
    """Test that valid handoff data passes schema validation."""
    handoff = HandoffSchema(**sample_handoff_data)

    assert handoff.from_agent == "PreCog"
    assert handoff.type == "request"
    assert handoff.priority == "high"


def test_invalid_priority():
    """Test that invalid priority is rejected."""
    with pytest.raises(Exception):
        HandoffSchema(
            **{
                "from": "Agent",
                "type": "request",
                "task": "Test",
                "priority": "super-urgent",  # Invalid
                "timestamp": "2026-03-29T10:00:00Z",
            }
        )


def test_invalid_type():
    """Test that invalid handoff type is rejected."""
    with pytest.raises(Exception):
        HandoffSchema(
            **{
                "from": "Agent",
                "type": "notification",  # Invalid
                "task": "Test",
                "priority": "high",
                "timestamp": "2026-03-29T10:00:00Z",
            }
        )


def test_missing_required_field():
    """Test that missing required field is caught."""
    with pytest.raises(Exception):
        HandoffSchema(
            **{
                "from": "Agent",
                "type": "request",
                # Missing "task"
                "priority": "high",
                "timestamp": "2026-03-29T10:00:00Z",
            }
        )


def test_handoff_file_validation(handoff_file):
    """Test evaluation of handoff file."""
    # Initialize evaluator with the handoff file's parent directory
    evaluator = HandoffEvaluator(handoff_file.parent)
    result = evaluator.evaluate_handoff_file(handoff_file)

    assert result.passed, f"Handoff validation failed: {result.errors}"
    assert result.metadata["from_agent"] == "PreCog"
    assert result.metadata["priority"] == "high"


def test_malformed_json(tmp_path):
    """Test that malformed JSON is detected."""
    bad_file = tmp_path / "bad-handoff.json"
    with open(bad_file, "w") as f:
        f.write("{invalid json")

    evaluator = HandoffEvaluator()
    result = evaluator.evaluate_handoff_file(bad_file)

    assert not result.passed
    assert any("JSON" in error for error in result.errors)


def test_trace_handoff_creation():
    """Test handoff creation in trace."""
    trace_file = Path("traces/precog-research-complete.json")

    with open(trace_file) as f:
        trace = json.load(f)

    evaluator = HandoffEvaluator()
    results = evaluator.evaluate_trace_handoffs(trace)

    # Should have at least one handoff created
    assert len(results) > 0, "Expected handoff creation in trace"

    # Check handoff validity
    for result in results:
        assert result.passed, f"Handoff validation failed: {result.errors}"


def test_handoff_sla():
    """Test SLA checking for handoff delivery."""
    evaluator = HandoffEvaluator()

    request_time = datetime(2026, 3, 29, 10, 0, 0)
    delivery_time = datetime(2026, 3, 29, 11, 30, 0)

    # Should pass within 2 cycles (2 hours)
    assert evaluator.check_handoff_sla(
        request_time, delivery_time, max_cycles=2, cycle_duration_minutes=60
    )

    # Should fail if too late
    late_delivery = datetime(2026, 3, 29, 13, 0, 0)
    assert not evaluator.check_handoff_sla(
        request_time, late_delivery, max_cycles=2, cycle_duration_minutes=60
    )


def test_handoff_filename_convention():
    """Test that handoff filenames follow expected pattern."""
    evaluator = HandoffEvaluator()

    assert evaluator._validate_filename("request-001.json", "request")
    assert evaluator._validate_filename("response-002.json", "response")
    assert not evaluator._validate_filename("wrong-001.json", "request")
    assert not evaluator._validate_filename("request-001.txt", "request")


def test_handoff_delivery_location(temp_handoff_dir, sample_handoff_data):
    """Test that handoff is delivered to correct directory."""
    handoff_file = temp_handoff_dir / "request-test.json"
    with open(handoff_file, "w") as f:
        json.dump(sample_handoff_data, f)

    # Initialize evaluator with the temp handoff directory
    evaluator = HandoffEvaluator(temp_handoff_dir)
    result = evaluator.evaluate_handoff_file(handoff_file)

    assert result.passed, f"Handoff validation failed: {result.errors}"

    # Check delivery location
    assert evaluator._validate_delivery_location(handoff_file)


def test_stale_handoff_warning(temp_handoff_dir):
    """Test that stale handoffs generate warnings."""
    # Create handoff with old timestamp
    old_timestamp = (datetime.now() - timedelta(days=2)).isoformat()
    stale_data = {
        "from": "Agent",
        "type": "request",
        "task": "Old task",
        "priority": "low",
        "timestamp": old_timestamp,
    }

    handoff_file = temp_handoff_dir / "request-stale.json"
    with open(handoff_file, "w") as f:
        json.dump(stale_data, f)

    evaluator = HandoffEvaluator(temp_handoff_dir)
    result = evaluator.evaluate_handoff_file(handoff_file)

    # Should still pass but have warning
    assert result.passed
    assert any("stale" in w.lower() for w in result.warnings)
