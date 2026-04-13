#!/usr/bin/env python3
"""
E14: Baseline Stability Check

Rerun Opus baseline on Custom-54 (April 11 vs March 30).
Verify measurement stability over 2 weeks.

Estimated cost: ~$3
"""

import json
import sys
import os
from datetime import datetime
import time
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moa.config import ModelConfig
from moa.judge import QualityJudge

def load_prompts():
    """Load Custom-54 prompts."""
    with open('benchmark/prompts.json') as f:
        data = json.load(f)
        return data.get('prompts', data)

def load_original_baseline():
    """Load the original March 30 baseline from premium_tier.json."""
    with open('results/premium_tier.json') as f:
        data = json.load(f)

    if 'single_models' in data and 'opus' in data['single_models']:
        original = data['single_models']['opus']
        return original
    return None

async def main():
    print("=" * 80)
    print("E14: BASELINE STABILITY CHECK")
    print("Rerunning Opus baseline to verify measurement stability")
    print("=" * 80)
    print()

    # Load prompts
    prompts = load_prompts()
    print(f"Loaded {len(prompts)} prompts")

    # Load original baseline
    original = load_original_baseline()
    if original:
        original_scores = [r['judge_score']['total'] for r in original]
        original_mean = sum(original_scores) / len(original_scores)
        print(f"Original baseline (March 30): {original_mean:.1f}")
    else:
        print("Warning: Could not load original baseline")
        original_mean = None

    print()
    print(f"Estimated cost: ~$3")
    print(f"Estimated time: 10-15 minutes")
    print()

    if '--yes' not in sys.argv:
        confirm = input("Proceed with baseline stability check? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return
    else:
        print("Auto-confirming (--yes flag provided)")

    print()
    print("Running Opus baseline...")
    print("-" * 80)

    # Initialize judge
    judge = QualityJudge(judge_model="opus")

    # Run Opus on all prompts
    opus_config = ModelConfig.get_config('opus')
    results = []
    total_cost = 0

    for i, prompt_data in enumerate(prompts, 1):
        prompt_id = prompt_data['id']
        category = prompt_data['category']
        prompt_text = prompt_data['prompt']

        print(f"[{i}/{len(prompts)}] {prompt_id}...", end=" ", flush=True)

        # Call Opus
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
            'input_tokens': response['input_tokens'],
            'output_tokens': response['output_tokens'],
            'judge_score': {
                'correctness': score.correctness,
                'completeness': score.completeness,
                'clarity': score.clarity,
                'total': score.total,
                'justification': score.justification
            },
            'timestamp': datetime.now().isoformat()
        })

        total_cost += response['cost']

        print(f"Score: {score.total:.1f}")

        # Rate limit
        if i % 10 == 0:
            time.sleep(2)

    print()
    print("=" * 80)
    print("BASELINE STABILITY CHECK COMPLETE")
    print("=" * 80)
    print(f"Total cost: ${total_cost:.2f}")
    print()

    # Save results
    output_file = f"results/e14_baseline_stability_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, 'w') as f:
        json.dump({
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'num_prompts': len(prompts),
                'total_cost': total_cost,
                'original_date': '2026-03-30',
                'retest_date': datetime.now().strftime('%Y-%m-%d')
            },
            'results': results
        }, f, indent=2)

    print(f"Results saved to: {output_file}")
    print()

    # Analyze stability
    print("=" * 80)
    print("STABILITY ANALYSIS")
    print("=" * 80)
    print()

    new_scores = [r['judge_score']['total'] for r in results]
    new_mean = sum(new_scores) / len(new_scores)

    print(f"Original baseline (March 30): {original_mean:.1f}" if original_mean else "Original: N/A")
    print(f"New baseline (April 11):      {new_mean:.1f}")

    if original_mean:
        diff = new_mean - original_mean
        diff_pct = (diff / original_mean) * 100

        print(f"Difference: {diff:+.1f} points ({diff_pct:+.1f}%)")
        print()

        if abs(diff) < 2:
            print("✅ Baseline is STABLE (difference < 2 points)")
        elif abs(diff) < 5:
            print("⚠️  Baseline has SHIFTED slightly (2-5 points)")
        else:
            print("🔴 Baseline has DRIFTED significantly (>5 points)")

    print()
    print("=" * 80)

if __name__ == '__main__':
    asyncio.run(main())
