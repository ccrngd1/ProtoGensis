#!/usr/bin/env python3
"""
Evaluate Self-Consistency Results

Compares self-consistency ensemble (same model, N samples, majority vote)
to single-run individual model performance.
"""

import json
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmarks.evaluators import evaluate_benchmark


def evaluate_self_consistency(
    self_consistency_file: str,
    individual_responses_file: str,
    prompts_file: str
):
    """Evaluate self-consistency vs individual performance"""

    # Load data
    with open(self_consistency_file, 'r') as f:
        sc_data = json.load(f)

    with open(individual_responses_file, 'r') as f:
        individual_data = json.load(f)

    with open(prompts_file, 'r') as f:
        prompts_data = json.load(f)

    prompts_by_id = {p['id']: p for p in prompts_data['prompts']}
    model_key = sc_data['model']

    # Build individual results map
    individual_by_id = {}
    for item in individual_data:
        prompt_id = item['prompt']['id']
        if model_key in item['responses']:
            individual_by_id[prompt_id] = item['responses'][model_key]

    # Evaluate both
    sc_results = {'correct': 0, 'total': 0, 'cost': 0.0}
    individual_results = {'correct': 0, 'total': 0, 'cost': 0.0}

    print("="*80)
    print("SELF-CONSISTENCY EVALUATION")
    print("="*80)
    print(f"Model: {model_key}")
    print(f"Samples per prompt: {sc_data['num_samples']}")
    print()

    for sc_result in sc_data['results']:
        prompt_id = sc_result['prompt_id']
        prompt = prompts_by_id.get(prompt_id)

        if not prompt:
            continue

        # Evaluate self-consistency answer
        sc_answer = sc_result['selected_answer']
        sc_correct = evaluate_benchmark(prompt, sc_answer)

        sc_results['total'] += 1
        sc_results['cost'] += sc_result['total_cost_usd']

        if sc_correct:
            sc_results['correct'] += 1

        # Evaluate individual answer (if exists)
        individual_response = individual_by_id.get(prompt_id)
        if individual_response:
            individual_answer = individual_response['answer']
            individual_correct = evaluate_benchmark(prompt, individual_answer)

            individual_results['total'] += 1
            individual_results['cost'] += individual_response.get('cost_usd', 0)

            if individual_correct:
                individual_results['correct'] += 1

            # Print comparison
            status = "✓" if sc_correct else "✗"
            ind_status = "✓" if individual_correct else "✗"

            if sc_correct != individual_correct:
                print(f"{prompt_id}:")
                print(f"  Self-consistency: {status} (agreement: {sc_result['agreement_rate']:.1%})")
                print(f"  Individual:       {ind_status}")
                if sc_correct and not individual_correct:
                    print(f"  → Self-consistency FIXED error")
                elif not sc_correct and individual_correct:
                    print(f"  → Self-consistency BROKE correct answer")
                print()

    # Print results
    print("="*80)
    print("RESULTS COMPARISON")
    print("="*80)

    sc_accuracy = (sc_results['correct'] / sc_results['total'] * 100) if sc_results['total'] > 0 else 0
    ind_accuracy = (individual_results['correct'] / individual_results['total'] * 100) if individual_results['total'] > 0 else 0

    print(f"{'Approach':<30} {'Accuracy':<15} {'Cost':<12} {'Cost/Correct':<15}")
    print("-"*80)

    ind_cost_per_correct = individual_results['cost'] / individual_results['correct'] if individual_results['correct'] > 0 else float('inf')
    sc_cost_per_correct = sc_results['cost'] / sc_results['correct'] if sc_results['correct'] > 0 else float('inf')

    print(f"{'Individual (single run)':<30} {individual_results['correct']:2}/{individual_results['total']:2} = {ind_accuracy:5.1f}%  "
          f"${individual_results['cost']:7.4f}   ${ind_cost_per_correct:.4f}")

    print(f"{'Self-consistency (N=' + str(sc_data['num_samples']) + ')':<30} {sc_results['correct']:2}/{sc_results['total']:2} = {sc_accuracy:5.1f}%  "
          f"${sc_results['cost']:7.4f}   ${sc_cost_per_correct:.4f}")

    print()
    print("="*80)
    print("ANALYSIS")
    print("="*80)

    # Compare
    diff = sc_results['correct'] - individual_results['correct']
    cost_multiplier = sc_results['cost'] / individual_results['cost'] if individual_results['cost'] > 0 else 0

    if diff > 0:
        print(f"✓ Self-consistency BEATS individual by {diff} correct answer(s)")
        print(f"  Cost: {cost_multiplier:.1f}x more (${sc_results['cost']:.4f} vs ${individual_results['cost']:.4f})")
        print(f"  Trade-off: Pay {cost_multiplier:.1f}x more for {diff} additional correct answers")
    elif diff == 0:
        print(f"= Self-consistency TIES individual")
        print(f"  Cost: {cost_multiplier:.1f}x more (${sc_results['cost']:.4f} vs ${individual_results['cost']:.4f})")
        print(f"  Trade-off: {cost_multiplier:.1f}x more expensive for same accuracy")
    else:
        print(f"✗ Self-consistency WORSE than individual by {abs(diff)} correct answer(s)")
        print(f"  Cost: {cost_multiplier:.1f}x more (${sc_results['cost']:.4f} vs ${individual_results['cost']:.4f})")
        print(f"  Result: Worse accuracy AND more expensive")

    print()
    print(f"Average agreement rate: {sum(r['agreement_rate'] for r in sc_data['results']) / len(sc_data['results']):.1%}")
    print(f"  (How often samples agreed with majority)")
    print()
    print("="*80)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python evaluate_self_consistency.py <self_consistency.json> <individual_responses.json> <prompts.json>")
        sys.exit(1)

    evaluate_self_consistency(sys.argv[1], sys.argv[2], sys.argv[3])
