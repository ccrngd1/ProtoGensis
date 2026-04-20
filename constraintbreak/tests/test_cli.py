"""Tests for CLI interface."""

import pytest
from typer.testing import CliRunner
from constraintbreak.cli import app

runner = CliRunner()


class TestCLI:
    """Test CLI commands."""

    def test_constraints_list(self):
        """Test listing constraints."""
        result = runner.invoke(app, ["constraints"])

        assert result.exit_code == 0
        assert "em_dash_ban" in result.stdout
        assert "colon_ban" in result.stdout

    def test_scan_help(self):
        """Test scan command help."""
        result = runner.invoke(app, ["scan", "--help"])

        assert result.exit_code == 0
        assert "scan" in result.stdout.lower()

    def test_recover_help(self):
        """Test recover command help."""
        result = runner.invoke(app, ["recover", "--help"])

        assert result.exit_code == 0
        assert "recover" in result.stdout.lower()

    def test_report_help(self):
        """Test report command help."""
        result = runner.invoke(app, ["report", "--help"])

        assert result.exit_code == 0
        assert "report" in result.stdout.lower()

    def test_scan_with_mock_provider(self, tmp_path):
        """Test running scan with mock provider."""
        db_file = tmp_path / "test.db"

        result = runner.invoke(
            app,
            [
                "scan",
                "--provider", "mock",
                "--model", "test-model",
                "--db", str(db_file),
                "--constraint", "em_dash_ban",
            ],
        )

        # Should complete successfully
        assert result.exit_code == 0
        assert db_file.exists()

    def test_recover_with_mock_provider(self, tmp_path):
        """Test running recover with mock provider."""
        db_file = tmp_path / "test.db"

        result = runner.invoke(
            app,
            [
                "recover",
                "em_dash_ban",
                "--provider", "mock",
                "--model", "test-model",
                "--db", str(db_file),
            ],
        )

        # Should complete successfully
        assert result.exit_code == 0
        assert db_file.exists()
