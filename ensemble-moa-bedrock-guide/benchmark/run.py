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
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from moa import MoA, Layer, ModelConfig, BedrockClient, QualityJudge
from moa.models import BEDROCK_MODELS, get_recipe


def load_prompts(prompts_file: str = "benchmark/prompts.json") -> List[Dict]:
    """Load benchmark prompts from JSON file."""
    with open(prompts_file, 'r') as f:
        data = json.load(f)
    return data['prompts']


async def run_single_model(
    model_key: str,
    prompt: str
) -> Dict:
    """
    Run a single model on a prompt.

    Args:
        model_key: Model identifier
        prompt: Input prompt

    Returns:
        Dict with response, cost, and latency data
    """
    from moa.models import get_model_pricing
    from moa.cost_tracker import CostTracker
    from moa.latency_tracker import LatencyTracker
    import time

    pricing = get_model_pricing(model_key)
    client = BedrockClient()

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
    prompt: str
) -> Dict:
    """
    Run MoA ensemble on a prompt.

    Args:
        recipe_name: Name of the recipe to use
        prompt: Input prompt

    Returns:
        Dict with response, cost, and latency data
    """
    from moa.core import create_moa_from_recipe

    moa = create_moa_from_recipe(recipe_name)
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
    limit: int | None = None,
    enable_judge: bool = True
) -> Dict:
    """
    Run full benchmark suite.

    Args:
        prompts: List of benchmark prompts
        limit: Limit number of prompts (for testing)
        enable_judge: Enable judge model scoring (default: True)

    Returns:
        Dict with all benchmark results
    """
    if limit:
        prompts = prompts[:limit]

    results = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "num_prompts": len(prompts),
            "mode": "live",
            "judge_enabled": enable_judge
        },
        "single_models": {},
        "ensembles": {},
        "baselines": {}
    }

    print(f"Running benchmark suite with {len(prompts)} prompts...")
    print(f"Mode: LIVE (AWS Bedrock)\n")

    # Models to test
    # NOTE: Mistral 7B and Llama 3.1 8B are not available on this Bedrock account
    # Using Nova Lite (which is the substitute) for cheap models
    cheap_models = ["nova-lite"]  # Single cheap model baseline
    baseline_models = ["nova-lite", "haiku", "sonnet", "opus"]  # Premium baselines (nova-premier removed - access denied)
    ensemble_recipes = ["ultra-cheap", "code-generation", "reasoning", "same-model-baseline",
                        "high-end-reasoning", "mixed-capability", "same-model-premium"]  # Added premium ensembles

    # Run single cheap models
    print("Testing individual cheap models...")
    for model_key in cheap_models:
        print(f"  - {model_key}")
        results["single_models"][model_key] = []

        for prompt_data in prompts:
            try:
                result = await run_single_model(
                    model_key=model_key,
                    prompt=prompt_data['prompt']
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
                    prompt=prompt_data['prompt']
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
                    prompt=prompt_data['prompt']
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

    # Score all responses with judge model
    if enable_judge:
        print("\n" + "="*60)
        print("SCORING RESPONSES WITH JUDGE MODEL (Opus)")
        print("="*60)

        judge = QualityJudge(judge_model="opus")

        # Score single models
        for model_key, result_list in results["single_models"].items():
            print(f"\nScoring {model_key}...")
            evaluations = [
                {
                    'prompt': prompts[i]['prompt'],
                    'response': result_list[i].get('response', ''),
                    'expected_answer': prompts[i].get('expected_answer')
                }
                for i in range(len(result_list))
                if 'response' in result_list[i]
            ]

            if evaluations:
                scores = await judge.score_batch(evaluations)

                # Add scores to results
                score_idx = 0
                for i in range(len(result_list)):
                    if 'response' in result_list[i]:
                        score = scores[score_idx]
                        result_list[i]['judge_score'] = {
                            'correctness': score.correctness,
                            'completeness': score.completeness,
                            'clarity': score.clarity,
                            'total': score.total,
                            'justification': score.justification
                        }
                        score_idx += 1

        # Score ensembles
        for recipe, result_list in results["ensembles"].items():
            print(f"\nScoring {recipe} ensemble...")
            evaluations = [
                {
                    'prompt': prompts[i]['prompt'],
                    'response': result_list[i].get('response', ''),
                    'expected_answer': prompts[i].get('expected_answer')
                }
                for i in range(len(result_list))
                if 'response' in result_list[i]
            ]

            if evaluations:
                scores = await judge.score_batch(evaluations)

                score_idx = 0
                for i in range(len(result_list)):
                    if 'response' in result_list[i]:
                        score = scores[score_idx]
                        result_list[i]['judge_score'] = {
                            'correctness': score.correctness,
                            'completeness': score.completeness,
                            'clarity': score.clarity,
                            'total': score.total,
                            'justification': score.justification
                        }
                        score_idx += 1

        # Score baselines
        for model_key, result_list in results["baselines"].items():
            print(f"\nScoring {model_key} baseline...")
            evaluations = [
                {
                    'prompt': prompts[i]['prompt'],
                    'response': result_list[i].get('response', ''),
                    'expected_answer': prompts[i].get('expected_answer')
                }
                for i in range(len(result_list))
                if 'response' in result_list[i]
            ]

            if evaluations:
                scores = await judge.score_batch(evaluations)

                score_idx = 0
                for i in range(len(result_list)):
                    if 'response' in result_list[i]:
                        score = scores[score_idx]
                        result_list[i]['judge_score'] = {
                            'correctness': score.correctness,
                            'completeness': score.completeness,
                            'clarity': score.clarity,
                            'total': score.total,
                            'justification': score.justification
                        }
                        score_idx += 1

        print("\n✓ Judge scoring complete")

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

        stats = {
            "avg_cost": round(sum(costs) / len(costs), 6) if costs else 0,
            "total_cost": round(sum(costs), 6) if costs else 0,
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
            "num_runs": len(result_list)
        }

        # Add quality stats if available
        quality_scores = [
            r['judge_score']['total']
            for r in result_list
            if 'judge_score' in r
        ]

        if quality_scores:
            import numpy as np
            stats["avg_quality"] = round(sum(quality_scores) / len(quality_scores), 2)
            stats["min_quality"] = round(min(quality_scores), 2)
            stats["max_quality"] = round(max(quality_scores), 2)
            stats["quality_std"] = round(np.std(quality_scores), 2)

        return stats

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
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Disable judge model scoring (faster, cheaper)"
    )

    args = parser.parse_args()

    # Load prompts
    prompts = load_prompts()

    # Run benchmarks
    results = asyncio.run(run_benchmark_suite(
        prompts=prompts,
        limit=args.limit,
        enable_judge=not args.no_judge
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

    # Print quality scores if available
    if not args.no_judge:
        print("\n" + "="*60)
        print("QUALITY SCORES (Judge Model: Opus)")
        print("="*60)

        print("\nSingle Models (avg quality /100):")
        for model, stats in summary['single_models'].items():
            if 'avg_quality' in stats:
                print(f"  {model:20s} {stats['avg_quality']:5.1f} ± {stats['quality_std']:.1f}")

        print("\nEnsembles (avg quality /100):")
        for recipe, stats in summary['ensembles'].items():
            if 'avg_quality' in stats:
                print(f"  {recipe:20s} {stats['avg_quality']:5.1f} ± {stats['quality_std']:.1f}")

        print("\nBaselines (avg quality /100):")
        for model, stats in summary['baselines'].items():
            if 'avg_quality' in stats:
                print(f"  {model:20s} {stats['avg_quality']:5.1f} ± {stats['quality_std']:.1f}")

    print("\n" + "="*60)


if __name__ == "__main__":
    main()
