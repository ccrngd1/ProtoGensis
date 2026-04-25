"""Benchmark runner for ToolGate."""

import json
import time
from pathlib import Path
from typing import Dict, List, Tuple

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from toolgate.config import IndexConfig, GatingConfig
from toolgate.index import ToolIndex
from toolgate.gating import GatingEngine
from toolgate.metrics import MetricsCollector, MetricsConfig
from toolgate.schemas import MCPTool, ToolInputSchema

console = Console()


def load_benchmark_data() -> Tuple[List[MCPTool], List[Dict]]:
    """Load tools and queries from JSON files."""
    benchmark_dir = Path(__file__).parent

    # Load tools
    with open(benchmark_dir / "tools.json") as f:
        tools_data = json.load(f)

    tools = []
    for tool_data in tools_data:
        input_schema = None
        if "inputSchema" in tool_data:
            input_schema = ToolInputSchema(**tool_data["inputSchema"])

        tool = MCPTool(
            name=tool_data["name"],
            description=tool_data.get("description"),
            inputSchema=input_schema,
        )
        tools.append(tool)

    # Load queries
    with open(benchmark_dir / "queries.json") as f:
        queries = json.load(f)

    return tools, queries


def calculate_precision_at_k(
    returned_tools: List[str],
    relevant_tools: List[str],
    k: int
) -> float:
    """Calculate precision@k metric."""
    if not returned_tools:
        return 0.0

    top_k = returned_tools[:k]
    relevant_set = set(relevant_tools)
    matches = sum(1 for tool in top_k if tool in relevant_set)

    return matches / len(top_k)


def calculate_token_reduction(
    all_tools: List[MCPTool],
    returned_tools: List[str],
    metrics: MetricsCollector
) -> Tuple[int, int, float]:
    """Calculate token reduction metrics."""
    total_tokens = sum(metrics.count_tool_tokens(tool) for tool in all_tools)

    returned_tokens = sum(
        metrics.count_tool_tokens(tool)
        for tool in all_tools
        if tool.name in returned_tools
    )

    reduction_pct = ((total_tokens - returned_tokens) / total_tokens * 100) if total_tokens > 0 else 0

    return total_tokens, returned_tokens, reduction_pct


async def run_benchmark():
    """Run the benchmark suite."""
    console.print(Panel.fit(
        "[bold cyan]ToolGate Benchmark Suite[/bold cyan]",
        subtitle="50 tools, 20 queries"
    ))

    # Load data
    console.print("\n[yellow]Loading benchmark data...[/yellow]")
    tools, queries = load_benchmark_data()

    console.print(f"✓ Loaded {len(tools)} tools")
    console.print(f"✓ Loaded {len(queries)} test queries\n")

    # Initialize components
    index_config = IndexConfig()
    gating_config = GatingConfig(top_k=10)
    metrics_config = MetricsConfig(enabled=False)  # Don't persist benchmark metrics

    console.print("[yellow]Building tool index...[/yellow]")
    start_time = time.time()

    index = ToolIndex(index_config)
    server_names = ["benchmark"] * len(tools)
    index.build_index(tools, server_names)

    index_time = (time.time() - start_time) * 1000
    console.print(f"✓ Index built in {index_time:.1f}ms\n")

    gating = GatingEngine(gating_config)
    metrics = MetricsCollector(metrics_config)

    # Run queries
    console.print("[yellow]Running queries...[/yellow]")

    precisions = []
    token_savings = []
    latencies = []

    for i, query_data in enumerate(queries, 1):
        query = query_data["query"]
        relevant_tools = query_data["relevant_tools"]

        # Time the search
        start_time = time.time()

        # Search index
        tool_names, scores = index.search(query, k=gating_config.top_k * 2)

        # Apply gating
        all_tool_names = index.get_all_tool_names()
        gating_result = gating.apply_gating(scores, all_tool_names)
        returned_tools = gating_result.tools

        latency_ms = (time.time() - start_time) * 1000
        latencies.append(latency_ms)

        # Calculate metrics
        precision = calculate_precision_at_k(returned_tools, relevant_tools, k=10)
        precisions.append(precision)

        all_tools = index.get_all_tools()
        total_tokens, returned_tokens, reduction_pct = calculate_token_reduction(
            all_tools, returned_tools, metrics
        )
        token_savings.append(reduction_pct)

        console.print(
            f"  [{i:2d}/20] P@10={precision:.2f} | "
            f"Tokens: {returned_tokens:,}/{total_tokens:,} ({reduction_pct:.1f}% saved) | "
            f"{latency_ms:.1f}ms"
        )

    # Calculate aggregate metrics
    avg_precision = sum(precisions) / len(precisions)
    avg_token_reduction = sum(token_savings) / len(token_savings)
    avg_latency = sum(latencies) / len(latencies)

    # Display results
    console.print("\n")
    results_table = Table(title="Benchmark Results", show_header=True)
    results_table.add_column("Metric", style="cyan", width=30)
    results_table.add_column("Value", style="green", width=20)
    results_table.add_column("Status", style="yellow", width=20)

    # Precision@10
    precision_status = "✓ PASS" if avg_precision >= 0.80 else "✗ FAIL"
    results_table.add_row(
        "Precision@10",
        f"{avg_precision:.1%}",
        precision_status
    )

    # Token reduction
    reduction_status = "✓ PASS" if avg_token_reduction >= 60 else "✗ FAIL"
    results_table.add_row(
        "Avg Token Reduction",
        f"{avg_token_reduction:.1f}%",
        reduction_status
    )

    # Latency
    latency_status = "✓ PASS" if avg_latency < 100 else "⚠ SLOW"
    results_table.add_row(
        "Avg Query Latency",
        f"{avg_latency:.1f}ms",
        latency_status
    )

    # Index build time
    results_table.add_row(
        "Index Build Time",
        f"{index_time:.1f}ms",
        "✓ PASS" if index_time < 5000 else "⚠ SLOW"
    )

    console.print(results_table)

    # Pass/fail summary
    all_pass = avg_precision >= 0.80 and avg_token_reduction >= 60

    if all_pass:
        console.print("\n[bold green]✓ All benchmarks PASSED[/bold green]")
    else:
        console.print("\n[bold red]✗ Some benchmarks FAILED[/bold red]")
        if avg_precision < 0.80:
            console.print(f"  • Precision@10 below threshold: {avg_precision:.1%} < 80%")
        if avg_token_reduction < 60:
            console.print(f"  • Token reduction below threshold: {avg_token_reduction:.1f}% < 60%")

    console.print()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_benchmark())
