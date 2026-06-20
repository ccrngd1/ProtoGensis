"""Benchmark report generator."""

import json
from typing import Dict, Any
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import print as rprint


def generate_report(results: Dict[str, Any], output_path: str = "benchmark_report.json"):
    """
    Generate benchmark report.

    Args:
        results: Benchmark results from runner
        output_path: Path to save JSON report
    """
    console = Console()

    # Save JSON report
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    console.print(f"\n[green]Benchmark report saved to {output_path}[/green]")

    # Print summary table
    summary = results["summary"]

    console.print("\n[bold cyan]NeedleRoute Benchmark Results[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Total Queries", str(summary["total_queries"]))
    table.add_row("Correct", str(summary["correct"]))
    table.add_row("Accuracy", f"{summary['accuracy']:.1%}")
    table.add_row("Escalated", str(summary["escalated"]))
    table.add_row("Escalation Rate", f"{summary['escalation_rate']:.1%}")
    table.add_row("Avg Latency", f"{summary['avg_latency_ms']:.1f}ms")
    table.add_row("P50 Latency", f"{summary['p50_latency_ms']:.1f}ms")
    table.add_row("P95 Latency", f"{summary['p95_latency_ms']:.1f}ms")

    console.print(table)

    # Show errors
    errors = [r for r in results["results"] if not r["correct"]]

    if errors:
        console.print(f"\n[yellow]Errors: {len(errors)}[/yellow]")

        error_table = Table(show_header=True, header_style="bold red")
        error_table.add_column("Query", style="white", width=40)
        error_table.add_column("Expected", style="green")
        error_table.add_column("Got", style="red")
        error_table.add_column("Reason", style="yellow")

        for error in errors[:10]:  # Show first 10 errors
            reason = error.get("escalation_reason", "low_confidence")
            error_table.add_row(
                error["query"][:40] + "..." if len(error["query"]) > 40 else error["query"],
                error["expected"],
                error["selected"],
                reason
            )

        console.print(error_table)

        if len(errors) > 10:
            console.print(f"\n[dim]... and {len(errors) - 10} more errors (see JSON report)[/dim]")

    console.print()


def generate_comparison_report(
    needleroute_results: Dict[str, Any],
    baseline_results: Dict[str, Any],
    output_path: str = "comparison_report.json"
):
    """
    Generate side-by-side comparison report.

    Args:
        needleroute_results: NeedleRoute benchmark results
        baseline_results: Baseline (e.g., Haiku) benchmark results
        output_path: Path to save comparison report
    """
    console = Console()

    comparison = {
        "needleroute": needleroute_results["summary"],
        "baseline": baseline_results["summary"],
        "improvement": {}
    }

    # Calculate improvements
    nr = needleroute_results["summary"]
    bl = baseline_results["summary"]

    comparison["improvement"] = {
        "accuracy_delta": nr["accuracy"] - bl["accuracy"],
        "latency_speedup": bl["avg_latency_ms"] / nr["avg_latency_ms"] if nr["avg_latency_ms"] > 0 else 0,
        "escalation_reduction": bl["escalation_rate"] - nr["escalation_rate"],
    }

    # Save JSON
    with open(output_path, "w") as f:
        json.dump(comparison, f, indent=2)

    # Print comparison table
    console.print("\n[bold cyan]NeedleRoute vs Baseline Comparison[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("NeedleRoute", justify="right")
    table.add_column("Baseline", justify="right")
    table.add_column("Improvement", justify="right")

    table.add_row(
        "Accuracy",
        f"{nr['accuracy']:.1%}",
        f"{bl['accuracy']:.1%}",
        f"{comparison['improvement']['accuracy_delta']:+.1%}"
    )

    table.add_row(
        "Avg Latency",
        f"{nr['avg_latency_ms']:.1f}ms",
        f"{bl['avg_latency_ms']:.1f}ms",
        f"{comparison['improvement']['latency_speedup']:.2f}x faster" if comparison['improvement']['latency_speedup'] > 1 else "slower"
    )

    table.add_row(
        "Escalation Rate",
        f"{nr['escalation_rate']:.1%}",
        f"{bl['escalation_rate']:.1%}",
        f"{comparison['improvement']['escalation_reduction']:+.1%}"
    )

    console.print(table)
    console.print(f"\n[green]Comparison report saved to {output_path}[/green]\n")
