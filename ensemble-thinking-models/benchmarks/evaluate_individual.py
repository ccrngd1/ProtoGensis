#!/usr/bin/env python3
"""
Evaluate individual model responses (no ensemble).

Simpler than evaluate.py - just evaluates harness.py output.
"""

import json
import sys
from evaluators import evaluate_benchmark


def evaluate_individual_run(responses_file: str, prompts_file: str):
    """
    Evaluate individual model responses.

    Args:
        responses_file: Output from harness.py
        prompts_file: Prompts JSON with ground truth

    Returns:
        Dict with accuracy results
    """
    # Load responses
    with open(responses_file, 'r') as f:
        responses = json.load(f)

    # Load prompts
    with open(prompts_file, 'r') as f:
        prompts_data = json.load(f)

    prompts_by_id = {p['id']: p for p in prompts_data['prompts']}

    # Evaluate each response
    results_by_model = {}

    for item in responses:
        prompt_id = item['prompt']['id']
        prompt = prompts_by_id.get(prompt_id)

        if not prompt:
            continue

        # Evaluate each model's response
        for model_key, response_data in item['responses'].items():
            if model_key not in results_by_model:
                results_by_model[model_key] = {
                    'correct': 0,
                    'total': 0,
                    'cost': 0.0,
                    'details': []
                }

            answer = response_data['answer']
            cost = response_data.get('cost_usd', 0)

            correct = evaluate_benchmark(prompt, answer)

            results_by_model[model_key]['total'] += 1
            results_by_model[model_key]['cost'] += cost

            if correct:
                results_by_model[model_key]['correct'] += 1

            results_by_model[model_key]['details'].append({
                'prompt_id': prompt_id,
                'correct': correct,
                'answer': answer[:100]
            })

    # Calculate accuracies
    for model_key, results in results_by_model.items():
        results['accuracy'] = results['correct'] / results['total'] if results['total'] > 0 else 0

    return results_by_model


def main():
    if len(sys.argv) != 3:
        print("Usage: python evaluate_individual.py <responses.json> <prompts.json>")
        sys.exit(1)

    responses_file = sys.argv[1]
    prompts_file = sys.argv[2]

    results = evaluate_individual_run(responses_file, prompts_file)

    # Print results
    print("="*80)
    print("INDIVIDUAL MODEL EVALUATION")
    print("="*80)

    for model_key, model_results in results.items():
        accuracy = model_results['accuracy'] * 100
        correct = model_results['correct']
        total = model_results['total']
        cost = model_results['cost']

        print(f"\n{model_key}:")
        print(f"  Accuracy: {correct}/{total} = {accuracy:.1f}%")
        print(f"  Cost: ${cost:.4f}")

    print("\n" + "="*80)

    # Return results as JSON if needed
    return results


if __name__ == "__main__":
    results = main()
