#!/usr/bin/env python3
"""
Benchmark script comparing PseudoAct vs ReAct on multiple tasks.
"""

import json
import time
from pseudoact import run_pseudoact, run_react, get_default_tools


# Benchmark tasks
BENCHMARK_TASKS = [
    {
        "name": "Simple Calculation",
        "query": "Calculate (25 + 15) * 2 and divide by 4"
    },
    {
        "name": "Sequential Search",
        "query": "Search for Python, then search for AI, then combine both results"
    },
    {
        "name": "Calculation with Comparison",
        "query": "Calculate 12 * 3. If result is greater than 30, search for 'AI', else calculate sqrt of result"
    },
    {
        "name": "Multi-step with Facts",
        "query": "Get the population of France, then get the capital of Japan, then search for information about weather"
    },
    {
        "name": "Complex Calculation",
        "query": "Calculate sqrt(144), then multiply by 5, then add 10, and finally divide by 2"
    },
    {
        "name": "Conditional Search",
        "query": "Calculate 100 / 5. If the result equals 20, get fact about USA population, otherwise search for world population"
    }
]


def run_benchmark():
    """Run benchmark comparing both approaches."""
    print("\n" + "=" * 80)
    print(" PseudoAct vs ReAct Benchmark")
    print(" Protogenesis W10 - Pseudocode Planning for LLM Agents")
    print("=" * 80 + "\n")

    results = {
        "pseudoact": [],
        "react": []
    }

    tool_registry = get_default_tools()

    for i, task in enumerate(BENCHMARK_TASKS, 1):
        print(f"\n{'─' * 80}")
        print(f"Task {i}/{len(BENCHMARK_TASKS)}: {task['name']}")
        print(f"Query: {task['query']}")
        print(f"{'─' * 80}\n")

        # Run PseudoAct
        print("Running PseudoAct...")
        try:
            start_time = time.time()
            pseudoact_result = run_pseudoact(task['query'], tool_registry, save_plan=False)
            pseudoact_time = time.time() - start_time

            result_entry = {
                "task": task['name'],
                "success": True,
                "result": str(pseudoact_result['result'])[:100],
                "time": pseudoact_time,
                "tokens": {
                    "synthesis_input": pseudoact_result['usage']['synthesis']['input_tokens'],
                    "synthesis_output": pseudoact_result['usage']['synthesis']['output_tokens'],
                    "execution_input": pseudoact_result['usage']['execution']['input_tokens'],
                    "execution_output": pseudoact_result['usage']['execution']['output_tokens'],
                    "total_input": pseudoact_result['usage']['total_input'],
                    "total_output": pseudoact_result['usage']['total_output'],
                    "total": pseudoact_result['usage']['total_input'] + pseudoact_result['usage']['total_output']
                }
            }
            results["pseudoact"].append(result_entry)

            print(f"✓ PseudoAct completed in {pseudoact_time:.2f}s")
            print(f"  Tokens: {result_entry['tokens']['total']} total "
                  f"({result_entry['tokens']['total_input']} in, {result_entry['tokens']['total_output']} out)")

        except Exception as e:
            print(f"✗ PseudoAct failed: {e}")
            results["pseudoact"].append({
                "task": task['name'],
                "success": False,
                "error": str(e)
            })

        # Run ReAct
        print("\nRunning ReAct...")
        try:
            start_time = time.time()
            react_result = run_react(task['query'], tool_registry, max_iterations=10)
            react_time = time.time() - start_time

            result_entry = {
                "task": task['name'],
                "success": True,
                "result": str(react_result['result'])[:100],
                "time": react_time,
                "iterations": react_result.get('iterations', 0),
                "tokens": {
                    "input": react_result['usage']['input_tokens'],
                    "output": react_result['usage']['output_tokens'],
                    "total": react_result['usage']['input_tokens'] + react_result['usage']['output_tokens']
                }
            }
            results["react"].append(result_entry)

            print(f"✓ ReAct completed in {react_time:.2f}s ({result_entry['iterations']} iterations)")
            print(f"  Tokens: {result_entry['tokens']['total']} total "
                  f"({result_entry['tokens']['input']} in, {result_entry['tokens']['output']} out)")

        except Exception as e:
            print(f"✗ ReAct failed: {e}")
            results["react"].append({
                "task": task['name'],
                "success": False,
                "error": str(e)
            })

    # Print summary
    print_summary(results)

    # Save results
    with open("benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\n✓ Results saved to benchmark_results.json")


