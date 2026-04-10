#!/usr/bin/env python3
"""
Evaluate ensemble comparison results.

Compares 4 approaches:
1. opus-fast (baseline individual)
2. opus-thinking (extended thinking individual)
3. vote ensemble (6 models + Haiku judge)
4. self-consistency (opus × 5 samples)
"""

import json
import sys
from typing import Dict, List
from evaluators import evaluate_benchmark


def load_prompts(prompts_file: str) -> Dict:
    """Load prompts with ground truth."""
    with open(prompts_file, 'r') as f:
        data = json.load(f)
    return {p['id']: p for p in data['prompts']}


def evaluate_individual_runs(run_files: List[str], model_key: str, prompts: Dict) -> Dict:
    """Evaluate individual model across multiple runs."""
    all_results = []

    for run_file in run_files:
        with open(run_file, 'r') as f:
            data = json.load(f)

        correct = 0
        total = 0

        for item in data:
            prompt_id = item['prompt']['id']
            prompt = prompts.get(prompt_id)
            if not prompt:
                continue

            if model_key in item['responses']:
                answer = item['responses'][model_key]['answer']
                if evaluate_benchmark(prompt, answer):
                    correct += 1
                total += 1

        accuracy = correct / total if total > 0 else 0
        all_results.append({'correct': correct, 'total': total, 'accuracy': accuracy})

    return {
        'runs': all_results,
        'mean_accuracy': sum(r['accuracy'] for r in all_results) / len(all_results),
        'accuracies': [r['accuracy'] for r in all_results]
    }


def evaluate_vote_runs(run_files: List[str], prompts: Dict) -> Dict:
    """Evaluate vote ensemble across multiple runs."""
    all_results = []

    for run_file in run_files:
        with open(run_file, 'r') as f:
            data = json.load(f)

        correct = 0
        total = 0

        for item in data:
            prompt_id = item.get('prompt_id')
            if not prompt_id:
                continue

            prompt = prompts.get(prompt_id)
            if not prompt:
                continue

            # Vote result has selected_answer at top level
            if 'selected_answer' in item:
                answer = item['selected_answer']
                if evaluate_benchmark(prompt, answer):
                    correct += 1
                total += 1

        accuracy = correct / total if total > 0 else 0
        all_results.append({'correct': correct, 'total': total, 'accuracy': accuracy})

    return {
        'runs': all_results,
        'mean_accuracy': sum(r['accuracy'] for r in all_results) / len(all_results),
        'accuracies': [r['accuracy'] for r in all_results]
    }


def evaluate_selfcons_runs(run_files: List[str], prompts: Dict) -> Dict:
    """Evaluate self-consistency across multiple runs."""
    all_results = []

    for run_file in run_files:
        with open(run_file, 'r') as f:
            data = json.load(f)

        correct = 0
        total = 0

        for result in data['results']:
            prompt_id = result['prompt_id']
            prompt = prompts.get(prompt_id)
            if not prompt:
                continue

            answer = result['selected_answer']
            if evaluate_benchmark(prompt, answer):
                correct += 1
            total += 1

        accuracy = correct / total if total > 0 else 0
        all_results.append({'correct': correct, 'total': total, 'accuracy': accuracy})

    return {
        'runs': all_results,
        'mean_accuracy': sum(r['accuracy'] for r in all_results) / len(all_results),
        'accuracies': [r['accuracy'] for r in all_results]
    }


def main():
    if len(sys.argv) != 2:
        print("Usage: python evaluate_ensemble_comparison.py <prompts.json>")
        sys.exit(1)

    prompts_file = sys.argv[1]
    prompts = load_prompts(prompts_file)

    print("="*80)
    print("ENSEMBLE COMPARISON EVALUATION")
    print("="*80)
    print()

    # Evaluate opus-fast (baseline)
    opus_fast_files = [
        'results/phase2/gsm8k_100_run1.json',
        'results/phase2/gsm8k_100_run2.json',
        'results/phase2/gsm8k_100_run3.json'
    ]
    opus_fast = evaluate_individual_runs(opus_fast_files, 'opus-fast', prompts)

    # Evaluate opus-thinking
    opus_thinking_files = [
        'results/phase2/gsm8k_100_opus_thinking_run1.json',
        'results/phase2/gsm8k_100_opus_thinking_run2.json',
        'results/phase2/gsm8k_100_opus_thinking_run3.json'
    ]
    opus_thinking = evaluate_individual_runs(opus_thinking_files, 'opus-thinking', prompts)

    # Evaluate vote ensemble
    vote_files = [
        'results/phase2/gsm8k_100_ensemble_run1.json',
        'results/phase2/gsm8k_100_ensemble_run2.json',
        'results/phase2/gsm8k_100_ensemble_run3.json'
    ]
    vote_ensemble = evaluate_vote_runs(vote_files, prompts)

    # Evaluate self-consistency
    selfcons_files = [
        'results/phase2/gsm8k_100_selfcons_run1.json',
        'results/phase2/gsm8k_100_selfcons_run2.json',
        'results/phase2/gsm8k_100_selfcons_run3.json'
    ]
    self_consistency = evaluate_selfcons_runs(selfcons_files, prompts)

    # Print results
    print(f"{'Configuration':<25} {'Mean Accuracy':<15} {'Runs'}")
    print("-"*80)

    configs = [
        ('Opus-fast (baseline)', opus_fast),
        ('Opus-thinking', opus_thinking),
        ('Vote ensemble', vote_ensemble),
        ('Self-consistency', self_consistency)
    ]

    for name, results in configs:
        mean_acc = results['mean_accuracy'] * 100
        run_str = ', '.join(f"{a*100:.1f}%" for a in results['accuracies'])
        print(f"{name:<25} {mean_acc:>5.1f}%           [{run_str}]")

    print()
    print("="*80)
    print()

    # Compare to baseline
    print("COMPARISON TO BASELINE (opus-fast):")
    print("-"*80)
    baseline = opus_fast['mean_accuracy']

    for name, results in configs[1:]:  # Skip baseline itself
        mean_acc = results['mean_accuracy']
        diff = mean_acc - baseline
        diff_pct = (diff / baseline) * 100 if baseline > 0 else 0

        if diff > 0:
            symbol = "✓"
            verdict = f"BETTER by {diff*100:.1f}% ({diff_pct:+.1f}%)"
        elif diff < 0:
            symbol = "✗"
            verdict = f"WORSE by {abs(diff)*100:.1f}% ({diff_pct:.1f}%)"
        else:
            symbol = "="
            verdict = "SAME"

        print(f"{symbol} {name:<23} {mean_acc*100:>5.1f}% | {verdict}")

    print()
    print("="*80)

    # Save results
    output = {
        'opus_fast': opus_fast,
        'opus_thinking': opus_thinking,
        'vote_ensemble': vote_ensemble,
        'self_consistency': self_consistency
    }

    with open('results/phase2/ensemble_comparison_results.json', 'w') as f:
        json.dump(output, f, indent=2)

    print("\n✓ Detailed results saved to results/phase2/ensemble_comparison_results.json")


if __name__ == "__main__":
    main()
