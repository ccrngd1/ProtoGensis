#!/usr/bin/env python3
"""
E3: Premium Ensembles on MT-Bench

Test mixed-capability, same-model-premium, and persona-diverse on MT-Bench-80.
Closes the "only tested weakest ensemble on MT-Bench" gap.

Phase 2 currently only has:
- Opus baseline: 82.6
- Ultra-cheap ensemble: 69.6

Now testing premium ensembles on same benchmark.

Estimated cost: ~$25
"""

import json
import sys
import os
from datetime import datetime
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moa.ensemble import run_ensemble
from moa.judge import judge_response

def load_mtbench_prompts():
    """Load MT-Bench prompts."""
    # MT-Bench typically has 80 questions across multiple turns
    # Check if we have the MT-Bench data

    try:
        with open('benchmark/mtbench_prompts.json') as f:
            data = json.load(f)
            return data.get('questions', data)
    except FileNotFoundError:
        print("⚠️  MT-Bench prompts not found at benchmark/mtbench_prompts.json")
        print("Using subset from results/mtbench_results.json instead")

        # Load from previous MT-Bench run
        with open('results/mtbench_results.json') as f:
            data = json.load(f)
            # Extract prompts from previous run
            prompts = []
            if 'results' in data:
                for result in data['results']:
                    prompts.append({
                        'id': result.get('question_id', f"mt_{len(prompts)+1}"),
                        'category': result.get('category', 'unknown'),
                        'prompt': result.get('turns', [''])[0],  # First turn
                        'turn': 1
                    })
            return prompts

def run_ensemble_on_mtbench(config_name, prompts):
    """Run an ensemble configuration on MT-Bench."""
    print(f"\n{'='*80}")
    print(f"{config_name.upper()} on MT-Bench")
    print(f"{'='*80}\n")

    results = []
    total_cost = 0

    for i, prompt_data in enumerate(prompts, 1):
        prompt_id = prompt_data['id']
        category = prompt_data.get('category', 'conversation')
        prompt_text = prompt_data['prompt']

        print(f"[{i}/{len(prompts)}] {prompt_id}...", end=" ", flush=True)

        # Run ensemble
        ensemble_result = run_ensemble(
            config_name=config_name,
            prompt=prompt_text,
            category=category
        )

        # Judge the aggregated response
        judge_score = judge_response(
            prompt_text,
            ensemble_result['aggregated_response'],
            category,
            model_key='opus'
        )

        results.append({
            'question_id': prompt_id,
            'category': category,
            'config': config_name,
            'prompt': prompt_text,
            'aggregated_response': ensemble_result['aggregated_response'],
            'cost': ensemble_result['total_cost'],
            'judge_score': judge_score,
            'turn': prompt_data.get('turn', 1)
        })

        total_cost += ensemble_result['total_cost']

        print(f"Score: {judge_score.get('total', 0)}")

        # Rate limit
        if i % 5 == 0:
            time.sleep(3)

    return results, total_cost

def main():
    print("=" * 80)
    print("E3: PREMIUM ENSEMBLES ON MT-BENCH")
    print("Testing premium ensemble configs on MT-Bench-80")
    print("=" * 80)
    print()

    # Load MT-Bench prompts
    prompts = load_mtbench_prompts()
    print(f"Loaded {len(prompts)} MT-Bench prompts")
    print()

    # Configs to test (Phase 1 premium ensembles)
    configs = ['mixed-capability', 'same-model-premium', 'high-end-reasoning']

    print(f"Testing {len(configs)} configs:")
    for config in configs:
        print(f"  - {config}")
    print()

    total_tests = len(prompts) * len(configs)
    print(f"Total tests: {total_tests} ({len(prompts)} prompts × {len(configs)} configs)")
    print(f"Estimated cost: ~$25")
    print(f"Estimated time: 2-3 hours")
    print()

    if '--yes' not in sys.argv:
        confirm = input("Proceed with MT-Bench premium tests? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return
    else:
        print("Auto-confirming (--yes flag provided)")

    print()

    # Run all configs
    all_results = {}
    grand_total_cost = 0

    for config in configs:
        results, cost = run_ensemble_on_mtbench(config, prompts)
        all_results[config] = results
        grand_total_cost += cost
        print(f"\n{config} cost: ${cost:.2f}")

    print()
    print("=" * 80)
    print("MT-BENCH PREMIUM TESTS COMPLETE")
    print("=" * 80)
    print(f"Total cost: ${grand_total_cost:.2f}")
    print()

    # Save results
    output_file = f"results/e3_mtbench_premium_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, 'w') as f:
        json.dump({
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'num_prompts': len(prompts),
                'configs': configs,
                'total_cost': grand_total_cost
            },
            'results': all_results
        }, f, indent=2)

    print(f"Results saved to: {output_file}")
    print()

    # Analyze results
    print("=" * 80)
    print("MT-BENCH PREMIUM ANALYSIS")
    print("=" * 80)
    print()

    print("Mean Scores by Configuration:")
    print()

    for config in configs:
        scores = [r['judge_score']['total'] for r in all_results[config]]
        mean = sum(scores) / len(scores)
        print(f"  {config}: {mean:.1f}")

    print()

    # Compare to Phase 2 baseline
    print("Comparison to Phase 2 MT-Bench:")
    print("  Opus baseline: 82.6 (from MTBENCH_RESULTS.md)")
    print("  Ultra-cheap ensemble: 69.6")
    print()

    for config in configs:
        scores = [r['judge_score']['total'] for r in all_results[config]]
        mean = sum(scores) / len(scores)
        diff_from_baseline = mean - 82.6

        print(f"  {config}: {mean:.1f} ({diff_from_baseline:+.1f} vs Opus baseline)")

    print()
    print("=" * 80)

if __name__ == '__main__':
    main()
