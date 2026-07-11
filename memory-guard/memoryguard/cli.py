"""CLI interface for MemoryGuard."""

import typer
from rich.console import Console
from rich.table import Table
from pathlib import Path
from typing import Optional

from .parsers import parse_memory_file
from .scanner import MemoryGuardScanner
from .reporter import generate_markdown_report, generate_json_report

app = typer.Typer(help="MemoryGuard: Injection attack detection for AI agent memory systems")
console = Console()


@app.command()
def scan(
    memory_file: str = typer.Argument(..., help="Path to memory file (Markdown or JSON)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output report path"),
    format: str = typer.Option("markdown", "--format", "-f", help="Report format: markdown or json"),
    json_output: bool = typer.Option(False, "--json", help="Output results as JSON to stdout"),
):
    """Scan a memory file for injection attacks."""
    try:
        console.print(f"[cyan]Loading memory file: {memory_file}[/cyan]")
        entries = parse_memory_file(memory_file)
        console.print(f"[green]✓ Loaded {len(entries)} entries[/green]")

        console.print("[cyan]Running detection modules...[/cyan]")
        scanner = MemoryGuardScanner()
        results = scanner.scan(entries)

        summary = results["summary"]
        flagged = results["flagged_entries"]

        if json_output:
            import json
            print(json.dumps(results, indent=2))
            return

        table = Table(title="Scan Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        table.add_row("Entries Scanned", str(summary["entries_scanned"]))
        table.add_row("Entries Flagged", str(summary["entries_flagged"]))
        table.add_row("High Risk (≥70)", str(summary["high_risk"]))
        table.add_row("Medium Risk (40-69)", str(summary["medium_risk"]))
        table.add_row("Low Risk (<40)", str(summary["low_risk"]))

        console.print(table)

        if flagged:
            console.print("\n[red]⚠ Issues Detected:[/red]\n")

            for entry in flagged:
                risk_color = "red" if entry["max_risk_score"] >= 70 else "yellow" if entry["max_risk_score"] >= 40 else "green"
                console.print(f"[{risk_color}]● {entry['entry_id']} (Risk: {entry['max_risk_score']})[/{risk_color}]")

                for detection in entry["detections"]:
                    console.print(f"  [{detection['risk_score']}] {detection['reason']}")
                console.print()
        else:
            console.print("\n[green]✅ No security issues detected[/green]")

        if output:
            if format == "json":
                generate_json_report(results, output)
            else:
                generate_markdown_report(results, output)
            console.print(f"[green]✓ Report saved to: {output}[/green]")

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def demo():
    """Run a demonstration with sample data."""
    console.print("[cyan]Running MemoryGuard demo...[/cyan]\n")

    demo_dir = Path(__file__).parent.parent / "demo"
    if not demo_dir.exists():
        console.print("[red]Demo directory not found. Run from project root.[/red]")
        raise typer.Exit(1)

    sample_file = demo_dir / "sample_memory.md"
    if not sample_file.exists():
        console.print(f"[red]Demo file not found: {sample_file}[/red]")
        raise typer.Exit(1)

    scan(str(sample_file))


if __name__ == "__main__":
    app()
