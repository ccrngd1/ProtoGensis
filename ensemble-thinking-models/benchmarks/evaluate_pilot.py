#!/usr/bin/env python3
"""
Quick pilot evaluation for GSM8K benchmark
Compares model accuracy without needing vote/stitch results
"""

import json
import sys
from evaluators import evaluate_benchmark

def evaluate_pilot(responses_file, prompts_file):
    """Evaluate GSM8K pilot results"""

    # Load data
    with open(responses_file, 'r') as f:
        responses_data = json.load(f)

    with open(prompts_file, 'r') as f:
        prompts_data = json.load(f)

    prompts_by_id = {p['id']: p for p in prompts_data['prompts']}

    # Track results per model
    model_results = {}

    print("="*70)
    print("GSM8K PILOT EVALUATION")
    print("="*70)
    print()

    # Evaluate each prompt
    for item in responses_data:
        prompt_id = item['prompt']['id']
        prompt = prompts_by_id.get(prompt_id)

        if not prompt:
            continue

        responses = item['responses']

        for model_key, response in responses.items():
            if model_key not in model_results:
                model_results[model_key] = {
                    'correct': 0,
                    'total': 0,
                    'cost': 0.0,
                    'details': []
                }

            if response.get('error'):
                model_results[model_key]['total'] += 1
                model_results[model_key]['details'].append({
                    'prompt_id': prompt_id,
                    'correct': False,
                    'error': True
                })
                continue

            # Evaluate
            is_correct = evaluate_benchmark(prompt, response['answer'])

            model_results[model_key]['total'] += 1
            model_results[model_key]['cost'] += response.get('cost_usd', 0)

            if is_correct:
                model_results[model_key]['correct'] += 1

            model_results[model_key]['details'].append({
                'prompt_id': prompt_id,
                'correct': is_correct,
                'answer': response['answer'][:100],
                'ground_truth': prompt['ground_truth']
            })

    # Print results
    print("MODEL ACCURACY COMPARISON:")
    print("-"*70)
    for model_key in sorted(model_results.keys()):
        results = model_results[model_key]
        accuracy = (results['correct'] / results['total'] * 100) if results['total'] > 0 else 0
        cost = results['cost']
        cost_per_correct = cost / results['correct'] if results['correct'] > 0 else float('inf')

        print(f"{model_key:25} {results['correct']:2}/{results['total']:2} = {accuracy:5.1f}%  "
              f"Cost: ${cost:.4f}  Cost/Correct: ${cost_per_correct:.4f}")

    print()
    print("="*70)
    print("DETAILED RESULTS:")
    print("="*70)

    for model_key in sorted(model_results.keys()):
        print(f"\n{model_key}:")
        print("-"*70)
        results = model_results[model_key]

        for detail in results['details']:
            status = "✓" if detail.get('correct') else "✗"
            if detail.get('error'):
                print(f"  {status} {detail['prompt_id']:15} ERROR")
            else:
                print(f"  {status} {detail['prompt_id']:15} Expected: {detail['ground_truth']:10}")

    print()
    print("="*70)
    print("SUMMARY:")
    print("="*70)

    # Find best model
    best_model = max(model_results.keys(),
                    key=lambda k: model_results[k]['correct'] / model_results[k]['total'])
    best_accuracy = (model_results[best_model]['correct'] / model_results[best_model]['total'] * 100)

    print(f"Best accuracy: {best_model} ({best_accuracy:.1f}%)")

    # Compare thinking vs fast
    if 'opus-thinking' in model_results and 'opus-fast' in model_results:
        thinking = model_results['opus-thinking']
        fast = model_results['opus-fast']

        thinking_acc = thinking['correct'] / thinking['total'] * 100
        fast_acc = fast['correct'] / fast['total'] * 100

        print()
        print("THINKING vs FAST:")
        print(f"  Opus-thinking: {thinking_acc:.1f}%  (Cost: ${thinking['cost']:.4f})")
        print(f"  Opus-fast:     {fast_acc:.1f}%  (Cost: ${fast['cost']:.4f})")

        if thinking_acc > fast_acc:
            print(f"  ✓ Thinking wins by {thinking_acc - fast_acc:.1f}%")
        elif fast_acc > thinking_acc:
            print(f"  ✓ Fast wins by {fast_acc - thinking_acc:.1f}%")
        else:
            print(f"  = Tied at {thinking_acc:.1f}%")

        cost_diff_pct = ((thinking['cost'] / fast['cost']) - 1) * 100
        print(f"  Thinking costs {cost_diff_pct:.1f}% more")

    print()
    print("="*70)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python evaluate_pilot.py <responses.json> <prompts.json>")
        sys.exit(1)

    evaluate_pilot(sys.argv[1], sys.argv[2])
