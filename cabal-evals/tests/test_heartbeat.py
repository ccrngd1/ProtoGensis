"""
Tests for heartbeat triage scenarios.

Validates that agents correctly identify when action is needed vs HEARTBEAT_OK.
"""

import json
from pathlib import Path

import pytest

from evaluators.tool_call import ToolCallEvaluator


def test_heartbeat_ok_scenario():
    """Test that agent correctly returns HEARTBEAT_OK when no handoffs present."""
    trace_file = Path("traces/main-heartbeat-ok.json")

    with open(trace_file) as f:
        trace = json.load(f)

    evaluator = ToolCallEvaluator()
    results = evaluator.evaluate_trace(trace)

    # Should have tool calls for checking handoff directory
    assert len(results) > 0, "Expected tool calls in heartbeat trace"

    # All tool calls should pass validation
    for result in results:
        assert result.passed, f"Tool call failed: {result.errors}"

    # Final message should indicate HEARTBEAT_OK
    final_message = trace["messages"][-1]
    assert "HEARTBEAT_OK" in final_message["content"]


def test_heartbeat_with_handoff():
    """Test that agent processes handoff instead of returning HEARTBEAT_OK."""
    trace_file = Path("traces/main-handoff-process.json")

    with open(trace_file) as f:
        trace = json.load(f)

    evaluator = ToolCallEvaluator()
    results = evaluator.evaluate_trace(trace)

    # Should have multiple tool calls
    assert len(results) >= 3, "Expected multiple tool calls for handoff processing"

    # All tool calls should pass validation
    failed = [r for r in results if not r.passed]
    assert len(failed) == 0, f"Tool calls failed: {[r.errors for r in failed]}"

    # Final message should NOT contain HEARTBEAT_OK
    final_message = trace["messages"][-1]
    assert "HEARTBEAT_OK" not in final_message["content"]

    # Should have processed the handoff
    assert any("processed" in msg["content"].lower() for msg in trace["messages"])


def test_heartbeat_tool_sequence():
    """Test that heartbeat uses correct tool call sequence."""
    trace_file = Path("traces/main-heartbeat-ok.json")

    with open(trace_file) as f:
        trace = json.load(f)

    # Extract tool names
    tool_names = []
    for message in trace["messages"]:
        if message.get("role") == "assistant" and "tool_calls" in message:
            for tool_call in message["tool_calls"]:
                tool_names.append(tool_call["function"]["name"])

    # Should start with checking handoff directory
    assert "file_read" in tool_names, "Expected file_read to check handoffs"


def test_heartbeat_no_destructive_actions():
    """Test that heartbeat never performs destructive actions."""
    from evaluators.safety import SafetyEvaluator

    trace_file = Path("traces/main-heartbeat-ok.json")

    with open(trace_file) as f:
        trace = json.load(f)

    evaluator = SafetyEvaluator()
    result = evaluator.evaluate_trace(trace)

    # Should have no safety violations
    assert result.passed, f"Safety violations found: {result.violations}"
    assert len(result.violations) == 0, "Heartbeat should have no safety violations"


@pytest.mark.parametrize(
    "scenario,expected_outcome",
    [
        ("main-heartbeat-ok.json", "HEARTBEAT_OK"),
        ("main-handoff-process.json", "processed"),
    ],
)
def test_heartbeat_outcomes(scenario: str, expected_outcome: str):
    """Test different heartbeat outcomes."""
    trace_file = Path("traces") / scenario

    if not trace_file.exists():
        pytest.skip(f"Trace file not found: {trace_file}")

    with open(trace_file) as f:
        trace = json.load(f)

    # Check final message contains expected outcome
    final_message = trace["messages"][-1]["content"]
    assert expected_outcome.lower() in final_message.lower()
