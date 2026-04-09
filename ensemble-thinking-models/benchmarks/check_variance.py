#!/usr/bin/env python3
"""
Check variance across multiple runs of the same benchmark.

Used to determine if 3 runs is sufficient for statistical testing.
"""

import json
import sys
import numpy as np
from typing import List, Dict
from collections import defaultdict


def load_results(files: List[str]) -> Dict[str, List[bool]]:
    """
    Load results from multiple run files.

    Returns:
        Dict mapping prompt_id -> list of correct/incorrect for each run
    """
    results_by_prompt = defaultdict(list)

    for file in files:
        with open(file, 'r') as f:
            data = json.load(f)

        # Handle different file formats
        if isinstance(data, list):
            # Harness output format
            for item in data:
                prompt_id = item['prompt']['id']
                # Need to evaluate if correct - for now assume we have this
                # This is a placeholder - actual evaluation logic needed
                results_by_prompt[prompt_id].append(None)
        elif 'results' in data:
            # Aggregator output format
            for result in data['results']:
                prompt_id = result['prompt_id']
                correct = result.get('correct', None)
                results_by_prompt[prompt_id].append(correct)

    return dict(results_by_prompt)


def calculate_variance_metrics(results_by_prompt: Dict[str, List[bool]]) -> Dict:
    """
    Calculate variance metrics across runs.

    Returns:
        Dict with variance statistics
    """
    n_prompts = len(results_by_prompt)
    n_runs = len(next(iter(results_by_prompt.values())))

    # Calculate accuracy for each run
    accuracies = []
    for run_idx in range(n_runs):
        correct_count = sum(
            1 for prompt_results in results_by_prompt.values()
            if prompt_results[run_idx] is True
        )
        accuracy = correct_count / n_prompts
        accuracies.append(accuracy)

    # Calculate variance metrics
    mean_accuracy = np.mean(accuracies)
    std_accuracy = np.std(accuracies, ddof=1)
    min_accuracy = min(accuracies)
    max_accuracy = max(accuracies)
    range_accuracy = max_accuracy - min_accuracy

    # Count prompts with inconsistent results
    inconsistent_count = 0
    for prompt_results in results_by_prompt.values():
        if len(set(prompt_results)) > 1:  # Not all same
            inconsistent_count += 1

    inconsistency_rate = inconsistent_count / n_prompts

    return {
        'n_prompts': n_prompts,
        'n_runs': n_runs,
        'accuracies': accuracies,
        'mean_accuracy': mean_accuracy,
        'std_accuracy': std_accuracy,
        'min_accuracy': min_accuracy,
        'max_accuracy': max_accuracy,
        'range_accuracy': range_accuracy,
        'inconsistent_prompts': inconsistent_count,
        'inconsistency_rate': inconsistency_rate
    }


def interpret_variance(metrics: Dict) -> str:
    """
    Interpret variance metrics and recommend action.
    """
    std = metrics['std_accuracy']
    range_acc = metrics['range_accuracy']
    inconsistency = metrics['inconsistency_rate']

    if std < 0.02 and range_acc < 0.05:
        return "LOW variance - 3 runs sufficient, proceed to full dataset"
    elif std < 0.05 and range_acc < 0.10:
        return "MODERATE variance - 3 runs OK but 5 runs would be better"
    elif std < 0.10 and range_acc < 0.15:
        return "HIGH variance - need 5+ runs for reliable estimates"
    else:
        return "VERY HIGH variance - model is inconsistent, need 10+ runs or different approach"


def main():
    if len(sys.argv) < 3:
        print("Usage: python check_variance.py <results_file1.json> <results_file2.json> [<results_file3.json> ...]")
        print("\nExpects 3+ result files from multiple runs of same prompts")
        sys.exit(1)

    files = sys.argv[1:]

    print("="*80)
    print("VARIANCE ANALYSIS")
    print("="*80)
    print(f"Analyzing {len(files)} runs")
    print()

    # For this pilot, we'll run harness and evaluate inline
    # This is a simplified version - we'll enhance after first run

    # Load all files
    all_results = []
    for file in files:
        with open(file, 'r') as f:
            data = json.load(f)
        all_results.append(data)

    print(f"Loaded {len(all_results)} result files")

    # Group by prompt and model
    print("\nNote: Full variance analysis will be implemented after first run")
    print("      to match actual data format from harness.py")

    # For now, just show what we loaded
    for i, results in enumerate(all_results, 1):
        print(f"\nRun {i}: {len(results) if isinstance(results, list) else '?'} entries")


if __name__ == "__main__":
    main()
