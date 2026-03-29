#!/usr/bin/env python3
"""
Markdown report generator for cabal-evals results.

Reads results JSON and produces markdown summary with pass/fail rates,
failure breakdowns, and trend data. Output suitable for WikiJS publishing.
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class ReportGenerator:
    """Generates markdown reports from evaluation results."""

    def __init__(self, results_dir: Path):
        """
        Initialize the report generator.

        Args:
            results_dir: Directory containing results JSON files
        """
        self.results_dir = results_dir

    def generate_summary_report(self) -> str:
        """
        Generate a summary report across all evaluation results.

        Returns:
            Markdown formatted report
        """
        # Load all result files
        results = self._load_all_results()

        if not results:
            return "# Evaluation Report\n\nNo evaluation results found.\n"

        # Aggregate statistics
        stats = self._aggregate_statistics(results)

        # Generate report sections
        report = self._build_report(stats, results)

        return report

    def generate_detailed_report(self, result_file: Path) -> str:
        """
        Generate a detailed report for a single result file.

        Args:
            result_file: Path to results JSON file

        Returns:
            Markdown formatted detailed report
        """
        with open(result_file) as f:
            result = json.load(f)

        report = f"# Detailed Evaluation Report\n\n"
        report += f"**Result File:** `{result_file.name}`\n"
        report += f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        # Add details based on result type
        if "total_tool_calls" in result:
            report += self._format_tool_call_details(result)
        elif "total_handoffs" in result:
            report += self._format_handoff_details(result)
        elif "total_violations" in result:
            report += self._format_safety_details(result)
        elif "total_checks" in result:
            report += self._format_hallucination_details(result)
        elif "overall_score" in result:
            report += self._format_completeness_details(result)

        return report

    def _load_all_results(self) -> List[Dict[str, Any]]:
        """Load all JSON result files from results directory."""
        results = []

        if not self.results_dir.exists():
            return results

        for result_file in self.results_dir.glob("*.json"):
            try:
                with open(result_file) as f:
                    data = json.load(f)
                    data["_source_file"] = result_file.name
                    results.append(data)
            except Exception as e:
                print(f"Warning: Could not load {result_file}: {e}", file=sys.stderr)

        return results

    def _aggregate_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate statistics across all results."""
        stats = {
            "total_evaluations": len(results),
            "passed": 0,
            "failed": 0,
            "by_type": defaultdict(lambda: {"passed": 0, "failed": 0, "total": 0}),
            "tool_calls": {"total": 0, "passed": 0, "failed": 0},
            "handoffs": {"total": 0, "passed": 0, "failed": 0},
            "safety": {"total": 0, "passed": 0, "violations": 0},
            "hallucination": {"total_checks": 0, "failed_checks": 0},
            "completeness": {"scores": []},
        }

        for result in results:
            # Overall pass/fail
            if result.get("passed", False):
                stats["passed"] += 1
            else:
                stats["failed"] += 1

            # Type-specific aggregation
            eval_type = self._identify_eval_type(result)
            type_stats = stats["by_type"][eval_type]
            type_stats["total"] += 1

            if result.get("passed", False):
                type_stats["passed"] += 1
            else:
                type_stats["failed"] += 1

            # Detailed aggregation
            if "total_tool_calls" in result:
                stats["tool_calls"]["total"] += result["total_tool_calls"]
                stats["tool_calls"]["passed"] += result.get("passed", 0)
                stats["tool_calls"]["failed"] += result.get("failed", 0)

            if "total_handoffs" in result:
                stats["handoffs"]["total"] += result["total_handoffs"]
                stats["handoffs"]["passed"] += result.get("passed", 0)
                stats["handoffs"]["failed"] += result.get("failed", 0)

            if "total_violations" in result:
                stats["safety"]["total"] += 1
                if result.get("passed", False):
                    stats["safety"]["passed"] += 1
                stats["safety"]["violations"] += result["total_violations"]

            if "total_checks" in result:
                stats["hallucination"]["total_checks"] += result["total_checks"]
                stats["hallucination"]["failed_checks"] += result.get("failed_checks", 0)

            if "overall_score" in result:
                stats["completeness"]["scores"].append(result["overall_score"])

        return stats

    def _identify_eval_type(self, result: Dict[str, Any]) -> str:
        """Identify the evaluation type from result structure."""
        if "total_tool_calls" in result:
            return "tool_calls"
        elif "total_handoffs" in result:
            return "handoffs"
        elif "total_violations" in result:
            return "safety"
        elif "total_checks" in result:
            return "hallucination"
        elif "overall_score" in result:
            return "completeness"
        else:
            return "unknown"

    def _build_report(
        self, stats: Dict[str, Any], results: List[Dict[str, Any]]
    ) -> str:
        """Build the complete markdown report."""
        report = "# CABAL Agent Evaluation Report\n\n"
        report += f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"**Total Evaluations:** {stats['total_evaluations']}\n\n"

        # Executive summary
        report += "## Executive Summary\n\n"
        overall_pass_rate = (
            stats["passed"] / stats["total_evaluations"]
            if stats["total_evaluations"] > 0
            else 0
        )
        report += f"- **Overall Pass Rate:** {overall_pass_rate:.1%}\n"
        report += f"- **Passed:** {stats['passed']}\n"
        report += f"- **Failed:** {stats['failed']}\n\n"

        if overall_pass_rate >= 0.9:
            report += "✅ **Status:** Excellent - agents operating reliably\n\n"
        elif overall_pass_rate >= 0.75:
            report += "⚠️ **Status:** Good - some issues need attention\n\n"
        else:
            report += "❌ **Status:** Needs Improvement - significant reliability issues\n\n"

        # Evaluation breakdown by type
        report += "## Evaluation Breakdown\n\n"
        report += "| Dimension | Total | Passed | Failed | Pass Rate |\n"
        report += "|-----------|-------|--------|--------|-----------|\n"

        for eval_type, type_stats in sorted(stats["by_type"].items()):
            pass_rate = (
                type_stats["passed"] / type_stats["total"] if type_stats["total"] > 0 else 0
            )
            report += (
                f"| {eval_type.title()} | {type_stats['total']} | "
                f"{type_stats['passed']} | {type_stats['failed']} | "
                f"{pass_rate:.1%} |\n"
            )

        report += "\n"

        # Detailed sections
        if stats["tool_calls"]["total"] > 0:
            report += self._format_tool_call_summary(stats["tool_calls"])

        if stats["handoffs"]["total"] > 0:
            report += self._format_handoff_summary(stats["handoffs"])

        if stats["safety"]["total"] > 0:
            report += self._format_safety_summary(stats["safety"])

        if stats["hallucination"]["total_checks"] > 0:
            report += self._format_hallucination_summary(stats["hallucination"])

        if stats["completeness"]["scores"]:
            report += self._format_completeness_summary(stats["completeness"])

        # Failures requiring attention
        report += self._format_failure_analysis(results)

        # Recommendations
        report += self._generate_recommendations(stats)

        return report

    def _format_tool_call_summary(self, tool_stats: Dict[str, int]) -> str:
        """Format tool call statistics."""
        pass_rate = (
            tool_stats["passed"] / tool_stats["total"] if tool_stats["total"] > 0 else 0
        )

        section = "### Tool Call Validation\n\n"
        section += f"- **Total Tool Calls:** {tool_stats['total']}\n"
        section += f"- **Valid:** {tool_stats['passed']}\n"
        section += f"- **Invalid:** {tool_stats['failed']}\n"
        section += f"- **Pass Rate:** {pass_rate:.1%}\n\n"

        return section

    def _format_handoff_summary(self, handoff_stats: Dict[str, int]) -> str:
        """Format handoff statistics."""
        pass_rate = (
            handoff_stats["passed"] / handoff_stats["total"]
            if handoff_stats["total"] > 0
            else 0
        )

        section = "### Handoff Delivery\n\n"
        section += f"- **Total Handoffs:** {handoff_stats['total']}\n"
        section += f"- **Valid:** {handoff_stats['passed']}\n"
        section += f"- **Invalid:** {handoff_stats['failed']}\n"
        section += f"- **Pass Rate:** {pass_rate:.1%}\n\n"

        return section

    def _format_safety_summary(self, safety_stats: Dict[str, int]) -> str:
        """Format safety statistics."""
        section = "### Safety Gates\n\n"
        section += f"- **Evaluations:** {safety_stats['total']}\n"
        section += f"- **Passed:** {safety_stats['passed']}\n"
        section += f"- **Total Violations:** {safety_stats['violations']}\n"

        if safety_stats["violations"] > 0:
            section += "\n⚠️ **Safety violations detected - review required**\n"

        section += "\n"
        return section

    def _format_hallucination_summary(self, hall_stats: Dict[str, int]) -> str:
        """Format hallucination detection statistics."""
        pass_rate = (
            (hall_stats["total_checks"] - hall_stats["failed_checks"])
            / hall_stats["total_checks"]
            if hall_stats["total_checks"] > 0
            else 0
        )

        section = "### Hallucination Detection\n\n"
        section += f"- **Total Checks:** {hall_stats['total_checks']}\n"
        section += f"- **Passed:** {hall_stats['total_checks'] - hall_stats['failed_checks']}\n"
        section += f"- **Failed:** {hall_stats['failed_checks']}\n"
        section += f"- **Accuracy:** {pass_rate:.1%}\n\n"

        return section

    def _format_completeness_summary(self, comp_stats: Dict[str, List[float]]) -> str:
        """Format completeness statistics."""
        scores = comp_stats["scores"]
        avg_score = sum(scores) / len(scores) if scores else 0

        section = "### Output Completeness\n\n"
        section += f"- **Evaluations:** {len(scores)}\n"
        section += f"- **Average Score:** {avg_score:.2f}\n"
        section += f"- **Min Score:** {min(scores):.2f}\n" if scores else ""
        section += f"- **Max Score:** {max(scores):.2f}\n\n" if scores else ""

        return section

    def _format_failure_analysis(self, results: List[Dict[str, Any]]) -> str:
        """Analyze and format failure details."""
        section = "## Failures Requiring Attention\n\n"

        failures = [r for r in results if not r.get("passed", False)]

        if not failures:
            section += "✅ No failures detected.\n\n"
            return section

        section += f"Found {len(failures)} failed evaluation(s):\n\n"

        for failure in failures[:10]:  # Limit to top 10
            eval_type = self._identify_eval_type(failure)
            source = failure.get("_source_file", "unknown")

            section += f"### {eval_type.title()} - {source}\n\n"

            # Add type-specific details
            if "errors" in failure:
                section += "**Errors:**\n"
                for error in failure["errors"][:5]:
                    section += f"- {error}\n"
                section += "\n"

            if "violations" in failure and failure["violations"]:
                section += "**Violations:**\n"
                for violation in failure["violations"][:5]:
                    section += f"- **{violation.get('severity', 'unknown').upper()}:** "
                    section += f"{violation.get('message', 'No message')}\n"
                section += "\n"

        return section

    def _generate_recommendations(self, stats: Dict[str, Any]) -> str:
        """Generate recommendations based on evaluation results."""
        section = "## Recommendations\n\n"

        recommendations = []

        # Tool call issues
        if stats["tool_calls"]["total"] > 0:
            tool_pass_rate = stats["tool_calls"]["passed"] / stats["tool_calls"]["total"]
            if tool_pass_rate < 0.9:
                recommendations.append(
                    "**Tool Call Validation:** Pass rate below 90%. Review tool call schemas "
                    "and ensure agents use correct argument formats."
                )

        # Safety violations
        if stats["safety"]["violations"] > 0:
            recommendations.append(
                "**Safety Violations:** Destructive commands or credential leaks detected. "
                "Review agent prompts and add safety constraints."
            )

        # Hallucination rate
        if stats["hallucination"]["total_checks"] > 0:
            hall_pass_rate = (
                stats["hallucination"]["total_checks"]
                - stats["hallucination"]["failed_checks"]
            ) / stats["hallucination"]["total_checks"]
            if hall_pass_rate < 0.9:
                recommendations.append(
                    "**Hallucination Detection:** URL/path verification rate below 90%. "
                    "Agents may be citing invalid sources or hallucinating file paths."
                )

        # Completeness scores
        if stats["completeness"]["scores"]:
            avg_score = sum(stats["completeness"]["scores"]) / len(
                stats["completeness"]["scores"]
            )
            if avg_score < 0.8:
                recommendations.append(
                    "**Output Completeness:** Average completeness score below 80%. "
                    "Review agent outputs for missing sections or insufficient detail."
                )

        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                section += f"{i}. {rec}\n\n"
        else:
            section += "✅ No critical issues identified. Continue monitoring.\n\n"

        return section

    def _format_tool_call_details(self, result: Dict[str, Any]) -> str:
        """Format detailed tool call results."""
        section = "## Tool Call Validation Results\n\n"
        section += f"- **Total Tool Calls:** {result['total_tool_calls']}\n"
        section += f"- **Passed:** {result['passed']}\n"
        section += f"- **Failed:** {result['failed']}\n"
        section += f"- **Pass Rate:** {result['pass_rate']:.1%}\n\n"

        if result.get("results"):
            section += "### Individual Results\n\n"
            for res in result["results"]:
                status = "✅" if res["passed"] else "❌"
                section += f"{status} **{res['tool_name']}**\n"
                if res.get("errors"):
                    for error in res["errors"]:
                        section += f"  - Error: {error}\n"
                section += "\n"

        return section

    def _format_handoff_details(self, result: Dict[str, Any]) -> str:
        """Format detailed handoff results."""
        section = "## Handoff Validation Results\n\n"
        section += f"- **Total Handoffs:** {result['total_handoffs']}\n"
        section += f"- **Passed:** {result['passed']}\n"
        section += f"- **Failed:** {result['failed']}\n\n"

        return section

    def _format_safety_details(self, result: Dict[str, Any]) -> str:
        """Format detailed safety results."""
        section = "## Safety Evaluation Results\n\n"
        section += f"- **Passed:** {'Yes' if result['passed'] else 'No'}\n"
        section += f"- **Total Violations:** {result['total_violations']}\n"
        section += f"- **Critical:** {result.get('critical_violations', 0)}\n"
        section += f"- **High:** {result.get('high_violations', 0)}\n\n"

        if result.get("violations"):
            section += "### Violations\n\n"
            for violation in result["violations"]:
                section += f"**{violation['severity'].upper()}** - {violation['category']}\n"
                section += f"- {violation['message']}\n"
                section += f"- Location: {violation['location']}\n\n"

        return section

    def _format_hallucination_details(self, result: Dict[str, Any]) -> str:
        """Format detailed hallucination results."""
        section = "## Hallucination Detection Results\n\n"
        section += f"- **Total Checks:** {result['total_checks']}\n"
        section += f"- **Failed:** {result['failed_checks']}\n"
        section += f"- **Pass Rate:** {result['pass_rate']:.1%}\n\n"

        return section

    def _format_completeness_details(self, result: Dict[str, Any]) -> str:
        """Format detailed completeness results."""
        section = "## Completeness Evaluation Results\n\n"
        section += f"- **Overall Score:** {result['overall_score']:.2f}\n"
        section += f"- **Passed:** {'Yes' if result['passed'] else 'No'}\n\n"

        if result.get("checks"):
            section += "### Individual Checks\n\n"
            for check in result["checks"]:
                status = "✅" if check["passed"] else "❌"
                section += f"{status} **{check['check_name']}** (score: {check['score']:.2f})\n"
                section += f"  - {check['details']}\n\n"

        return section


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate evaluation reports")
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results"),
        help="Directory containing result JSON files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (default: print to stdout)",
    )
    parser.add_argument(
        "--detailed",
        type=Path,
        help="Generate detailed report for specific result file",
    )

    args = parser.parse_args()

    generator = ReportGenerator(args.results_dir)

    if args.detailed:
        report = generator.generate_detailed_report(args.detailed)
    else:
        report = generator.generate_summary_report()

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            f.write(report)
        print(f"Report generated: {args.output}")
    else:
        print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
