#!/usr/bin/env python3
"""
E2: Phase 1 Repeated Runs

Rerun all 4 Phase 1 configs × 3 runs to add confidence intervals and variance estimates.

Configs:
- Opus baseline
- High-end reasoning
- Mixed capability
- Same-model-premium

Custom-54 prompts × 4 configs × 3 runs = 648 total tests
Estimated cost: ~$135
"""

import json
import sys
import os
import asyncio

# Import existing MOA modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from moa.config import ModelConfig
from moa.ensemble import run_ensemble
from moa.judge import QualityJudge
from datetime import datetime
import time

def load_prompts():
    """Load Custom-54 prompts."""
    with open('benchmark/prompts.json') as f:
        data = json.load(f)
        return data.get('prompts', data)

async def run_opus_baseline(prompts, run_num, judge):
    """Run Opus baseline on all prompts."""
    print(f"\n{'='*80}")
    print(f"RUN {run_num}: OPUS BASELINE")
    print(f"{'='*80}\n")

    results = []

    for i, prompt_data in enumerate(prompts, 1):
        prompt_id = prompt_data['id']
        category = prompt_data['category']
        prompt_text = prompt_data['prompt']

        print(f"[{i}/{len(prompts)}] {prompt_id}...", end=" ", flush=True)

        # Call Opus directly
        opus_config = ModelConfig.get_config('opus')
        response = opus_config.generate(prompt_text)

        # Judge the response
        score = await judge.score_response(
            prompt=prompt_text,
            response=response['text'],
            expected_answer=None
        )

        results.append({
            'prompt_id': prompt_id,
            'category': category,
            'model': 'Claude Opus 4.6',
            'model_key': 'opus',
            'response': response['text'],
            'cost': response['cost'],
            'judge_score': {
                'correctness': score.correctness,
                'completeness': score.completeness,
                'clarity': score.clarity,
                'total': score.total,
                'justification': score.justification
            },
            'run': run_num
        })

        print(f"Score: {score.total:.1f}")

        # Rate limit
        if i % 10 == 0:
            time.sleep(2)

    return results

async def run_ensemble_config(config_name, prompts, run_num, judge):
    """Run a specific ensemble configuration."""
    print(f"\n{'='*80}")
    print(f"RUN {run_num}: {config_name.upper()}")
    print(f"{'='*80}\n")

    results = []

    for i, prompt_data in enumerate(prompts, 1):
        prompt_id = prompt_data['id']
        category = prompt_data['category']
        prompt_text = prompt_data['prompt']

        print(f"[{i}/{len(prompts)}] {prompt_id}...", end=" ", flush=True)

        # Run ensemble
        ensemble_result = run_ensemble(
            config_name=config_name,
            prompt=prompt_text,
            category=category
        )

        # Judge the aggregated response
        score = await judge.score_response(
            prompt=prompt_text,
            response=ensemble_result['aggregated_response'],
            expected_answer=None
        )

        results.append({
            'prompt_id': prompt_id,
            'category': category,
            'config': config_name,
            'proposer_responses': ensemble_result['proposer_responses'],
            'aggregated_response': ensemble_result['aggregated_response'],
            'cost': ensemble_result['total_cost'],
            'judge_score': {
                'correctness': score.correctness,
                'completeness': score.completeness,
                'clarity': score.clarity,
                'total': score.total,
                'justification': score.justification
            },
            'run': run_num
        })

        print(f"Score: {score.total:.1f}")

        # Rate limit
        if i % 5 == 0:
            time.sleep(3)

    return results

async def main():
    print("=" * 80)
    print("E2: PHASE 1 REPEATED RUNS")
    print("Adding confidence intervals and variance estimates")
    print("=" * 80)
    print()

    # Load prompts
    prompts = load_prompts()
    print(f"Loaded {len(prompts)} prompts")
    print()

    configs = ['opus', 'high-end-reasoning', 'mixed-capability', 'same-model-premium']
    num_runs = 3
    total_tests = len(prompts) * len(configs) * num_runs

    print(f"Total tests: {total_tests} ({len(prompts)} prompts × {len(configs)} configs × {num_runs} runs)")
    print(f"Estimated cost: ~$135")
    print(f"Estimated time: 4-6 hours")
    print()

    if '--yes' not in sys.argv:
        confirm = input("Proceed with repeated runs? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return
    else:
        print("Auto-confirming (--yes flag provided)")

    print()

    # Initialize judge
    judge = QualityJudge(judge_model="opus")

    # Run all configs × runs
    all_results = {}
    total_cost = 0

    for run_num in range(1, num_runs + 1):
        for config in configs:
            print(f"\n{'='*80}")
            print(f"CONFIG: {config} | RUN: {run_num}/{num_runs}")
            print(f"{'='*80}")

            if config == 'opus':
                results = await run_opus_baseline(prompts, run_num, judge)
            else:
                results = await run_ensemble_config(config, prompts, run_num, judge)

            # Track results
            key = f"{config}_run{run_num}"
            all_results[key] = results

            # Calculate costs
            run_cost = sum(r['cost'] for r in results)
            total_cost += run_cost
            print(f"\nRun cost: ${run_cost:.2f}")
            print(f"Total cost so far: ${total_cost:.2f}")

    print()
    print("=" * 80)
    print("PHASE 1 REPEATED RUNS COMPLETE")
    print("=" * 80)
    print(f"Total cost: ${total_cost:.2f}")
    print()

    # Save results
    output_file = f"results/e2_repeated_runs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, 'w') as f:
        json.dump({
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'num_prompts': len(prompts),
                'num_runs': num_runs,
                'configs': configs,
                'total_cost': total_cost
            },
            'results': all_results
        }, f, indent=2)

    print(f"Results saved to: {output_file}")
    print()

    # Calculate statistics
    print("=" * 80)
    print("STATISTICAL ANALYSIS")
    print("=" * 80)
    print()

    for config in configs:
        # Gather scores across runs
        scores_by_run = []
        for run_num in range(1, num_runs + 1):
            key = f"{config}_run{run_num}"
            scores = [r['judge_score']['total'] for r in all_results[key]]
            mean_score = sum(scores) / len(scores)
            scores_by_run.append(mean_score)

        # Calculate stats
        mean = sum(scores_by_run) / len(scores_by_run)
        variance = sum((s - mean) ** 2 for s in scores_by_run) / len(scores_by_run)
        std_dev = variance ** 0.5

        # 95% CI (assuming normal distribution)
        import math
        margin = 1.96 * (std_dev / math.sqrt(num_runs))
        ci_lower = mean - margin
        ci_upper = mean + margin

        print(f"{config}:")
        print(f"  Runs: {', '.join(f'{s:.1f}' for s in scores_by_run)}")
        print(f"  Mean: {mean:.1f}")
        print(f"  Std Dev: {std_dev:.2f}")
        print(f"  95% CI: [{ci_lower:.1f}, {ci_upper:.1f}]")
        print()

    print("=" * 80)

if __name__ == '__main__':
    asyncio.run(main())
