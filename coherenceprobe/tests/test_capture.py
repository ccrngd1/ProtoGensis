"""Tests for capture backends."""

import pytest
from pathlib import Path
import tempfile
import json

from coherenceprobe.capture import (
    LogCapture,
    FileCapture,
    DecoratorCapture,
    load_outputs_from_jsonl,
    load_outputs_from_directory,
)
from coherenceprobe.models import AgentOutput


def test_log_capture_basic():
    """Test basic LogCapture functionality."""
    capture = LogCapture()

    # Capture some outputs
    capture.capture("agent1", "input1", "output1")
    capture.capture("agent2", "input2", "output2", {"meta": "data"})

    outputs = capture.get_outputs()

    assert len(outputs) == 2
    assert outputs[0].agent == "agent1"
    assert outputs[0].input == "input1"
    assert outputs[0].output == "output1"
    assert outputs[1].metadata == {"meta": "data"}


def test_log_capture_clear():
    """Test clearing LogCapture."""
    capture = LogCapture()
    capture.capture("agent1", "input", "output")

    assert len(capture.get_outputs()) == 1

    capture.clear()
    assert len(capture.get_outputs()) == 0


def test_file_capture(tmp_path):
    """Test FileCapture writes to file."""
    capture_file = tmp_path / "outputs.jsonl"
    capture = FileCapture(capture_file)

    # Capture outputs
    capture.capture("agent1", "input1", "output1")
    capture.capture("agent2", "input2", "output2")

    # Check file was created and contains data
    assert capture_file.exists()

    # Load and verify
    loaded = load_outputs_from_jsonl(capture_file)
    assert len(loaded) == 2
    assert loaded[0].agent == "agent1"
    assert loaded[1].agent == "agent2"


def test_decorator_capture():
    """Test DecoratorCapture wraps functions."""
    capture = DecoratorCapture()

    @capture.agent("test_agent")
    def process(x: int) -> int:
        return x * 2

    result = process(5)
    assert result == 10

    outputs = capture.get_outputs()
    assert len(outputs) == 1
    assert outputs[0].agent == "test_agent"
    assert "5" in outputs[0].input
    assert "10" in outputs[0].output


def test_decorator_capture_with_metadata():
    """Test DecoratorCapture with static metadata."""
    capture = DecoratorCapture()

    @capture.agent("test_agent", metadata={"version": "1.0"})
    def process(text: str) -> str:
        return text.upper()

    result = process("hello")
    assert result == "HELLO"

    outputs = capture.get_outputs()
    assert outputs[0].metadata["version"] == "1.0"


def test_load_from_directory(tmp_path):
    """Test loading outputs from directory."""
    # Create directory with agent output files
    (tmp_path / "agent1.txt").write_text("Output from agent 1")
    (tmp_path / "agent2.txt").write_text("Output from agent 2")

    outputs = load_outputs_from_directory(tmp_path)

    assert len(outputs) == 2
    agents = {o.agent for o in outputs}
    assert agents == {"agent1", "agent2"}


def test_load_from_jsonl_empty(tmp_path):
    """Test loading from empty JSONL file."""
    empty_file = tmp_path / "empty.jsonl"
    empty_file.write_text("")

    outputs = load_outputs_from_jsonl(empty_file)
    assert len(outputs) == 0


def test_load_from_jsonl_with_blank_lines(tmp_path):
    """Test loading from JSONL with blank lines."""
    file_path = tmp_path / "outputs.jsonl"

    output1 = AgentOutput(agent="a1", timestamp="2026-01-01T00:00:00Z",
                         input="in", output="out1")
    output2 = AgentOutput(agent="a2", timestamp="2026-01-01T00:00:01Z",
                         input="in", output="out2")

    # Write with blank lines
    file_path.write_text(
        output1.model_dump_json() + "\n" +
        "\n" +
        output2.model_dump_json() + "\n"
    )

    outputs = load_outputs_from_jsonl(file_path)
    assert len(outputs) == 2
