"""Rich CLI for ToolGate management."""

import asyncio
import sys
import time
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from toolgate.config import ToolGateConfig
from toolgate.proxy import run_proxy
from toolgate.index import ToolIndex
from toolgate.metrics import MetricsCollector

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """ToolGate - MCP proxy for dynamic tool gating."""
    pass


@cli.command()
@click.option(
    "--config",
    "-c",
    required=True,
    type=click.Path(exists=True),
    help="Path to config YAML file",
)
def serve(config: str):
    """Start the ToolGate proxy server."""
    try:
        cfg = ToolGateConfig.from_yaml(config)
        console.print(Panel.fit(
            "[bold green]Starting ToolGate proxy...[/bold green]",
            title="ToolGate"
        ))
        asyncio.run(run_proxy(cfg))
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}", style="red")
        sys.exit(1)


@cli.command()
@click.option(
    "--config",
    "-c",
    required=True,
    type=click.Path(exists=True),
    help="Path to config YAML file",
)
def index(config: str):
    """Build and display the tool index."""
    try:
        cfg = ToolGateConfig.from_yaml(config)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Building index...", total=None)

            # This is a simplified version - in production would connect to servers
            console.print("\n[yellow]Note: This is a dry-run. Use 'serve' to build real index.[/yellow]")

            progress.update(task, completed=True)

        # Display config
        table = Table(title="Index Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Model", cfg.index.model_name)
        table.add_row("Similarity", cfg.index.similarity_metric)
        table.add_row("Top-K", str(cfg.gating.top_k))
        table.add_row("Session Boost", f"{cfg.gating.session_boost:.2f}")

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}", style="red")
        sys.exit(1)


@cli.command()
@click.option(
    "--config",
    "-c",
    required=True,
    type=click.Path(exists=True),
    help="Path to config YAML file",
)
@click.option(
    "--limit",
    "-n",
    default=20,
    type=int,
    help="Number of recent events to show",
)
def status(config: str, limit: int):
    """Show proxy status and metrics."""
    try:
        cfg = ToolGateConfig.from_yaml(config)
        cfg.expand_paths()

        metrics = MetricsCollector(cfg.metrics)

        # Get overall stats
        stats = metrics.get_stats()

        # Display summary
        table = Table(title="ToolGate Status")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Events", str(stats.get("count", 0)))
        table.add_row(
            "Avg Latency",
            f"{stats.get('avg_latency_ms', 0):.2f} ms" if stats.get('avg_latency_ms') else "N/A"
        )
        table.add_row(
            "Total Tokens Saved",
            f"{stats.get('total_tokens_saved', 0):,}"
        )
        table.add_row(
            "Avg Tools Returned",
            f"{stats.get('avg_tools_returned', 0):.1f}" if stats.get('avg_tools_returned') else "N/A"
        )

        console.print(table)

        # Get recent events
        if limit > 0:
            events = metrics.get_recent_events(limit=limit)

            if events:
                console.print(f"\n[bold]Recent Events (last {len(events)}):[/bold]")
                events_table = Table()
                events_table.add_column("Type", style="cyan")
                events_table.add_column("Tool", style="yellow")
                events_table.add_column("Latency", style="green")
                events_table.add_column("Tokens Saved", style="magenta")

                for event in events[:limit]:
                    events_table.add_row(
                        event.get("event_type", ""),
                        event.get("tool_name", "-") or "-",
                        f"{event.get('latency_ms', 0):.1f} ms" if event.get('latency_ms') else "-",
                        str(event.get("tokens_saved", "-")) if event.get("tokens_saved") else "-",
                    )

                console.print(events_table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}", style="red")
        sys.exit(1)


@cli.command()
@click.option(
    "--benchmark-dir",
    "-d",
    default="./benchmark",
    type=click.Path(exists=True),
    help="Path to benchmark directory",
)
def benchmark(benchmark_dir: str):
    """Run benchmark suite."""
    try:
        benchmark_path = Path(benchmark_dir)
        run_script = benchmark_path / "run.py"

        if not run_script.exists():
            console.print(
                f"[bold red]Error:[/bold red] Benchmark script not found at {run_script}",
                style="red"
            )
            sys.exit(1)

        console.print(Panel.fit(
            "[bold green]Running ToolGate benchmark...[/bold green]",
            title="Benchmark"
        ))

        # Import and run benchmark
        import importlib.util
        spec = importlib.util.spec_from_file_location("benchmark_run", run_script)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, "run_benchmark"):
                asyncio.run(module.run_benchmark())
            else:
                console.print("[bold red]Error:[/bold red] run_benchmark() not found", style="red")
                sys.exit(1)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}", style="red")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