def print_summary(results):
    """Print benchmark summary."""
    print("\n" + "=" * 80)
    print(" BENCHMARK SUMMARY")
    print("=" * 80 + "\n")

    # Calculate statistics
    pseudoact_stats = calculate_stats(results["pseudoact"])
    react_stats = calculate_stats(results["react"])

    print("PseudoAct Performance:")
    print(f"  Success Rate: {pseudoact_stats['success_rate']:.1f}%")
    print(f"  Avg Time: {pseudoact_stats['avg_time']:.2f}s")
    print(f"  Avg Tokens: {pseudoact_stats['avg_tokens']:.0f} "
          f"({pseudoact_stats['avg_input']:.0f} in, {pseudoact_stats['avg_output']:.0f} out)")
    print(f"  Total Tokens: {pseudoact_stats['total_tokens']}")

    print("\nReAct Performance:")
    print(f"  Success Rate: {react_stats['success_rate']:.1f}%")
    print(f"  Avg Time: {react_stats['avg_time']:.2f}s")
    print(f"  Avg Iterations: {react_stats['avg_iterations']:.1f}")
    print(f"  Avg Tokens: {react_stats['avg_tokens']:.0f} "
          f"({react_stats['avg_input']:.0f} in, {react_stats['avg_output']:.0f} out)")
    print(f"  Total Tokens: {react_stats['total_tokens']}")

    print("\nComparison:")
    if pseudoact_stats['total_tokens'] > 0 and react_stats['total_tokens'] > 0:
        token_ratio = pseudoact_stats['total_tokens'] / react_stats['total_tokens']
        time_ratio = pseudoact_stats['avg_time'] / react_stats['avg_time'] if react_stats['avg_time'] > 0 else 0

        print(f"  Token Usage: PseudoAct uses {token_ratio:.2f}x tokens compared to ReAct")
        print(f"  Time: PseudoAct is {time_ratio:.2f}x compared to ReAct")

        if token_ratio < 1:
            savings = (1 - token_ratio) * 100
            print(f"  → PseudoAct saves {savings:.1f}% tokens")
        else:
            increase = (token_ratio - 1) * 100
            print(f"  → PseudoAct uses {increase:.1f}% more tokens")

    print("\n" + "=" * 80)


def calculate_stats(results):
    """Calculate statistics from results."""
    successful = [r for r in results if r.get("success", False)]
    total = len(results)

    if not successful:
        return {
            "success_rate": 0,
            "avg_time": 0,
            "avg_tokens": 0,
            "avg_input": 0,
            "avg_output": 0,
            "avg_iterations": 0,
            "total_tokens": 0
        }

    success_rate = (len(successful) / total * 100) if total > 0 else 0
    avg_time = sum(r["time"] for r in successful) / len(successful)

    # Handle different token structures
    if "total" in successful[0].get("tokens", {}):
        total_tokens = sum(r["tokens"]["total"] for r in successful)
        avg_tokens = total_tokens / len(successful)
        avg_input = sum(r["tokens"].get("input", r["tokens"].get("total_input", 0)) for r in successful) / len(successful)
        avg_output = sum(r["tokens"].get("output", r["tokens"].get("total_output", 0)) for r in successful) / len(successful)
    else:
        total_tokens = 0
        avg_tokens = 0
        avg_input = 0
        avg_output = 0

    avg_iterations = sum(r.get("iterations", 0) for r in successful) / len(successful)

    return {
        "success_rate": success_rate,
        "avg_time": avg_time,
        "avg_tokens": avg_tokens,
        "avg_input": avg_input,
        "avg_output": avg_output,
        "avg_iterations": avg_iterations,
        "total_tokens": total_tokens
    }


if __name__ == "__main__":
    run_benchmark()
