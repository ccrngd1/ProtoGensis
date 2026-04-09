#!/usr/bin/env python3
"""
Analyze variance across multiple runs of the same benchmark.
"""

import json
import sys
import numpy as np
from typing import List, Dict
from collections import defaultdict
from evaluators import evaluate_benchmark


def load_and_evaluate_runs(response_files: List[str], prompts_file: str) -> Dict:
    """
    Load multiple runs and evaluate each.

    Returns:
        Dict with per-prompt results across runs
    """
    # Load prompts
    with open(prompts_file, 'r') as f:
        prompts_data = json.load(f)
    prompts_by_id = {p['id']: p for p in prompts_data['prompts']}

    # Load all runs
    all_runs = []
    for file in response_files:
        with open(file, 'r') as f:
            all_runs.append(json.load(f))

    # Group results by prompt and model
    results_by_prompt = defaultdict(lambda: defaultdict(list))

    for run_idx, run_data in enumerate(all_runs):
        for item in run_data:
            prompt_id = item['prompt']['id']
            prompt = prompts_by_id.get(prompt_id)

            if not prompt:
                continue

            for model_key, response_data in item['responses'].items():
                answer = response_data['answer']
                correct = evaluate_benchmark(prompt, answer)

                results_by_prompt[prompt_id][model_key].append(correct)

    return dict(results_by_prompt)


def analyze_variance(results_by_prompt: Dict, model_key: str) -> Dict:
    """
    Analyze variance for a specific model across runs.
    """
    n_prompts = len(results_by_prompt)
    n_runs = len(next(iter(results_by_prompt.values()))[model_key])

    # Calculate accuracy for each run
    accuracies = []
    for run_idx in range(n_runs):
        correct_count = sum(
            1 for prompt_results in results_by_prompt.values()
            if prompt_results[model_key][run_idx]
        )
        accuracy = correct_count / n_prompts
        accuracies.append(accuracy)

    # Calculate variance metrics
    mean_accuracy = np.mean(accuracies)
    std_accuracy = np.std(accuracies, ddof=1)
    min_accuracy = min(accuracies)
    max_accuracy = max(accuracies)
    range_accuracy = max_accuracy - min_accuracy

    # Find inconsistent prompts
    inconsistent_prompts = []
    for prompt_id, model_results in results_by_prompt.items():
        prompt_outcomes = model_results[model_key]
        if len(set(prompt_outcomes)) > 1:  # Not all same
            inconsistent_prompts.append({
                'prompt_id': prompt_id,
                'outcomes': prompt_outcomes,
                'correct_count': sum(prompt_outcomes)
            })

    inconsistency_rate = len(inconsistent_prompts) / n_prompts

    return {
        'model': model_key,
        'n_prompts': n_prompts,
        'n_runs': n_runs,
        'accuracies': [round(a * 100, 1) for a in accuracies],
        'mean_accuracy': round(mean_accuracy * 100, 1),
        'std_accuracy': round(std_accuracy * 100, 2),
        'min_accuracy': round(min_accuracy * 100, 1),
        'max_accuracy': round(max_accuracy * 100, 1),
        'range_accuracy': round(range_accuracy * 100, 1),
        'inconsistent_prompts': inconsistent_prompts,
        'inconsistency_rate': round(inconsistency_rate * 100, 1)
    }


def interpret_variance(metrics: Dict) -> str:
    """
    Interpret variance metrics and recommend action.
    """
    std = metrics['std_accuracy']
    range_acc = metrics['range_accuracy']
    inconsistency = metrics['inconsistency_rate']

    if std < 2.0 and range_acc < 5.0:
        return "✅ LOW variance - 3 runs sufficient, proceed to full dataset"
    elif std < 5.0 and range_acc < 10.0:
        return "⚠️  MODERATE variance - 3 runs OK but 5 runs would be better"
    elif std < 10.0 and range_acc < 15.0:
        return "❌ HIGH variance - need 5+ runs for reliable estimates"
    else:
        return "❌ VERY HIGH variance - model is inconsistent, need 10+ runs"


def main():
    if len(sys.argv) < 4:
        print("Usage: python analyze_variance.py <prompts.json> <run1.json> <run2.json> [<run3.json> ...]")
        sys.exit(1)

    prompts_file = sys.argv[1]
    response_files = sys.argv[2:]

    print("="*80)
    print("VARIANCE ANALYSIS")
    print("="*80)
    print(f"Analyzing {len(response_files)} runs")
    print()

    # Load and evaluate all runs
    results_by_prompt = load_and_evaluate_runs(response_files, prompts_file)

    # Get model keys
    model_keys = list(next(iter(results_by_prompt.values())).keys())

    for model_key in model_keys:
        metrics = analyze_variance(results_by_prompt, model_key)

        print(f"Model: {model_key}")
        print("-"*80)
        print(f"Accuracies across runs: {metrics['accuracies']}")
        print(f"Mean accuracy: {metrics['mean_accuracy']}%")
        print(f"Standard deviation: {metrics['std_accuracy']}%")
        print(f"Range: {metrics['min_accuracy']}% - {metrics['max_accuracy']}% (span: {metrics['range_accuracy']}%)")
        print(f"Inconsistent prompts: {len(metrics['inconsistent_prompts'])}/{metrics['n_prompts']} ({metrics['inconsistency_rate']}%)")

        if metrics['inconsistent_prompts']:
            print("\nPrompts with inconsistent results:")
            for item in metrics['inconsistent_prompts'][:5]:  # Show first 5
                outcomes_str = "".join(["✓" if x else "✗" for x in item['outcomes']])
                print(f"  {item['prompt_id']}: {outcomes_str} ({item['correct_count']}/{len(item['outcomes'])} correct)")
            if len(metrics['inconsistent_prompts']) > 5:
                print(f"  ... and {len(metrics['inconsistent_prompts']) - 5} more")

        print()
        interpretation = interpret_variance(metrics)
        print(f"Recommendation: {interpretation}")
        print()

    print("="*80)


if __name__ == "__main__":
    main()
