"""Tests for CLI commands."""

import pytest
from click.testing import CliRunner
import yaml

from toolgate.cli import cli


def test_cli_help():
    """Test CLI help command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "ToolGate" in result.output


def test_cli_version():
    """Test CLI version command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_serve_no_config():
    """Test serve command without config."""
    runner = CliRunner()
    result = runner.invoke(cli, ["serve"])

    assert result.exit_code != 0


def test_serve_invalid_config():
    """Test serve command with invalid config."""
    runner = CliRunner()
    result = runner.invoke(cli, ["serve", "--config", "nonexistent.yaml"])

    assert result.exit_code != 0


def test_index_command(temp_dir):
    """Test index command."""
    runner = CliRunner()

    # Create a minimal config file
    config_path = temp_dir / "config.yaml"
    config_data = {
        "upstream_servers": [
            {
                "name": "test",
                "command": "test-cmd",
                "args": []
            }
        ]
    }

    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    result = runner.invoke(cli, ["index", "--config", str(config_path)])

    # Should run without error (dry-run mode)
    assert "Index Configuration" in result.output


def test_status_command(temp_dir):
    """Test status command."""
    runner = CliRunner()

    # Create a minimal config file
    config_path = temp_dir / "config.yaml"
    config_data = {
        "upstream_servers": [],
        "metrics": {
            "enabled": True,
            "db_path": str(temp_dir / "metrics.db")
        }
    }

    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    result = runner.invoke(cli, ["status", "--config", str(config_path)])

    assert "ToolGate Status" in result.output


def test_status_command_with_limit(temp_dir):
    """Test status command with event limit."""
    runner = CliRunner()

    config_path = temp_dir / "config.yaml"
    config_data = {
        "upstream_servers": [],
        "metrics": {
            "enabled": True,
            "db_path": str(temp_dir / "metrics.db")
        }
    }

    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    result = runner.invoke(cli, ["status", "--config", str(config_path), "--limit", "10"])

    assert result.exit_code == 0
