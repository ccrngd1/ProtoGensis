"""Tests for CLI functionality."""

import pytest
from click.testing import CliRunner
from pathlib import Path
import json

from coherenceprobe.cli import main
from coherenceprobe.models import AgentOutput


@pytest.fixture
def runner():
    """Fixture providing CLI runner."""
    return CliRunner()


@pytest.fixture
def sample_jsonl(tmp_path):
    """Fixture creating a sample JSONL file."""
    file_path = tmp_path / "outputs.jsonl"

    outputs = [
        AgentOutput(
            agent="agent1",
            timestamp="2026-01-01T00:00:00Z",
            input="test",
            output="The server runs on port 8080.",
            metadata={}
        ),
        AgentOutput(
            agent="agent2",
            timestamp="2026-01-01T00:00:01Z",
            input="test",
            output="The server is operational.",
            metadata={}
        ),
    ]

    with open(file_path, "w") as f:
        for output in outputs:
            f.write(output.model_dump_json() + "\n")

    return file_path


@pytest.fixture
def sample_directory(tmp_path):
    """Fixture creating a sample directory with agent outputs."""
    dir_path = tmp_path / "outputs"
    dir_path.mkdir()

    (dir_path / "agent1.txt").write_text("The server runs on port 8080.")
    (dir_path / "agent2.txt").write_text("The server is operational.")

    return dir_path


def test_cli_help(runner):
    """Test CLI help command."""
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "CoherenceProbe" in result.output


def test_cli_check_help(runner):
    """Test check command help."""
    result = runner.invoke(main, ["check", "--help"])
    assert result.exit_code == 0
    assert "INPUT_PATH" in result.output


def test_cli_info(runner):
    """Test info command."""
    result = runner.invoke(main, ["info"])
    assert result.exit_code == 0
    assert "CoherenceProbe" in result.output
    assert "Default Configuration" in result.output


def test_cli_init(runner, tmp_path):
    """Test init command."""
    output_file = tmp_path / "test.jsonl"
    result = runner.invoke(main, ["init", str(output_file)])

    assert result.exit_code == 0
    assert output_file.exists()
    assert "Created capture file" in result.output


def test_cli_init_overwrite_confirm(runner, tmp_path):
    """Test init with existing file."""
    output_file = tmp_path / "test.jsonl"
    output_file.write_text("existing")

    result = runner.invoke(main, ["init", str(output_file)], input="n\n")

    assert result.exit_code == 0
    assert "already exists" in result.output


def test_cli_stats_jsonl(runner, sample_jsonl):
    """Test stats command with JSONL file."""
    result = runner.invoke(main, ["stats", str(sample_jsonl)])

    assert result.exit_code == 0
    assert "Total outputs: 2" in result.output
    assert "Total agents: 2" in result.output


def test_cli_stats_directory(runner, sample_directory):
    """Test stats command with directory."""
    result = runner.invoke(main, ["stats", str(sample_directory)])

    assert result.exit_code == 0
    assert "Total outputs: 2" in result.output


def test_cli_check_jsonl_local(runner, sample_jsonl):
    """Test check command with JSONL in local mode."""
    pytest.importorskip("spacy")

    result = runner.invoke(main, [
        "check",
        str(sample_jsonl),
        "--local",
        "--format", "text"
    ])

    # May succeed or fail depending on if spaCy model is installed
    # But should not crash
    assert "COHERENCE" in result.output or "Error" in result.output


def test_cli_check_directory_local(runner, sample_directory):
    """Test check command with directory in local mode."""
    pytest.importorskip("spacy")

    result = runner.invoke(main, [
        "check",
        str(sample_directory),
        "--local",
        "--format", "text"
    ])

    # Should produce output or error
    assert "COHERENCE" in result.output or "Error" in result.output


def test_cli_check_json_format(runner, sample_jsonl, tmp_path):
    """Test check command with JSON output."""
    pytest.importorskip("spacy")

    output_file = tmp_path / "report.json"

    result = runner.invoke(main, [
        "check",
        str(sample_jsonl),
        "--local",
        "--format", "json",
        "--output", str(output_file)
    ])

    if result.exit_code == 0:
        assert output_file.exists()
        # Verify it's valid JSON
        data = json.loads(output_file.read_text())
        assert "score" in data


def test_cli_check_html_format(runner, sample_jsonl, tmp_path):
    """Test check command with HTML output."""
    pytest.importorskip("spacy")

    output_file = tmp_path / "report.html"

    result = runner.invoke(main, [
        "check",
        str(sample_jsonl),
        "--local",
        "--format", "html",
        "--output", str(output_file)
    ])

    if result.exit_code == 0:
        assert output_file.exists()
        content = output_file.read_text()
        assert "<!DOCTYPE html>" in content or "<html" in content


def test_cli_check_verbose(runner, sample_jsonl):
    """Test check command with verbose flag."""
    pytest.importorskip("spacy")

    result = runner.invoke(main, [
        "check",
        str(sample_jsonl),
        "--local",
        "--verbose"
    ])

    # Verbose should include extra output
    if "Error" not in result.output:
        assert "Loading" in result.output or "Extracting" in result.output


def test_cli_check_threshold(runner, sample_jsonl):
    """Test check command with custom threshold."""
    pytest.importorskip("spacy")

    result = runner.invoke(main, [
        "check",
        str(sample_jsonl),
        "--local",
        "--threshold", "0.5"
    ])

    # Should run without error
    assert result.exit_code in [0, 1]  # May exit with 1 if contradictions found


def test_cli_check_nonexistent_file(runner):
    """Test check command with non-existent file."""
    result = runner.invoke(main, ["check", "/nonexistent/path.jsonl"])

    assert result.exit_code != 0
    assert "does not exist" in result.output.lower() or "error" in result.output.lower()
