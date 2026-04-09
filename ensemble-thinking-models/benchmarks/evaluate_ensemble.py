#!/usr/bin/env python3
"""
Full ensemble evaluation for GSM8K benchmark
Compares individual models vs ensemble methods
"""

import json
import sys
from evaluators import evaluate_benchmark

def evaluate_ensemble(responses_file, vote_file, stitch_file, prompts_file):
    """Evaluate GSM8K ensemble results"""

    # Load data
    with open(responses_file, 'r') as f:
        responses_data = json.load(f)

    with open(vote_file, 'r') as f:
        vote_data = json.load(f)

    with open(stitch_file, 'r') as f:
        stitch_data = json.load(f)

    with open(prompts_file, 'r') as f:
        prompts_data = json.load(f)

    prompts_by_id = {p['id']: p for p in prompts_data['prompts']}
    vote_by_id = {v['prompt_id']: v for v in vote_data}
    stitch_by_id = {s['prompt_id']: s for s in stitch_data}

    # Track results
    model_results = {}
    vote_results = {'correct': 0, 'total': 0, 'cost': 0.0}
    stitch_results = {'correct': 0, 'total': 0, 'cost': 0.0}

    print("="*70)
    print("GSM8K ENSEMBLE EVALUATION")
    print("="*70)
    print()

    # Evaluate each prompt
    for item in responses_data:
        prompt_id = item['prompt']['id']
        prompt = prompts_by_id.get(prompt_id)

        if not prompt:
            continue

        responses = item['responses']

        # Evaluate individual models
        for model_key, response in responses.items():
            if model_key not in model_results:
                model_results[model_key] = {
                    'correct': 0,
                    'total': 0,
                    'cost': 0.0
                }

            if response.get('error'):
                model_results[model_key]['total'] += 1
                continue

            is_correct = evaluate_benchmark(prompt, response['answer'])

            model_results[model_key]['total'] += 1
            model_results[model_key]['cost'] += response.get('cost_usd', 0)

            if is_correct:
                model_results[model_key]['correct'] += 1

        # Evaluate vote ensemble
        vote_result = vote_by_id.get(prompt_id)
        if vote_result:
            vote_answer = vote_result.get('selected_answer', '')
            is_correct = evaluate_benchmark(prompt, vote_answer)

            vote_results['total'] += 1
            vote_results['cost'] += vote_result.get('judge_cost_usd', 0)

            if is_correct:
                vote_results['correct'] += 1

        # Evaluate stitch ensemble
        stitch_result = stitch_by_id.get(prompt_id)
        if stitch_result:
            stitch_answer = stitch_result.get('synthesized_answer', '')
            is_correct = evaluate_benchmark(prompt, stitch_answer)

            stitch_results['total'] += 1
            stitch_results['cost'] += stitch_result.get('synthesis_cost_usd', 0)

            if is_correct:
                stitch_results['correct'] += 1

    # Print results
    print("ACCURACY COMPARISON:")
    print("-"*70)
    print(f"{'Approach':30} {'Accuracy':15} {'Cost':12} {'Cost/Correct':15}")
    print("-"*70)

    # Individual models
    for model_key in sorted(model_results.keys()):
        results = model_results[model_key]
        accuracy = (results['correct'] / results['total'] * 100) if results['total'] > 0 else 0
        cost = results['cost']
        cost_per_correct = cost / results['correct'] if results['correct'] > 0 else float('inf')

        print(f"{model_key:30} {results['correct']:2}/{results['total']:2} = {accuracy:5.1f}%  "
              f"${cost:7.4f}   ${cost_per_correct:.4f}")

    # Add vote/stitch ensemble costs to their base costs
    total_model_cost = sum(r['cost'] for r in model_results.values())

    vote_total_cost = total_model_cost + vote_results['cost']
    vote_accuracy = (vote_results['correct'] / vote_results['total'] * 100) if vote_results['total'] > 0 else 0
    vote_cost_per_correct = vote_total_cost / vote_results['correct'] if vote_results['correct'] > 0 else float('inf')

    stitch_total_cost = total_model_cost + stitch_results['cost']
    stitch_accuracy = (stitch_results['correct'] / stitch_results['total'] * 100) if stitch_results['total'] > 0 else 0
    stitch_cost_per_correct = stitch_total_cost / stitch_results['correct'] if stitch_results['correct'] > 0 else float('inf')

    print("-"*70)
    print(f"{'Ensemble: Vote':30} {vote_results['correct']:2}/{vote_results['total']:2} = {vote_accuracy:5.1f}%  "
          f"${vote_total_cost:7.4f}   ${vote_cost_per_correct:.4f}")
    print(f"{'Ensemble: Stitch':30} {stitch_results['correct']:2}/{stitch_results['total']:2} = {stitch_accuracy:5.1f}%  "
          f"${stitch_total_cost:7.4f}   ${stitch_cost_per_correct:.4f}")

    print()
    print("="*70)
    print("ENSEMBLE VALUE ANALYSIS:")
    print("="*70)

    # Find best individual
    best_model = max(model_results.keys(),
                    key=lambda k: (model_results[k]['correct'] / model_results[k]['total'],
                                  -model_results[k]['cost']))
    best_accuracy = (model_results[best_model]['correct'] / model_results[best_model]['total'] * 100)
    best_correct = model_results[best_model]['correct']

    print(f"Best individual: {best_model} ({best_accuracy:.1f}%, {best_correct}/{model_results[best_model]['total']} correct)")
    print()

    # Compare ensembles to best individual
    vote_beats_best = vote_results['correct'] > best_correct
    stitch_beats_best = stitch_results['correct'] > best_correct

    print(f"Vote ensemble:   {vote_results['correct']}/{vote_results['total']} correct ({vote_accuracy:.1f}%)")
    if vote_beats_best:
        print(f"  ✓ Vote BEATS best individual by {vote_results['correct'] - best_correct} correct answers")
    elif vote_results['correct'] == best_correct:
        print(f"  = Vote TIES best individual")
    else:
        print(f"  ✗ Vote does NOT beat best individual ({best_correct - vote_results['correct']} fewer correct)")

    print()
    print(f"Stitch ensemble: {stitch_results['correct']}/{stitch_results['total']} correct ({stitch_accuracy:.1f}%)")
    if stitch_beats_best:
        print(f"  ✓ Stitch BEATS best individual by {stitch_results['correct'] - best_correct} correct answers")
    elif stitch_results['correct'] == best_correct:
        print(f"  = Stitch TIES best individual")
    else:
        print(f"  ✗ Stitch does NOT beat best individual ({best_correct - stitch_results['correct']} fewer correct)")

    print()
    print("="*70)
    print("SUMMARY:")
    print("="*70)

    ensemble_wins = 0
    if vote_beats_best:
        ensemble_wins += 1
    if stitch_beats_best:
        ensemble_wins += 1

    if ensemble_wins == 0:
        print("❌ ENSEMBLES DID NOT BEAT BEST INDIVIDUAL")
        print(f"   Best individual ({best_model}): {best_correct} correct")
        print(f"   Vote ensemble: {vote_results['correct']} correct")
        print(f"   Stitch ensemble: {stitch_results['correct']} correct")
    else:
        print(f"✓ {ensemble_wins}/2 ensemble methods beat best individual")

    print()
    print("Cost comparison:")
    print(f"  Best individual: ${model_results[best_model]['cost']:.4f}")
    print(f"  Vote ensemble:   ${vote_total_cost:.4f} ({vote_total_cost/model_results[best_model]['cost']:.1f}x more)")
    print(f"  Stitch ensemble: ${stitch_total_cost:.4f} ({stitch_total_cost/model_results[best_model]['cost']:.1f}x more)")

    print()
    print("="*70)

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python evaluate_ensemble.py <responses.json> <vote.json> <stitch.json> <prompts.json>")
        sys.exit(1)

    evaluate_ensemble(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
