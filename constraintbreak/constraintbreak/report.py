"""Report generation with heatmap, markdown, and JSON output."""

import json
from typing import List, Dict, Any, Optional
from collections import defaultdict
from rich.console import Console
from rich.table import Table
from rich.text import Text

from .engine import ComparisonResult
from .recovery import RecoveryResult


class ReportGenerator:
    """Generate reports from test results."""

    def __init__(self):
        """Initialize report generator."""
        self.console = Console()

    def generate_comparison_heatmap(
        self,
        results: List[ComparisonResult],
        show: bool = True,
    ) -> Table:
        """Generate Rich heatmap for comparison results.

        Args:
            results: List of comparison results
            show: If True, print to console

        Returns:
            Rich Table object
        """
        # Organize results into matrix
        matrix = defaultdict(dict)
        constraints = set()
        tasks = set()

        for result in results:
            matrix[result.constraint_name][result.task_name] = result
            constraints.add(result.constraint_name)
            tasks.add(result.task_name)

        # Create table
        table = Table(title="Constraint Fragility Heatmap", show_header=True)
        table.add_column("Constraint", style="bold")

        for task in sorted(tasks):
            table.add_column(task, justify="center")

        # Add rows
        for constraint in sorted(constraints):
            row = [constraint]
            for task in sorted(tasks):
                result = matrix[constraint].get(task)
                if result:
                    cell = self._format_heatmap_cell(result)
                    row.append(cell)
                else:
                    row.append("—")

            table.add_row(*row)

        if show:
            self.console.print(table)

        return table

    def _format_heatmap_cell(self, result: ComparisonResult) -> Text:
        """Format a single heatmap cell with color.

        Args:
            result: Comparison result

        Returns:
            Rich Text object with color
        """
        severity = result.get_severity()
        win_rate_pct = f"{result.win_rate * 100:.0f}%"

        # Color by severity
        if severity == "none":
            color = "green"
            symbol = "🟢"
        elif severity == "low":
            color = "yellow"
            symbol = "🟡"
        elif severity == "medium":
            color = "orange1"
            symbol = "🟠"
        else:  # high
            color = "red"
            symbol = "🔴"

        return Text(f"{symbol} {win_rate_pct}", style=color)

    def generate_markdown_report(
        self,
        results: List[ComparisonResult],
        provider: str,
        model_name: str,
        output_file: Optional[str] = None,
    ) -> str:
        """Generate markdown report.

        Args:
            results: List of comparison results
            provider: Provider name
            model_name: Model name
            output_file: Optional file to write to

        Returns:
            Markdown string
        """
        # Organize by constraint
        by_constraint = defaultdict(list)
        for result in results:
            by_constraint[result.constraint_name].append(result)

        # Generate markdown
        lines = [
            "# ConstraintBreak Report",
            "",
            f"**Provider:** {provider}",
            f"**Model:** {model_name}",
            "",
            "## Summary",
            "",
            "This report shows how output constraints affect LLM quality, measured via pairwise comparison with position bias correction.",
            "",
            "### Severity Levels",
            "",
            "- 🟢 **None** (<5%): Constraint has minimal impact",
            "- 🟡 **Low** (5-15%): Minor quality degradation",
            "- 🟠 **Medium** (15-30%): Significant quality loss",
            "- 🔴 **High** (>30%): Severe quality degradation",
            "",
            "## Results by Constraint",
            "",
        ]

        for constraint_name in sorted(by_constraint.keys()):
            constraint_results = by_constraint[constraint_name]

            # Calculate aggregate stats
            avg_win_rate = sum(r.win_rate for r in constraint_results) / len(
                constraint_results
            )
            degradation_count = sum(1 for r in constraint_results if r.degradation_detected)

            lines.append(f"### {constraint_name}")
            lines.append("")
            lines.append(f"**Average Win Rate:** {avg_win_rate * 100:.1f}%")
            lines.append(
                f"**Tasks with Degradation:** {degradation_count}/{len(constraint_results)}"
            )
            lines.append("")

            # Recommendation
            if avg_win_rate < 0.05:
                recommendation = "✅ **KEEP** - Minimal impact on quality"
            elif avg_win_rate < 0.15:
                recommendation = "⚠️ **USE TWO-PASS** - Minor degradation, recoverable"
            elif avg_win_rate < 0.30:
                recommendation = "⚠️ **USE TWO-PASS** - Significant degradation"
            else:
                recommendation = "❌ **DROP** - Severe quality loss"

            lines.append(f"**Recommendation:** {recommendation}")
            lines.append("")

            # Task breakdown
            lines.append("| Task | Win Rate | Severity |")
            lines.append("|------|----------|----------|")

            for result in sorted(constraint_results, key=lambda r: r.win_rate, reverse=True):
                severity_icon = {
                    "none": "🟢",
                    "low": "🟡",
                    "medium": "🟠",
                    "high": "🔴",
                }[result.get_severity()]

                lines.append(
                    f"| {result.task_name} | {result.win_rate * 100:.1f}% | {severity_icon} {result.get_severity()} |"
                )

            lines.append("")

        markdown = "\n".join(lines)

        if output_file:
            with open(output_file, "w") as f:
                f.write(markdown)

        return markdown

    def generate_json_report(
        self,
        results: List[ComparisonResult],
        provider: str,
        model_name: str,
        output_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate JSON report.

        Args:
            results: List of comparison results
            provider: Provider name
            model_name: Model name
            output_file: Optional file to write to

        Returns:
            Report dict
        """
        report = {
            "provider": provider,
            "model": model_name,
            "results": [],
        }

        for result in results:
            report["results"].append(
                {
                    "task": result.task_name,
                    "constraint": result.constraint_name,
                    "win_rate": result.win_rate,
                    "degradation_detected": result.degradation_detected,
                    "severity": result.get_severity(),
                    "winner_ab": result.winner_ab,
                    "winner_ba": result.winner_ba,
                }
            )

        if output_file:
            with open(output_file, "w") as f:
                json.dump(report, f, indent=2)

        return report

    def generate_recovery_report(
        self,
        results: List[RecoveryResult],
        provider: str,
        model_name: str,
        constraint_name: str,
    ) -> str:
        """Generate recovery test report.

        Args:
            results: List of recovery results
            provider: Provider name
            model_name: Model name
            constraint_name: Constraint tested

        Returns:
            Markdown string
        """
        lines = [
            "# Two-Pass Recovery Report",
            "",
            f"**Provider:** {provider}",
            f"**Model:** {model_name}",
            f"**Constraint:** {constraint_name}",
            "",
            "## Summary",
            "",
            "Two-pass generation: Generate unconstrained, then rewrite with constraint applied.",
            "",
        ]

        # Calculate aggregate recovery rate
        recovery_rate = sum(1 for r in results if r.two_pass_better) / len(results)

        lines.append(f"**Overall Recovery Rate:** {recovery_rate * 100:.1f}%")
        lines.append("")

        if recovery_rate > 0.8:
            recommendation = "✅ **USE TWO-PASS** - Excellent recovery"
        elif recovery_rate > 0.5:
            recommendation = "⚠️ **TWO-PASS HELPS** - Partial recovery"
        else:
            recommendation = "❌ **DROP CONSTRAINT** - Poor recovery"

        lines.append(f"**Recommendation:** {recommendation}")
        lines.append("")
        lines.append("## Task Results")
        lines.append("")
        lines.append("| Task | Two-Pass Better | Recommendation |")
        lines.append("|------|----------------|----------------|")

        for result in results:
            better = "✅" if result.two_pass_better else "❌"
            lines.append(
                f"| {result.task_name} | {better} | {result.get_recommendation()} |"
            )

        lines.append("")

        return "\n".join(lines)

    def print_summary(self, results: List[ComparisonResult]):
        """Print summary statistics to console.

        Args:
            results: List of comparison results
        """
        total = len(results)
        degraded = sum(1 for r in results if r.degradation_detected)
        avg_win_rate = sum(r.win_rate for r in results) / total if total > 0 else 0

        severity_counts = defaultdict(int)
        for result in results:
            severity_counts[result.get_severity()] += 1

        self.console.print("\n[bold]Summary Statistics[/bold]\n")
        self.console.print(f"Total comparisons: {total}")
        self.console.print(f"Degradation detected: {degraded} ({degraded/total*100:.1f}%)")
        self.console.print(f"Average win rate: {avg_win_rate * 100:.1f}%")
        self.console.print("")
        self.console.print("Severity breakdown:")
        self.console.print(f"  🟢 None: {severity_counts['none']}")
        self.console.print(f"  🟡 Low: {severity_counts['low']}")
        self.console.print(f"  🟠 Medium: {severity_counts['medium']}")
        self.console.print(f"  🔴 High: {severity_counts['high']}")
        self.console.print("")
