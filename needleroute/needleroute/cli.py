"""Command-line interface for NeedleRoute."""

import asyncio
import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from needleroute.config import NeedleRouteConfig
from needleroute.proxy import run_proxy
from needleroute.metrics import MetricsCollector


console = Console()


def cmd_serve(args):
    """Run NeedleRoute proxy server."""
    config_path = args.config or "config.yaml"

    try:
        config = NeedleRouteConfig.from_yaml(config_path)
        console.print(f"[green]Starting NeedleRoute proxy from {config_path}[/green]")
        asyncio.run(run_proxy(config))
    except FileNotFoundError:
        console.print(f"[red]Error: Config file not found: {config_path}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def cmd_index(args):
    """Build tool index from config."""
    config_path = args.config or "config.yaml"

    try:
        config = NeedleRouteConfig.from_yaml(config_path)
        console.print("[yellow]Index building is done automatically on startup[/yellow]")
        console.print("Use 'needleroute serve' to start the proxy and build the index")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def cmd_finetune(args):
    """Generate finetuning data and train Needle model."""
    config_path = args.config or "config.yaml"

    try:
        config = NeedleRouteConfig.from_yaml(config_path)
        console.print("[yellow]Finetuning not yet implemented[/yellow]")
        console.print("This would:")
        console.print("  1. Generate training data using Gemini API")
        console.print("  2. Store data in ~/.needleroute/training/")
        console.print("  3. Finetune Needle model")
        console.print("  4. Save finetuned weights to ~/.needleroute/models/")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def cmd_benchmark(args):
    """Run benchmark comparison."""
    config_path = args.config or "config.yaml"

    try:
        from needleroute.benchmark.runner import run_benchmark

        config = NeedleRouteConfig.from_yaml(config_path)
        console.print("[cyan]Running benchmark...[/cyan]")
        asyncio.run(run_benchmark(config))
    except ImportError:
        console.print("[yellow]Benchmark module not found[/yellow]")
        console.print("This would run side-by-side comparisons:")
        console.print("  - NeedleRoute vs Haiku 4.5 vs Sonnet 4.6 vs GPT-4o-mini")
        console.print("  - Metrics: accuracy, latency, cost, escalation rate")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def cmd_status(args):
    """Show NeedleRoute status."""
    config_path = args.config or "config.yaml"

    try:
        config = NeedleRouteConfig.from_yaml(config_path)

        # Check Needle model availability
        from needleroute.needle_model import create_needle_model
        needle = create_needle_model(config.needle.model_path)

        console.print("\n[bold cyan]NeedleRoute Status[/bold cyan]")
        console.print(f"Config: {config_path}")
        console.print(f"Upstream servers: {len(config.upstream_servers)}")

        for server in config.upstream_servers:
            console.print(f"  - {server.name}: {' '.join(server.command)}")

        console.print(f"\nNeedle model: {'[green]Available[/green]' if needle.is_available() else '[red]Unavailable (using escalation)[/red]'}")
        console.print(f"Escalation provider: {config.escalation.provider}")
        console.print(f"Escalation model: {config.escalation.model}")
        console.print(f"Confidence threshold: {config.needle.confidence_threshold}")
        console.print(f"ToolGate top-K: {config.toolgate.top_k}")

        # Show recent metrics if available
        if config.metrics.enabled:
            metrics = MetricsCollector(config.metrics)
            stats = metrics.get_stats(hours=24)

            if "error" not in stats:
                console.print(f"\n[bold]Last 24 Hours[/bold]")
                console.print(f"Total routes: {stats['total_routes']}")
                console.print(f"Escalation rate: {stats['escalation_rate']:.1%}")
                console.print(f"Avg confidence: {stats['avg_confidence']:.3f}")
                console.print(f"Avg latency: {stats['avg_latency_ms']:.1f}ms")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def cmd_metrics(args):
    """Show metrics for last N hours."""
    config_path = args.config or "config.yaml"
    hours = args.last or 24

    # Parse time period (e.g., "24h", "7d")
    if isinstance(hours, str):
        if hours.endswith("h"):
            hours = int(hours[:-1])
        elif hours.endswith("d"):
            hours = int(hours[:-1]) * 24
        else:
            hours = int(hours)

    try:
        config = NeedleRouteConfig.from_yaml(config_path)

        if not config.metrics.enabled:
            console.print("[yellow]Metrics not enabled in config[/yellow]")
            sys.exit(1)

        metrics = MetricsCollector(config.metrics)
        stats = metrics.get_stats(hours=hours)

        if "error" in stats:
            console.print(f"[red]Error: {stats['error']}[/red]")
            sys.exit(1)

        console.print(f"\n[bold cyan]Metrics - Last {hours} hours[/bold cyan]\n")

        # Overview table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")

        table.add_row("Total Routes", str(stats["total_routes"]))
        table.add_row("Escalations", str(stats["escalated_count"]))
        table.add_row("Escalation Rate", f"{stats['escalation_rate']:.1%}")
        table.add_row("Avg Confidence", f"{stats['avg_confidence']:.3f}")
        table.add_row("Avg Latency", f"{stats['avg_latency_ms']:.1f}ms")
        table.add_row("Tokens Saved", f"{stats['total_tokens_saved']:,}")
        table.add_row("Tokens Used (Escalation)", f"{stats['total_tokens_used']:,}")

        console.print(table)

        # Escalation reasons
        if stats["escalation_reasons"]:
            console.print("\n[bold]Escalation Reasons:[/bold]")
            reason_table = Table(show_header=True)
            reason_table.add_column("Reason", style="yellow")
            reason_table.add_column("Count", justify="right")

            for reason, count in stats["escalation_reasons"].items():
                reason_table.add_row(reason or "unknown", str(count))

            console.print(reason_table)

        # Top tools
        if stats["top_tools"]:
            console.print("\n[bold]Top Tools:[/bold]")
            tool_table = Table(show_header=True)
            tool_table.add_column("Tool", style="green")
            tool_table.add_column("Count", justify="right")

            for tool, count in list(stats["top_tools"].items())[:10]:
                tool_table.add_row(tool or "unknown", str(count))

            console.print(tool_table)

        console.print()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="NeedleRoute - MCP routing proxy with Needle model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Run NeedleRoute proxy server")
    serve_parser.add_argument("--config", "-c", help="Config file path (default: config.yaml)")

    # index command
    index_parser = subparsers.add_parser("index", help="Build tool index")
    index_parser.add_argument("--config", "-c", help="Config file path")

    # finetune command
    finetune_parser = subparsers.add_parser("finetune", help="Finetune Needle model")
    finetune_parser.add_argument("--config", "-c", help="Config file path")

    # benchmark command
    benchmark_parser = subparsers.add_parser("benchmark", help="Run benchmark comparison")
    benchmark_parser.add_argument("--config", "-c", help="Config file path")

    # status command
    status_parser = subparsers.add_parser("status", help="Show NeedleRoute status")
    status_parser.add_argument("--config", "-c", help="Config file path")

    # metrics command
    metrics_parser = subparsers.add_parser("metrics", help="Show metrics")
    metrics_parser.add_argument("--config", "-c", help="Config file path")
    metrics_parser.add_argument("--last", default=24, help="Time period (e.g., 24, '24h', '7d')")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Dispatch to command handlers
    commands = {
        "serve": cmd_serve,
        "index": cmd_index,
        "finetune": cmd_finetune,
        "benchmark": cmd_benchmark,
        "status": cmd_status,
        "metrics": cmd_metrics,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
