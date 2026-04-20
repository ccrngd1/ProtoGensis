"""Tests for report generator."""

import pytest
import json
import tempfile
from pathlib import Path
from constraintbreak.report import ReportGenerator
from constraintbreak.engine import ComparisonResult


class TestReportGenerator:
    """Test ReportGenerator."""

    @pytest.fixture
    def generator(self):
        """Create report generator."""
        return ReportGenerator()

    @pytest.fixture
    def sample_results(self):
        """Create sample comparison results."""
        return [
            ComparisonResult(
                task_name="task1",
                constraint_name="constraint1",
                unconstrained_response="Unconstrained response",
                constrained_response="Constrained response",
                winner_ab="A",
                winner_ba="B",
                degradation_detected=True,
                win_rate=0.5,
            ),
            ComparisonResult(
                task_name="task2",
                constraint_name="constraint1",
                unconstrained_response="Unconstrained response",
                constrained_response="Constrained response",
                winner_ab="A",
                winner_ba="A",
                degradation_detected=False,
                win_rate=0.0,
            ),
            ComparisonResult(
                task_name="task1",
                constraint_name="constraint2",
                unconstrained_response="Unconstrained response",
                constrained_response="Constrained response",
                winner_ab="B",
                winner_ba="B",
                degradation_detected=True,
                win_rate=1.0,
            ),
        ]

    def test_generator_initialization(self, generator):
        """Test generator initialization."""
        assert generator.console is not None

    def test_generate_comparison_heatmap(self, generator, sample_results):
        """Test heatmap generation."""
        table = generator.generate_comparison_heatmap(sample_results, show=False)

        assert table is not None
        assert table.title == "Constraint Fragility Heatmap"

    def test_format_heatmap_cell(self, generator):
        """Test heatmap cell formatting."""
        # Test each severity level
        result_none = ComparisonResult(
            task_name="test",
            constraint_name="test",
            unconstrained_response="test",
            constrained_response="test",
            winner_ab="B",
            winner_ba="A",
            degradation_detected=False,
            win_rate=0.0,
        )
        cell = generator._format_heatmap_cell(result_none)
        assert "🟢" in cell.plain

        result_low = ComparisonResult(
            task_name="test",
            constraint_name="test",
            unconstrained_response="test",
            constrained_response="test",
            winner_ab="A",
            winner_ba="A",
            degradation_detected=True,
            win_rate=0.1,
        )
        cell = generator._format_heatmap_cell(result_low)
        assert "🟡" in cell.plain

        result_medium = ComparisonResult(
            task_name="test",
            constraint_name="test",
            unconstrained_response="test",
            constrained_response="test",
            winner_ab="A",
            winner_ba="B",
            degradation_detected=True,
            win_rate=0.2,
        )
        cell = generator._format_heatmap_cell(result_medium)
        assert "🟠" in cell.plain

        result_high = ComparisonResult(
            task_name="test",
            constraint_name="test",
            unconstrained_response="test",
            constrained_response="test",
            winner_ab="B",
            winner_ba="B",
            degradation_detected=True,
            win_rate=1.0,
        )
        cell = generator._format_heatmap_cell(result_high)
        assert "🔴" in cell.plain

    def test_generate_markdown_report(self, generator, sample_results):
        """Test markdown report generation."""
        markdown = generator.generate_markdown_report(
            results=sample_results,
            provider="mock",
            model_name="test-model",
        )

        assert "# ConstraintBreak Report" in markdown
        assert "mock" in markdown
        assert "test-model" in markdown
        assert "constraint1" in markdown
        assert "constraint2" in markdown

    def test_generate_markdown_report_to_file(self, generator, sample_results):
        """Test markdown report generation to file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
            output_file = f.name

        try:
            markdown = generator.generate_markdown_report(
                results=sample_results,
                provider="mock",
                model_name="test-model",
                output_file=output_file,
            )

            assert Path(output_file).exists()
            with open(output_file, "r") as f:
                content = f.read()
                assert content == markdown
        finally:
            Path(output_file).unlink()

    def test_generate_json_report(self, generator, sample_results):
        """Test JSON report generation."""
        report = generator.generate_json_report(
            results=sample_results,
            provider="mock",
            model_name="test-model",
        )

        assert report["provider"] == "mock"
        assert report["model"] == "test-model"
        assert len(report["results"]) == 3
        assert all("task" in r for r in report["results"])
        assert all("constraint" in r for r in report["results"])
        assert all("win_rate" in r for r in report["results"])

    def test_generate_json_report_to_file(self, generator, sample_results):
        """Test JSON report generation to file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            output_file = f.name

        try:
            report = generator.generate_json_report(
                results=sample_results,
                provider="mock",
                model_name="test-model",
                output_file=output_file,
            )

            assert Path(output_file).exists()
            with open(output_file, "r") as f:
                content = json.load(f)
                assert content == report
        finally:
            Path(output_file).unlink()

    def test_print_summary(self, generator, sample_results):
        """Test summary printing (should not raise)."""
        # Just test that it doesn't raise
        generator.print_summary(sample_results)
