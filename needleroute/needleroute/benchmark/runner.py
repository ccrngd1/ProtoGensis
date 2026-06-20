"""Benchmark runner for NeedleRoute."""

import json
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Any

from needleroute.config import NeedleRouteConfig
from needleroute.schemas import MCPTool
from needleroute.router import NeedleRouter
from needleroute.index import ToolIndex


def load_benchmark_data() -> tuple[List[MCPTool], List[Dict]]:
    """Load benchmark tools and queries."""
    benchmark_dir = Path(__file__).parent

    # Load tools
    with open(benchmark_dir / "tools.json") as f:
        tools_data = json.load(f)

    tools = [MCPTool(**tool) for tool in tools_data]

    # Load queries
    with open(benchmark_dir / "queries.json") as f:
        queries = json.load(f)

    return tools, queries


async def run_benchmark(config: NeedleRouteConfig) -> Dict[str, Any]:
    """
    Run benchmark comparison.

    Args:
        config: NeedleRoute configuration

    Returns:
        Benchmark results dictionary
    """
    print("Loading benchmark data...")
    tools, queries = load_benchmark_data()

    print(f"Benchmark: {len(tools)} tools, {len(queries)} queries")

    # Initialize router
    router = NeedleRouter(config)

    # Build index
    index = ToolIndex(config.toolgate)
    server_names = ["benchmark"] * len(tools)
    index.build_index(tools, server_names)

    # Pre-encode tools
    router.pre_encode_tools(tools)

    # Run benchmark
    results = []
    correct = 0
    total = 0
    escalated = 0
    total_latency = 0.0

    for i, query_data in enumerate(queries):
        query = query_data["query"]
        expected = query_data["expected_tool"]

        # Search index
        tool_names, scores = index.search(query, k=config.toolgate.top_k)

        # Get tools for routing
        available_tools = [t for t in tools if t.name in tool_names]

        # Route with Needle
        start_time = time.time()
        decision = await router.route(query, available_tools, scores)
        latency_ms = (time.time() - start_time) * 1000

        # Check correctness
        is_correct = decision.selected_tool == expected

        if is_correct:
            correct += 1

        if decision.escalated:
            escalated += 1

        total += 1
        total_latency += latency_ms

        results.append({
            "query": query,
            "expected": expected,
            "selected": decision.selected_tool,
            "correct": is_correct,
            "confidence": decision.confidence,
            "escalated": decision.escalated,
            "escalation_reason": decision.escalation_reason,
            "latency_ms": latency_ms,
        })

        if (i + 1) % 10 == 0:
            print(f"Progress: {i + 1}/{len(queries)} queries")

    # Calculate metrics
    accuracy = correct / total if total > 0 else 0.0
    escalation_rate = escalated / total if total > 0 else 0.0
    avg_latency = total_latency / total if total > 0 else 0.0

    summary = {
        "total_queries": total,
        "correct": correct,
        "accuracy": accuracy,
        "escalated": escalated,
        "escalation_rate": escalation_rate,
        "avg_latency_ms": avg_latency,
        "p50_latency_ms": _percentile([r["latency_ms"] for r in results], 50),
        "p95_latency_ms": _percentile([r["latency_ms"] for r in results], 95),
    }

    return {
        "summary": summary,
        "results": results,
    }


def _percentile(values: List[float], p: int) -> float:
    """Calculate percentile of values."""
    if not values:
        return 0.0

    sorted_values = sorted(values)
    index = int(len(sorted_values) * p / 100)
    return sorted_values[min(index, len(sorted_values) - 1)]


if __name__ == "__main__":
    # Example usage
    from needleroute.config import NeedleRouteConfig

    config = NeedleRouteConfig(
        upstream_servers=[],  # Not needed for benchmark
        needle={"confidence_threshold": 0.7},
        escalation={"provider": "mock"},
    )

    results = asyncio.run(run_benchmark(config))

    print(f"\nBenchmark Results:")
    print(f"  Accuracy: {results['summary']['accuracy']:.1%}")
    print(f"  Escalation Rate: {results['summary']['escalation_rate']:.1%}")
    print(f"  Avg Latency: {results['summary']['avg_latency_ms']:.1f}ms")
    print(f"  P95 Latency: {results['summary']['p95_latency_ms']:.1f}ms")
