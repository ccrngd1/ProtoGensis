#!/usr/bin/env python3
"""
E13: Adversarial-Only Benchmark

Run Phase 1 configs on ONLY the 5 adversarial prompts × 10 repetitions (n=50).
Quantifies adversarial brittleness discovered in M-V4.

Estimated cost: ~$10
"""

import json
import sys
import os
from datetime import datetime
import time
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moa.config import ModelConfig
from moa.ensemble import run_ensemble
from moa.judge import QualityJudge

def load_adversarial_prompts():
    """Load only the adversarial prompts from Custom-54."""
    with open('benchmark/prompts.json') as f:
        data = json.load(f)
        all_prompts = data.get('prompts', data)

    # Filter for adversarial prompts (category or specific IDs)
    adversarial = [p for p in all_prompts if 'adversarial' in p.get('category', '').lower()
                   or 'edge' in p.get('category', '').lower()]

    # If no adversarial category, identify by known IDs
    if len(adversarial) < 5:
        # Based on M-V4 analysis, these are typically the last 5 in each category
        # or specifically marked. For now, let's take edge-cases category
        adversarial = [p for p in all_prompts if p.get('category') == 'edge-cases']

    return adversarial

async def run_config_on_prompts(config_name, prompts, repetition, judge):
    """Run a configuration on prompts."""
    results = []

    for i, prompt_data in enumerate(prompts, 1):
        prompt_id = prompt_data['id']
        category = prompt_data['category']
        prompt_text = prompt_data['prompt']

        print(f"  [{i}/{len(prompts)}] {prompt_id}...", end=" ", flush=True)

        if config_name == 'opus':
            # Baseline
            opus_config = ModelConfig.get_config('opus')
            response = opus_config.generate(prompt_text)

            score = await judge.score_response(
                prompt=prompt_text,
                response=response['text'],
                expected_answer=None
            )

            results.append({
                'prompt_id': prompt_id,
                'category': category,
                'config': 'opus-baseline',
                'response': response['text'],
                'cost': response['cost'],
                'judge_score': {
                    'correctness': score.correctness,
                    'completeness': score.completeness,
                    'clarity': score.clarity,
                    'total': score.total,
                    'justification': score.justification
                },
                'repetition': repetition
            })
        else:
            # Ensemble
            ensemble_result = run_ensemble(
                config_name=config_name,
                prompt=prompt_text,
                category=category
            )

            score = await judge.score_response(
                prompt=prompt_text,
                response=ensemble_result['aggregated_response'],
                expected_answer=None
            )

            results.append({
                'prompt_id': prompt_id,
                'category': category,
                'config': config_name,
                'aggregated_response': ensemble_result['aggregated_response'],
                'cost': ensemble_result['total_cost'],
                'judge_score': {
                    'correctness': score.correctness,
                    'completeness': score.completeness,
                    'clarity': score.clarity,
                    'total': score.total,
                    'justification': score.justification
                },
                'repetition': repetition
            })

        print(f"Score: {score.total:.1f}")

        # Rate limit
        time.sleep(1)

    return results

async def main():
    print("=" * 80)
    print("E13: ADVERSARIAL-ONLY BENCHMARK")
    print("Testing ensemble adversarial brittleness")
    print("=" * 80)
    print()

    # Load adversarial prompts
    adversarial_prompts = load_adversarial_prompts()
    print(f"Loaded {len(adversarial_prompts)} adversarial prompts:")
    for p in adversarial_prompts:
        print(f"  - {p['id']}: {p['prompt'][:60]}...")
    print()

    configs = ['opus', 'high-end-reasoning', 'mixed-capability', 'same-model-premium']
    num_reps = 10
    total_tests = len(adversarial_prompts) * len(configs) * num_reps

    print(f"Total tests: {total_tests} ({len(adversarial_prompts)} prompts × {len(configs)} configs × {num_reps} reps)")
    print(f"Estimated cost: ~$10")
    print(f"Estimated time: 1-2 hours")
    print()

    if '--yes' not in sys.argv:
        confirm = input("Proceed with adversarial-only benchmark? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return
    else:
        print("Auto-confirming (--yes flag provided)")

    print()

    # Initialize judge
    judge = QualityJudge(judge_model="opus")

    # Run all configs × repetitions
    all_results = []
    total_cost = 0

    for rep in range(1, num_reps + 1):
        for config in configs:
            print(f"\n{config.upper()} - Repetition {rep}/{num_reps}")
            print("-" * 80)

            results = await run_config_on_prompts(config, adversarial_prompts, rep, judge)
            all_results.extend(results)

            rep_cost = sum(r['cost'] for r in results)
            total_cost += rep_cost
            print(f"  Rep cost: ${rep_cost:.2f} | Total: ${total_cost:.2f}")

    print()
    print("=" * 80)
    print("ADVERSARIAL-ONLY BENCHMARK COMPLETE")
    print("=" * 80)
    print(f"Total cost: ${total_cost:.2f}")
    print()

    # Save results
    output_file = f"results/e13_adversarial_only_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, 'w') as f:
        json.dump({
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'num_prompts': len(adversarial_prompts),
                'num_repetitions': num_reps,
                'configs': configs,
                'total_cost': total_cost
            },
            'adversarial_prompts': [p['id'] for p in adversarial_prompts],
            'results': all_results
        }, f, indent=2)

    print(f"Results saved to: {output_file}")
    print()

    # Analyze adversarial brittleness
    print("=" * 80)
    print("ADVERSARIAL BRITTLENESS ANALYSIS")
    print("=" * 80)
    print()

    # Calculate mean scores by config
    from collections import defaultdict
    config_scores = defaultdict(list)

    for result in all_results:
        config = result['config']
        score = result['judge_score']['total']
        config_scores[config].append(score)

    print(f"{'Configuration':<25} {'Mean Score':<12} {'Std Dev':<10} {'N':<5}")
    print("-" * 55)

    for config in configs:
        config_key = config if config == 'opus' else config
        if config == 'opus':
            config_key = 'opus-baseline'

        scores = config_scores[config_key]
        if scores:
            mean = sum(scores) / len(scores)
            variance = sum((s - mean) ** 2 for s in scores) / len(scores)
            std_dev = variance ** 0.5

            print(f"{config:<25} {mean:>10.1f}  {std_dev:>8.2f}  {len(scores):>4}")

    print()
    print("=" * 80)

if __name__ == '__main__':
    asyncio.run(main())
