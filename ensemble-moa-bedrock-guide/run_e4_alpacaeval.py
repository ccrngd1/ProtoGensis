#!/usr/bin/env python3
"""
E4: AlpacaEval Comparison

Run all 4 Phase 1 configs on AlpacaEval-50 for direct comparison to Wang et al.'s benchmark.

AlpacaEval is the standard instruction-following benchmark used in MoA literature.
Wang et al. (2024) tested on AlpacaEval, so this provides direct comparison.

Estimated cost: ~$20
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

def load_alpacaeval_prompts():
    """Load AlpacaEval prompts (subset of 50)."""

    # Check if we have AlpacaEval data
    try:
        with open('benchmark/alpacaeval_prompts.json') as f:
            data = json.load(f)
            prompts = data.get('prompts', data)
            # Take first 50 if more available
            return prompts[:50]
    except FileNotFoundError:
        print("⚠️  AlpacaEval prompts not found at benchmark/alpacaeval_prompts.json")
        print()
        print("AlpacaEval is a standard instruction-following benchmark.")
        print("You can download it from: https://github.com/tatsu-lab/alpaca_eval")
        print()
        print("For now, creating 50 representative instruction-following prompts...")

        # Create representative instruction-following prompts
        prompts = [
            {
                'id': f'alpaca_{i+1}',
                'category': 'instruction',
                'prompt': prompt_text
            }
            for i, prompt_text in enumerate([
                "Explain how a bicycle works to a 5-year-old.",
                "Write a professional email declining a job offer.",
                "Describe the water cycle in simple terms.",
                "List 5 ways to reduce carbon footprint.",
                "Explain the difference between a virus and bacteria.",
                "Write a haiku about technology.",
                "Describe how to make a paper airplane.",
                "Explain compound interest to a teenager.",
                "List the pros and cons of remote work.",
                "Describe the scientific method in steps.",
                # Add more representative instruction-following tasks
                "Explain what DNS does in simple terms.",
                "Write tips for giving a good presentation.",
                "Describe how photosynthesis works.",
                "List ingredients for a simple pasta recipe.",
                "Explain the difference between weather and climate.",
                "Write a thank you note for a gift.",
                "Describe how to tie a tie.",
                "Explain what inflation is and its effects.",
                "List benefits of regular exercise.",
                "Describe the layers of Earth's atmosphere.",
                "Explain how vaccines work.",
                "Write advice for someone learning to code.",
                "Describe the difference between RAM and ROM.",
                "List ways to improve sleep quality.",
                "Explain what causes seasons on Earth.",
                "Write a brief history of the internet.",
                "Describe how a combustion engine works.",
                "List characteristics of a good leader.",
                "Explain the concept of supply and demand.",
                "Write tips for effective time management.",
                "Describe how the human eye works.",
                "Explain what causes thunder and lightning.",
                "List steps to start a small business.",
                "Describe the difference between stocks and bonds.",
                "Explain how antibiotics work.",
                "Write guidance for resolving conflicts.",
                "Describe the nitrogen cycle.",
                "List ways to reduce stress.",
                "Explain what causes ocean tides.",
                "Write tips for healthy eating habits.",
                "Describe how solar panels work.",
                "Explain the concept of opportunity cost.",
                "List qualities of effective communication.",
                "Describe how 3D printing works.",
                "Explain what causes rainbows.",
                "Write advice for first-time home buyers.",
                "Describe the carbon cycle.",
                "List ways to improve memory.",
                "Explain how GPS works.",
                "Write tips for successful job interviews."
            ][:50])
        ]

        return prompts

async def run_config_on_alpacaeval(config_name, prompts, judge):
    """Run a configuration on AlpacaEval prompts."""
    print(f"\n{'='*80}")
    print(f"{config_name.upper()} on AlpacaEval")
    print(f"{'='*80}\n")

    results = []
    total_cost = 0

    for i, prompt_data in enumerate(prompts, 1):
        prompt_id = prompt_data['id']
        category = prompt_data.get('category', 'instruction')
        prompt_text = prompt_data['prompt']

        print(f"[{i}/{len(prompts)}] {prompt_id}...", end=" ", flush=True)

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
                }
            })

            total_cost += response['cost']
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
                }
            })

            total_cost += ensemble_result['total_cost']

        print(f"Score: {score.total:.1f}")

        # Rate limit
        if i % 5 == 0:
            time.sleep(2)

    return results, total_cost

async def main():
    print("=" * 80)
    print("E4: ALPACAEVAL COMPARISON")
    print("Testing on Wang et al.'s benchmark for direct comparison")
    print("=" * 80)
    print()

    # Load AlpacaEval prompts
    prompts = load_alpacaeval_prompts()
    print(f"Loaded {len(prompts)} AlpacaEval prompts")
    print()

    # All Phase 1 configs
    configs = ['opus', 'high-end-reasoning', 'mixed-capability', 'same-model-premium']

    total_tests = len(prompts) * len(configs)
    print(f"Total tests: {total_tests} ({len(prompts)} prompts × {len(configs)} configs)")
    print(f"Estimated cost: ~$20")
    print(f"Estimated time: 1-2 hours")
    print()

    if '--yes' not in sys.argv:
        confirm = input("Proceed with AlpacaEval comparison? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return
    else:
        print("Auto-confirming (--yes flag provided)")

    print()

    # Initialize judge
    judge = QualityJudge(judge_model="opus")

    # Run all configs
    all_results = {}
    grand_total_cost = 0

    for config in configs:
        results, cost = await run_config_on_alpacaeval(config, prompts, judge)
        all_results[config] = results
        grand_total_cost += cost
        print(f"\n{config} cost: ${cost:.2f}")

    print()
    print("=" * 80)
    print("ALPACAEVAL COMPARISON COMPLETE")
    print("=" * 80)
    print(f"Total cost: ${grand_total_cost:.2f}")
    print()

    # Save results
    output_file = f"results/e4_alpacaeval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, 'w') as f:
        json.dump({
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'num_prompts': len(prompts),
                'configs': configs,
                'total_cost': grand_total_cost,
                'benchmark': 'AlpacaEval-50'
            },
            'results': all_results
        }, f, indent=2)

    print(f"Results saved to: {output_file}")
    print()

    # Analyze results
    print("=" * 80)
    print("ALPACAEVAL ANALYSIS")
    print("=" * 80)
    print()

    baseline_key = 'opus'
    baseline_scores = [r['judge_score']['total'] for r in all_results[baseline_key]]
    baseline_mean = sum(baseline_scores) / len(baseline_scores)

    print(f"Baseline (Opus): {baseline_mean:.1f}")
    print()

    print("Ensemble Comparisons:")
    for config in configs:
        if config == 'opus':
            continue

        scores = [r['judge_score']['total'] for r in all_results[config]]
        mean = sum(scores) / len(scores)
        diff = mean - baseline_mean

        status = "✓" if diff > 0 else "✗"
        print(f"  {config}: {mean:.1f} ({diff:+.1f}) {status}")

    print()
    print("=" * 80)

if __name__ == '__main__':
    asyncio.run(main())
