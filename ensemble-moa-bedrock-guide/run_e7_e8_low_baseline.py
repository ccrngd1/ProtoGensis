#!/usr/bin/env python3
"""
E7 & E8: Low-Baseline Ensemble Tests

E7: 3×Haiku proposers → Opus aggregator (baseline ~85/100)
E8: 3×Nova-Lite proposers → Haiku aggregator (baseline ~76/100)

Tests if MoA helps when proposers are weaker than aggregator.

Estimated cost: ~$6 total
"""

import json
import sys
import os
from datetime import datetime
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moa.config import ModelConfig
from moa.judge import judge_response

def load_prompts():
    """Load Custom-54 prompts."""
    with open('benchmark/prompts.json') as f:
        data = json.load(f)
        return data.get('prompts', data)

def run_low_baseline_ensemble(proposer_model, aggregator_model, prompts, experiment_name):
    """
    Run a low-baseline ensemble.

    Args:
        proposer_model: Model key for proposers (e.g., 'haiku', 'nova-lite')
        aggregator_model: Model key for aggregator (e.g., 'opus', 'haiku')
        prompts: List of prompt dicts
        experiment_name: E7 or E8
    """
    print(f"\n{'='*80}")
    print(f"{experiment_name}: {proposer_model.upper()} PROPOSERS → {aggregator_model.upper()} AGGREGATOR")
    print(f"{'='*80}\n")

    proposer_config = ModelConfig.get_config(proposer_model)
    aggregator_config = ModelConfig.get_config(aggregator_model)

    results = []
    total_cost = 0

    for i, prompt_data in enumerate(prompts, 1):
        prompt_id = prompt_data['id']
        category = prompt_data['category']
        prompt_text = prompt_data['prompt']

        print(f"[{i}/{len(prompts)}] {prompt_id}...", end=" ", flush=True)

        # Generate 3 proposer responses
        proposer_responses = []
        for j in range(3):
            response = proposer_config.generate(prompt_text)
            proposer_responses.append({
                'model': proposer_config.name,
                'text': response['text'],
                'cost': response['cost']
            })
            total_cost += response['cost']

        # Aggregate with stronger model
        aggregation_prompt = f"""You are synthesizing responses from multiple AI models to provide the best possible answer.

Original Prompt:
{prompt_text}

Model Responses:
"""
        for j, prop_resp in enumerate(proposer_responses, 1):
            aggregation_prompt += f"\nResponse {j}:\n{prop_resp['text']}\n"

        aggregation_prompt += """
Your task: Synthesize these responses into a single, high-quality answer. Consider:
- Which responses are most accurate?
- Are there contradictions to resolve?
- Can you combine the best parts of each?

Provide your synthesized response below:"""

        agg_response = aggregator_config.generate(aggregation_prompt)
        total_cost += agg_response['cost']

        # Judge the aggregated response
        judge_score = judge_response(prompt_text, agg_response['text'], category, model_key='opus')

        results.append({
            'prompt_id': prompt_id,
            'category': category,
            'proposer_model': proposer_model,
            'aggregator_model': aggregator_model,
            'proposer_responses': [p['text'] for p in proposer_responses],
            'aggregated_response': agg_response['text'],
            'cost': sum(p['cost'] for p in proposer_responses) + agg_response['cost'],
            'judge_score': judge_score
        })

        print(f"Score: {judge_score.get('total', 0)}")

        # Rate limit
        if i % 5 == 0:
            time.sleep(2)

    return results, total_cost

def run_baseline_comparison(model_key, prompts):
    """Run individual baseline for comparison."""
    print(f"\n{'='*80}")
    print(f"{model_key.upper()} BASELINE (Individual)")
    print(f"{'='*80}\n")

    config = ModelConfig.get_config(model_key)
    results = []
    total_cost = 0

    for i, prompt_data in enumerate(prompts, 1):
        prompt_id = prompt_data['id']
        category = prompt_data['category']
        prompt_text = prompt_data['prompt']

        print(f"[{i}/{len(prompts)}] {prompt_id}...", end=" ", flush=True)

        response = config.generate(prompt_text)
        judge_score = judge_response(prompt_text, response['text'], category, model_key='opus')

        results.append({
            'prompt_id': prompt_id,
            'category': category,
            'model': config.name,
            'model_key': model_key,
            'response': response['text'],
            'cost': response['cost'],
            'judge_score': judge_score
        })

        total_cost += response['cost']

        print(f"Score: {judge_score.get('total', 0)}")

        # Rate limit
        if i % 10 == 0:
            time.sleep(2)

    return results, total_cost

