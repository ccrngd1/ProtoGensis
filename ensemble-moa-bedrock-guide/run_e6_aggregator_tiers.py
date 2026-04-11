#!/usr/bin/env python3
"""
E6: Different Aggregator Tiers

Test cheap proposers with Sonnet aggregator (vs Opus) on Custom-54.
Tests if aggregator capability matters.

Configurations:
- Baseline: 3×Nova-Lite proposers → Haiku aggregator (from E8)
- Test: 3×Nova-Lite proposers → Sonnet aggregator (mid-tier)
- Reference: 3×Nova-Lite proposers → Opus aggregator (high-tier, if E7 ran)

Estimated cost: ~$8
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

def run_aggregator_tier_test(proposer_model, aggregator_model, prompts):
    """
    Run ensemble with specific aggregator tier.

    Args:
        proposer_model: Model key for proposers (e.g., 'nova-lite', 'haiku')
        aggregator_model: Model key for aggregator (e.g., 'sonnet', 'opus')
        prompts: List of prompt dicts
    """
    print(f"\n{'='*80}")
    print(f"PROPOSERS: 3×{proposer_model.upper()} → AGGREGATOR: {aggregator_model.upper()}")
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

        # Aggregate with specified tier
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

def main():
    print("=" * 80)
    print("E6: AGGREGATOR TIERS TEST")
    print("Testing if aggregator capability matters")
    print("=" * 80)
    print()

    # Load prompts
    prompts = load_prompts()
    print(f"Loaded {len(prompts)} prompts")
    print()

    print("Testing configurations:")
    print("  - 3×Nova-Lite → Sonnet aggregator")
    print("  - (Compare to E8: 3×Nova-Lite → Haiku aggregator)")
    print()

    print(f"Total tests: {len(prompts)}")
    print(f"Estimated cost: ~$8")
    print(f"Estimated time: 30-60 minutes")
    print()

    if '--yes' not in sys.argv:
        confirm = input("Proceed with aggregator tiers test? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return
    else:
        print("Auto-confirming (--yes flag provided)")

    print()

    # Run Sonnet aggregator test
    results, total_cost = run_aggregator_tier_test('nova-lite', 'sonnet', prompts)

    print()
    print("=" * 80)
    print("AGGREGATOR TIERS TEST COMPLETE")
    print("=" * 80)
    print(f"Total cost: ${total_cost:.2f}")
    print()

    # Save results
    output_file = f"results/e6_aggregator_tiers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, 'w') as f:
        json.dump({
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'num_prompts': len(prompts),
                'proposer_model': 'nova-lite',
                'aggregator_model': 'sonnet',
                'total_cost': total_cost
            },
            'results': results
        }, f, indent=2)

    print(f"Results saved to: {output_file}")
    print()

    # Analyze results
    print("=" * 80)
    print("AGGREGATOR TIERS ANALYSIS")
    print("=" * 80)
    print()

    scores = [r['judge_score']['total'] for r in results]
    mean_score = sum(scores) / len(scores)

    print(f"3×Nova-Lite → Sonnet: {mean_score:.1f}")
    print()

    print("Comparison to other aggregator tiers:")
    print("  (From E8 results, if available)")
    print("  - 3×Nova-Lite → Haiku: TBD")
    print("  - 3×Nova-Lite → Opus: TBD")
    print("  - 3×Nova-Lite → Sonnet: {:.1f}".format(mean_score))
    print()

    print("Baseline comparison:")
    print("  - Nova-Lite individual: ~81.8 (from Phase 1)")
    print(f"  - Nova-Lite → Sonnet ensemble: {mean_score:.1f}")
    print(f"  - Improvement: {mean_score - 81.8:+.1f}")
    print()

    if mean_score > 85:
        print("✅ Sonnet aggregator provides SIGNIFICANT improvement")
    elif mean_score > 81.8:
        print("⚠️  Sonnet aggregator provides MODERATE improvement")
    else:
        print("❌ Sonnet aggregator does NOT improve over baseline")

    print()
    print("=" * 80)

if __name__ == '__main__':
    main()
