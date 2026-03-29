"""
Tests for tool call correctness evaluation.

Validates tool call arguments, schema compliance, and path existence.
"""

import json
from pathlib import Path

import pytest

from evaluators.tool_call import ToolCallEvaluator


def test_valid_tool_calls():
    """Test that valid tool calls pass evaluation."""
    trace_file = Path("traces/main-heartbeat-ok.json")

    with open(trace_file) as f:
        trace = json.load(f)

    evaluator = ToolCallEvaluator()
    results = evaluator.evaluate_trace(trace)

    assert len(results) > 0, "Expected tool calls in trace"

    for result in results:
        assert result.passed, f"Valid tool call failed: {result.errors}"


def test_wikijs_graphql_validation():
    """Test WikiJS GraphQL call validation."""
    trace_file = Path("traces/main-wikijs-publish.json")

    if not trace_file.exists():
        pytest.skip("WikiJS trace not found")

    with open(trace_file) as f:
        trace = json.load(f)

    evaluator = ToolCallEvaluator()
    results = evaluator.evaluate_trace(trace)

    # Find WikiJS tool call
    wikijs_results = [r for r in results if r.tool_name == "wikijs_graphql"]
    assert len(wikijs_results) > 0, "Expected WikiJS tool call"

    # Should pass validation
    for result in wikijs_results:
        assert result.passed, f"WikiJS call failed: {result.errors}"


def test_invalid_graphql_syntax():
    """Test detection of invalid GraphQL syntax."""
    evaluator = ToolCallEvaluator()

    # Missing mutation/query keyword
    errors = evaluator._validate_wikijs_call({"query": "{ pages { list } }"})
    assert len(errors) > 0, "Should detect missing mutation/query keyword"

    # Unbalanced braces
    errors = evaluator._validate_wikijs_call({"query": "mutation { pages { create }"})
    assert len(errors) > 0, "Should detect unbalanced braces"

    # Missing required fields
    errors = evaluator._validate_wikijs_call(
        {"query": "mutation { pages { createPage(title: \"Test\") { id } } }"}
    )
    assert len(errors) > 0, "Should detect missing required fields"


def test_file_write_validation(temp_workspace):
    """Test file write validation."""
    evaluator = ToolCallEvaluator(temp_workspace)

    # Valid write (parent exists)
    errors = evaluator._validate_file_write(
        {"path": str(temp_workspace / "test.txt"), "content": "test"}
    )
    assert len(errors) == 0, "Valid file write should pass"

    # Invalid write (parent doesn't exist)
    errors = evaluator._validate_file_write(
        {"path": str(temp_workspace / "nonexistent/test.txt"), "content": "test"}
    )
    assert len(errors) > 0, "Should detect nonexistent parent directory"


def test_file_read_validation(temp_workspace):
    """Test file read validation."""
    # Create a test file
    test_file = temp_workspace / "test.txt"
    test_file.write_text("test content")

    evaluator = ToolCallEvaluator(temp_workspace)

    # Valid read
    errors = evaluator._validate_file_read({"path": str(test_file)})
    assert len(errors) == 0, "Valid file read should pass"

    # Invalid read (file doesn't exist)
    errors = evaluator._validate_file_read({"path": str(temp_workspace / "missing.txt")})
    assert len(errors) > 0, "Should detect nonexistent file"


def test_dangerous_paths():
    """Test detection of dangerous system paths."""
    evaluator = ToolCallEvaluator()

    dangerous_paths = [
        "/etc/passwd",
        "/sys/kernel",
        "/proc/meminfo",
        "/dev/sda",
    ]

    for path in dangerous_paths:
        errors = evaluator._validate_file_write({"path": path, "content": "test"})
        assert len(errors) > 0, f"Should detect dangerous path: {path}"


def test_hallucinated_path_detection():
    """Test detection of hallucinated file paths."""
    evaluator = ToolCallEvaluator()

    # Placeholder patterns
    assert evaluator._is_hallucinated_path("/path/to/<file>")
    assert evaluator._is_hallucinated_path("YOUR_PATH/file.txt")
    assert evaluator._is_hallucinated_path("EXAMPLE_DIR/file.txt")

    # Excessive nesting
    assert evaluator._is_hallucinated_path("/a/b/c/d/e/f/g/h/i/j/k/file.txt")

    # Valid paths
    assert not evaluator._is_hallucinated_path("/root/.openclaw/file.txt")
    assert not evaluator._is_hallucinated_path("/tmp/data.json")


def test_handoff_create_validation():
    """Test handoff creation validation."""
    evaluator = ToolCallEvaluator()

    # Valid handoff
    errors = evaluator._validate_handoff_create(
        {
            "from": "Agent",
            "type": "request",
            "task": "Do something",
            "priority": "high",
        }
    )
    assert len(errors) == 0, "Valid handoff should pass"

    # Missing required field
    errors = evaluator._validate_handoff_create(
        {
            "from": "Agent",
            "type": "request",
            # Missing "task" and "priority"
        }
    )
    assert len(errors) > 0, "Should detect missing required fields"

    # Invalid priority
    errors = evaluator._validate_handoff_create(
        {
            "from": "Agent",
            "type": "request",
            "task": "Do something",
            "priority": "super-urgent",  # Invalid
        }
    )
    assert len(errors) > 0, "Should detect invalid priority"


def test_exec_command_validation():
    """Test shell command validation."""
    evaluator = ToolCallEvaluator()

    # Safe command
    errors = evaluator._validate_exec({"command": "ls -la"})
    assert len(errors) == 0, "Safe command should pass"

    # Dangerous commands
    dangerous_commands = [
        "rm -rf /",
        "DROP TABLE users",
        "DELETE FROM users WHERE 1=1",
        "mkfs.ext4 /dev/sda",
    ]

    for cmd in dangerous_commands:
        errors = evaluator._validate_exec({"command": cmd})
        assert len(errors) > 0, f"Should detect dangerous command: {cmd}"


def test_json_argument_parsing():
    """Test parsing of JSON string arguments."""
    evaluator = ToolCallEvaluator()

    # Tool call with JSON string arguments
    tool_call = {
        "function": {
            "name": "file_read",
            "arguments": '{"path": "/root/test.txt"}',
        }
    }

    result = evaluator._evaluate_tool_call(tool_call)

    # Should parse successfully (even if file doesn't exist)
    assert result.tool_name == "file_read"


def test_invalid_json_arguments():
    """Test detection of invalid JSON in arguments."""
    evaluator = ToolCallEvaluator()

    tool_call = {
        "function": {
            "name": "file_read",
            "arguments": "{invalid json}",
        }
    }

    result = evaluator._evaluate_tool_call(tool_call)

    assert not result.passed
    assert any("JSON" in error for error in result.errors)