def main():
    print("=" * 80)
    print("E7 & E8: LOW-BASELINE ENSEMBLE TESTS")
    print("Testing if MoA helps when proposers are weaker")
    print("=" * 80)
    print()

    # Load prompts
    prompts = load_prompts()
    print(f"Loaded {len(prompts)} prompts")
    print()

    print("E7: 3×Haiku → Opus (54 prompts)")
    print("E8: 3×Nova-Lite → Haiku (54 prompts)")
    print("Plus baselines: Haiku individual, Nova-Lite individual")
    print()
    print(f"Total tests: {len(prompts) * 4} (54 prompts × 4 configs)")
    print(f"Estimated cost: ~$6")
    print(f"Estimated time: 1-2 hours")
    print()

    if '--yes' not in sys.argv:
        confirm = input("Proceed with low-baseline tests? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return
    else:
        print("Auto-confirming (--yes flag provided)")

    print()

    # Run E7: Haiku proposers → Opus aggregator
    e7_results, e7_cost = run_low_baseline_ensemble('haiku', 'opus', prompts, 'E7')
    print(f"\nE7 cost: ${e7_cost:.2f}")

    # Run Haiku baseline
    haiku_baseline, haiku_cost = run_baseline_comparison('haiku', prompts)
    print(f"\nHaiku baseline cost: ${haiku_cost:.2f}")

    # Run E8: Nova-Lite proposers → Haiku aggregator
    e8_results, e8_cost = run_low_baseline_ensemble('nova-lite', 'haiku', prompts, 'E8')
    print(f"\nE8 cost: ${e8_cost:.2f}")

    # Run Nova-Lite baseline
    nova_baseline, nova_cost = run_baseline_comparison('nova-lite', prompts)
    print(f"\nNova-Lite baseline cost: ${nova_cost:.2f}")

    total_cost = e7_cost + haiku_cost + e8_cost + nova_cost

    print()
    print("=" * 80)
    print("LOW-BASELINE TESTS COMPLETE")
    print("=" * 80)
    print(f"Total cost: ${total_cost:.2f}")
    print()

    # Save results
    output_file = f"results/e7_e8_low_baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, 'w') as f:
        json.dump({
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'num_prompts': len(prompts),
                'total_cost': total_cost
            },
            'e7_ensemble': e7_results,
            'haiku_baseline': haiku_baseline,
            'e8_ensemble': e8_results,
            'nova_lite_baseline': nova_baseline
        }, f, indent=2)

    print(f"Results saved to: {output_file}")
    print()

    # Analyze results
    print("=" * 80)
    print("LOW-BASELINE ANALYSIS")
    print("=" * 80)
    print()

    # E7 analysis
    e7_scores = [r['judge_score']['total'] for r in e7_results]
    haiku_scores = [r['judge_score']['total'] for r in haiku_baseline]
    e7_mean = sum(e7_scores) / len(e7_scores)
    haiku_mean = sum(haiku_scores) / len(haiku_scores)

    print("E7: Haiku Proposers → Opus Aggregator")
    print(f"  Ensemble mean: {e7_mean:.1f}")
    print(f"  Baseline mean: {haiku_mean:.1f}")
    print(f"  Difference: {e7_mean - haiku_mean:+.1f}")

    if e7_mean > haiku_mean:
        print("  ✅ Ensemble IMPROVES over weak baseline")
    else:
        print("  ❌ Ensemble does NOT improve")

    print()

    # E8 analysis
    e8_scores = [r['judge_score']['total'] for r in e8_results]
    nova_scores = [r['judge_score']['total'] for r in nova_baseline]
    e8_mean = sum(e8_scores) / len(e8_scores)
    nova_mean = sum(nova_scores) / len(nova_scores)

    print("E8: Nova-Lite Proposers → Haiku Aggregator")
    print(f"  Ensemble mean: {e8_mean:.1f}")
    print(f"  Baseline mean: {nova_mean:.1f}")
    print(f"  Difference: {e8_mean - nova_mean:+.1f}")

    if e8_mean > nova_mean:
        print("  ✅ Ensemble IMPROVES over weak baseline")
    else:
        print("  ❌ Ensemble does NOT improve")

    print()
    print("=" * 80)

if __name__ == '__main__':
    main()
