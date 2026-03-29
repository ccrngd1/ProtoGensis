#!/usr/bin/env python3
"""
Benchmark runner for MoA vs single-model comparison.

Runs benchmarks against:
1. Individual cheap models
2. Cheap model ensembles (MoA)
3. Single strong models (baselines)

Produces cost, latency, and quality comparisons.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from moa import MoA, Layer, ModelConfig, BedrockClient, MockBedrockClient
from moa.models import BEDROCK_MODELS, get_recipe


def load_prompts(prompts_file: str = "benchmark/prompts.json") -> List[Dict]:
    """Load benchmark prompts from JSON file."""
    with open(prompts_file, 'r') as f:
        data = json.load(f)
    return data['prompts']


async def run_single_model(
    model_key: str,
    prompt: str,
    mock_mode: bool = False
) -> Dict:
    """
    Run a single model on a prompt.

    Args:
        model_key: Model identifier
        prompt: Input prompt
        mock_mode: Use mock client

    Returns:
        Dict with response, cost, and latency data
    """
    from moa.models import get_model_pricing
    from moa.cost_tracker import CostTracker
    from moa.latency_tracker import LatencyTracker
    import time

    pricing = get_model_pricing(model_key)
    client = MockBedrockClient() if mock_mode else BedrockClient()

    # Track execution
    start_time = time.time()

    result = await client.invoke_model(
        model_id=pricing.model_id,
        prompt=prompt,
        max_tokens=2048,
        temperature=0.7
    )

    duration_ms = (time.time() - start_time) * 1000

    # Calculate cost
    input_cost = (result['input_tokens'] / 1000) * pricing.input_price_per_1k
    output_cost = (result['output_tokens'] / 1000) * pricing.output_price_per_1k
    total_cost = input_cost + output_cost

    return {
        "model": pricing.name,
        "model_key": model_key,
        "response": result['response'],
        "cost": round(total_cost, 6),
        "input_tokens": result['input_tokens'],
        "output_tokens": result['output_tokens'],
        "latency_ms": round(duration_ms, 2)
    }


async def run_moa_ensemble(
    recipe_name: str,
    prompt: str,
    mock_mode: bool = False
) -> Dict:
    """
    Run MoA ensemble on a prompt.

    Args:
        recipe_name: Name of the recipe to use
        prompt: Input prompt
        mock_mode: Use mock client

    Returns:
        Dict with response, cost, and latency data
    """
    from moa.core import create_moa_from_recipe

    moa = create_moa_from_recipe(recipe_name, mock_mode=mock_mode)
    response = await moa.run(prompt)

    return {
        "recipe": recipe_name,
        "response": response.final_response,
        "cost": response.cost_summary.get('total_cost', 0),
        "latency_ms": response.latency_summary.get('total_duration_ms', 0),
        "cost_summary": response.cost_summary,
        "latency_summary": response.latency_summary,
        "metadata": response.metadata
    }


async def run_benchmark_suite(
    prompts: List[Dict],
    mock_mode: bool = False,
    limit: int | None = None
) -> Dict:
    """
    Run full benchmark suite.

    Args:
        prompts: List of benchmark prompts
        mock_mode: Use mock client
        limit: Limit number of prompts (for testing)

    Returns:
        Dict with all benchmark results
    """
    if limit:
        prompts = prompts[:limit]

    results = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "num_prompts": len(prompts),
            "mock_mode": mock_mode
        },
        "single_models": {},
        "ensembles": {},
        "baselines": {}
    }

    print(f"Running benchmark suite with {len(prompts)} prompts...")
    print(f"Mock mode: {mock_mode}\n")

    # Models to test
    cheap_models = ["nova-lite", "mistral-7b", "llama-3.1-8b"]
    baseline_models = ["haiku", "sonnet"]
    ensemble_recipes = ["ultra-cheap", "code-generation", "reasoning"]

    # Run single cheap models
    print("Testing individual cheap models...")
    for model_key in cheap_models:
        print(f"  - {model_key}")
        results["single_models"][model_key] = []

        for prompt_data in prompts:
            try:
                result = await run_single_model(
                    model_key=model_key,
                    prompt=prompt_data['prompt'],
                    mock_mode=mock_mode
                )
                results["single_models"][model_key].append({
                    "prompt_id": prompt_data['id'],
                    "category": prompt_data['category'],
                    **result
                })
            except Exception as e:
                print(f"    Error on {prompt_data['id']}: {e}")
                results["single_models"][model_key].append({
                    "prompt_id": prompt_data['id'],
                    "error": str(e)
                })

    # Run ensemble recipes
    print("\nTesting MoA ensembles...")
    for recipe in ensemble_recipes:
        print(f"  - {recipe}")
        results["ensembles"][recipe] = []

        for prompt_data in prompts:
            try:
                result = await run_moa_ensemble(
                    recipe_name=recipe,
                    prompt=prompt_data['prompt'],
                    mock_mode=mock_mode
                )
                results["ensembles"][recipe].append({
                    "prompt_id": prompt_data['id'],
                    "category": prompt_data['category'],
                    **result
                })
            except Exception as e:
                print(f"    Error on {prompt_data['id']}: {e}")
                results["ensembles"][recipe].append({
                    "prompt_id": prompt_data['id'],
                    "error": str(e)
                })

    # Run baseline models
    print("\nTesting baseline models...")
    for model_key in baseline_models:
        print(f"  - {model_key}")
        results["baselines"][model_key] = []

        for prompt_data in prompts:
            try:
                result = await run_single_model(
                    model_key=model_key,
                    prompt=prompt_data['prompt'],
                    mock_mode=mock_mode
                )
                results["baselines"][model_key].append({
                    "prompt_id": prompt_data['id'],
                    "category": prompt_data['category'],
                    **result
                })
            except Exception as e:
                print(f"    Error on {prompt_data['id']}: {e}")
                results["baselines"][model_key].append({
                    "prompt_id": prompt_data['id'],
                    "error": str(e)
                })

    return results


def calculate_summary_stats(results: Dict) -> Dict:
    """Calculate summary statistics from benchmark results."""
    summary = {
        "single_models": {},
        "ensembles": {},
        "baselines": {}
    }

    # Helper to calculate stats for a list of results
    def calc_stats(result_list: List[Dict]) -> Dict:
        costs = [r['cost'] for r in result_list if 'cost' in r]
        latencies = [r['latency_ms'] for r in result_list if 'latency_ms' in r]

        return {
            "avg_cost": round(sum(costs) / len(costs), 6) if costs else 0,
            "total_cost": round(sum(costs), 6) if costs else 0,
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
            "num_runs": len(result_list)
        }

    # Calculate for each category
    for category in ['single_models', 'ensembles', 'baselines']:
        for key, result_list in results.get(category, {}).items():
            summary[category][key] = calc_stats(result_list)

    return summary


def main():
    """Main benchmark execution."""
    import argparse

    parser = argparse.ArgumentParser(description="Run MoA benchmarks")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock mode (no real Bedrock API calls)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of prompts (for testing)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results/benchmark_results.json",
        help="Output file path"
    )

    args = parser.parse_args()

    # Load prompts
    prompts = load_prompts()

    # Run benchmarks
    results = asyncio.run(run_benchmark_suite(
        prompts=prompts,
        mock_mode=args.mock,
        limit=args.limit
    ))

    # Calculate summary stats
    summary = calculate_summary_stats(results)
    results['summary'] = summary

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n✓ Results saved to {output_path}")

    # Print summary
    print("\n" + "="*60)
    print("BENCHMARK SUMMARY")
    print("="*60)

    print("\nSingle Models (avg per prompt):")
    for model, stats in summary['single_models'].items():
        print(f"  {model:20s} ${stats['avg_cost']:.6f}  {stats['avg_latency_ms']:.0f}ms")

    print("\nEnsembles (avg per prompt):")
    for recipe, stats in summary['ensembles'].items():
        print(f"  {recipe:20s} ${stats['avg_cost']:.6f}  {stats['avg_latency_ms']:.0f}ms")

    print("\nBaselines (avg per prompt):")
    for model, stats in summary['baselines'].items():
        print(f"  {model:20s} ${stats['avg_cost']:.6f}  {stats['avg_latency_ms']:.0f}ms")

    print("\n" + "="*60)


if __name__ == "__main__":
    main()
