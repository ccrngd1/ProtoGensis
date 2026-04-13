#!/usr/bin/env python3
"""
Correctness-Based Judging Analysis: E18-E20 vs E1-E2

Tests the hypothesis: "Is the judge doing the wrong task?"

Compares:
- E1 (agreement-based vote) vs E18 (correctness-based vote)
- E2 (quality-based best-of-N) vs E19 (correctness-based best-of-N)
- E18 (single-stage) vs E20 (two-stage)

Key question: Does asking the judge to evaluate CORRECTNESS instead of AGREEMENT
fix ensemble performance?
"""

import json
import re
from typing import List, Dict, Tuple
from pathlib import Path


def extract_numeric_answer(text: str) -> str:
    """Extract numeric answer from model output (GSM8K format)"""

    # Remove markdown formatting
    text = re.sub(r'\*\*', '', text)
    text = re.sub(r'__', '', text)
    text = text.strip()

    # If the text is just a number, return it
    if re.match(r'^-?\d+(?:,\d{3})*(?:\.\d+)?$', text):
        return text.replace(',', '')

    # First try to extract from #### format (standard GSM8K)
    match = re.search(r'####\s*(-?\d+(?:,\d{3})*(?:\.\d+)?)', text)
    if match:
        return match.group(1).replace(',', '')

    # Try to find final answer patterns (most reliable)
    final_answer_patterns = [
        # "Daily earnings: 9 × $2 = $18" at end
        r'(?:earnings?|profit|total|answer|result|solution)[:\s]+(?:[^\n]*=\s*)?\$?\s*(-?\d+(?:,\d{3})*(?:\.\d+)?)\s*$',
        # "The answer is X"
        r'(?:answer|result|solution|therefore|thus|so)\s+(?:is|:)\s*\$?\s*(-?\d+(?:,\d{3})*(?:\.\d+)?)',
    ]

    for pattern in final_answer_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).replace(',', '')

    # Try calculation patterns (take LAST match = final calculation)
    calc_patterns = [
        # "= $X" patterns
        r'=\s*\$?\s*(-?\d+(?:,\d{3})*(?:\.\d+)?)',
        # "makes/earns $X" patterns
        r'(?:makes?|earns?|gets?|receives?|costs?|pays?|totals?)\s+\$?\s*(-?\d+(?:,\d{3})*(?:\.\d+)?)',
    ]

    for pattern in calc_patterns:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            return matches[-1].group(1).replace(',', '')

    # Last resort: find the very last number in the text
    match = re.search(r'\$?\s*(-?\d+(?:,\d{3})*(?:\.\d+))\s*$', text, re.MULTILINE)
    if match:
        return match.group(1).replace(',', '')

    return ""


# Global ground truth map
GROUND_TRUTH_MAP = {}


def normalize_results(run) -> tuple[List[Dict], float]:
    """Normalize different result formats to a common structure"""
    results = []
    total_cost = 0.0

    # Format 1: List at top level (harness format)
    if isinstance(run, list):
        for item in run:
            if 'prompt' in item and 'responses' in item:
                # Harness format
                prompt_data = item.get('prompt', {})
                ground_truth = prompt_data.get('ground_truth', '')

                # Get first response
                responses = item.get('responses', {})
                if responses:
                    first_response = list(responses.values())[0]
                    answer = first_response.get('answer', '')
                    cost = first_response.get('cost_usd', 0.0)
                    total_cost += cost

                    results.append({
                        'ground_truth': ground_truth,
                        'answer': answer
                    })
            # Ensemble format (E1 original, old vote format)
            elif 'selected_answer' in item:
                prompt_id = item.get('prompt_id', '')
                ground_truth = GROUND_TRUTH_MAP.get(prompt_id, '')

                results.append({
                    'ground_truth': ground_truth,
                    'selected_answer': item['selected_answer']
                })
                total_cost += item.get('judge_cost_usd', 0.0)

    # Format 2: Runner script format (E1, E2, E18, E19, E20, self-consistency)
    elif isinstance(run, dict) and 'results' in run:
        results = run['results']
        total_cost = run.get('total_cost_usd', 0.0)

        # Add ground truth if missing
        for result in results:
            if 'ground_truth' not in result or not result['ground_truth']:
                prompt_id = result.get('prompt_id', '')
                if prompt_id in GROUND_TRUTH_MAP:
                    result['ground_truth'] = GROUND_TRUTH_MAP[prompt_id]

    return results, total_cost


def evaluate_accuracy(results: List[Dict]) -> Tuple[float, int, int]:
    """Calculate accuracy from normalized results"""
    correct = 0
    total = 0

    for result in results:
        ground_truth = str(result.get('ground_truth', '')).strip()

        # Handle different answer keys
        answer = None
        if 'selected_answer' in result:
            answer = result['selected_answer']
        elif 'answer' in result:
            answer = result['answer']
        elif 'vote_result' in result:
            # E1 format: answer is nested in vote_result
            vote_result = result['vote_result']
            if isinstance(vote_result, dict):
                answer = vote_result.get('selected_answer', '')
        elif 'two_stage_result' in result:
            # E20 format: answer in two_stage_result
            two_stage = result['two_stage_result']
            if isinstance(two_stage, dict):
                answer = two_stage.get('selected_answer', '')

        if not answer:
            continue

        # Extract numeric answers
        predicted = extract_numeric_answer(answer).strip()

        if predicted and ground_truth:
            total += 1
            if predicted == ground_truth:
                correct += 1

    accuracy = (correct / total * 100) if total > 0 else 0.0
    return accuracy, correct, total


def load_experiment_runs(pattern: str) -> List:
    """Load all runs matching a pattern"""
    results_dir = Path('results/phase2')
    files = sorted(results_dir.glob(pattern))

    runs = []
    for f in files:
        with open(f, 'r') as file:
            data = json.load(file)
            runs.append(data)

    return runs


def analyze_experiment(name: str, pattern: str) -> Dict:
    """Analyze all runs of an experiment"""
    runs = load_experiment_runs(pattern)

    if not runs:
        return {'name': name, 'error': 'No results found'}

    accuracies = []
    costs = []

    for run in runs:
        results, total_cost = normalize_results(run)
        costs.append(total_cost)

        acc, correct, total = evaluate_accuracy(results)
        accuracies.append(acc)

    return {
        'name': name,
        'runs': len(runs),
        'accuracy_mean': sum(accuracies) / len(accuracies) if accuracies else 0.0,
        'accuracy_runs': accuracies,
        'cost_mean': sum(costs) / len(costs) if costs else 0.0,
        'cost_total': sum(costs)
    }


def main():
    global GROUND_TRUTH_MAP

    print("\n" + "="*70)
    print("CORRECTNESS-BASED JUDGING ANALYSIS")
    print("="*70 + "\n")

    # Load prompts for ground truth matching
    print("Loading prompts for ground truth...")
    with open('prompts/gsm8k_100.json', 'r') as f:
        prompts_data = json.load(f)
    prompts = prompts_data.get('prompts', [])

    # Create ground truth mapping
    GROUND_TRUTH_MAP = {p['id']: p['ground_truth'] for p in prompts}
    print(f"Loaded {len(GROUND_TRUTH_MAP)} ground truths\n")

    # Baselines
    baselines = {
        'Opus-fast (baseline)': analyze_experiment('opus-fast', 'gsm8k_100_run*.json'),
        'Self-consistency': analyze_experiment('self-cons', 'gsm8k_100_selfcons_run*_fixed.json'),
    }

    # Original experiments (agreement-based)
    original = {
        'E1: Vote + Opus (agreement)': analyze_experiment('e1', 'e1_strong_judge_vote_run*.json'),
        'E2: Best-of-N + Opus (quality)': analyze_experiment('e2', 'e2_best_of_n_opus_run*.json'),
    }

    # New experiments (correctness-based)
    correctness = {
        'E18: Vote + Opus (correctness)': analyze_experiment('e18', 'e18_correctness_vote_run*.json'),
        'E19: Best-of-N + Opus (correctness)': analyze_experiment('e19', 'e19_correctness_best_of_n_run*.json'),
        'E20: Two-Stage': analyze_experiment('e20', 'e20_two_stage_run*.json'),
    }

    # Print results
    baseline_acc = baselines['Opus-fast (baseline)']['accuracy_mean']

    print("="*70)
    print("BASELINES")
    print("-" * 70)
    print(f"{'Method':<35} {'Accuracy':<15} {'Δ vs Base':<15} {'Cost':<10}")
    print("-" * 70)

    for name, data in baselines.items():
        if 'error' in data:
            print(f"{name:<35} ERROR: {data['error']}")
            continue

        acc = data['accuracy_mean']
        delta = acc - baseline_acc
        cost = data['cost_mean']

        delta_str = f"{delta:+.1f}%" if name != 'Opus-fast (baseline)' else "baseline"
        print(f"{name:<35} {acc:>5.1f}%  ({data['runs']} runs)  {delta_str:<15} ${cost:.2f}")

    print("\n" + "="*70)
    print("ORIGINAL EXPERIMENTS (Agreement/Quality-Based Judging)")
    print("-" * 70)
    print(f"{'Method':<35} {'Accuracy':<15} {'Δ vs Base':<15} {'Cost':<10}")
    print("-" * 70)

    for name, data in original.items():
        if 'error' in data:
            print(f"{name:<35} ERROR: {data['error']}")
            continue

        acc = data['accuracy_mean']
        delta = acc - baseline_acc
        cost = data['cost_mean']

        print(f"{name:<35} {acc:>5.1f}%  ({data['runs']} runs)  {delta:+.1f}%        ${cost:.2f}")

    print("\n" + "="*70)
    print("NEW EXPERIMENTS (Correctness-Based Judging)")
    print("-" * 70)
    print(f"{'Method':<35} {'Accuracy':<15} {'Δ vs Base':<15} {'Cost':<10}")
    print("-" * 70)

    for name, data in correctness.items():
        if 'error' in data:
            print(f"{name:<35} ERROR: {data['error']}")
            continue

        acc = data['accuracy_mean']
        delta = acc - baseline_acc
        cost = data['cost_mean']

        print(f"{name:<35} {acc:>5.1f}%  ({data['runs']} runs)  {delta:+.1f}%        ${cost:.2f}")

    # Analysis
    print("\n" + "="*70)
    print("HYPOTHESIS TEST: Does Correctness-Based Judging Fix Ensembles?")
    print("="*70 + "\n")

    # Test 1: E1 vs E18
    e1_acc = original['E1: Vote + Opus (agreement)']['accuracy_mean']
    e18_acc = correctness['E18: Vote + Opus (correctness)']['accuracy_mean']
    e1_e18_delta = e18_acc - e1_acc

    print("Test 1: Agreement-Based vs Correctness-Based Vote")
    print(f"  E1 (agreement):    {e1_acc:.1f}%")
    print(f"  E18 (correctness): {e18_acc:.1f}%")
    print(f"  Improvement:       {e1_e18_delta:+.1f}%")

    if e1_e18_delta > 2.0:
        print(f"  ✓ Correctness-based judging SIGNIFICANTLY improves vote ensemble")
    elif e1_e18_delta > 0:
        print(f"  ~ Slight improvement, but not decisive")
    else:
        print(f"  ✗ Correctness-based judging does NOT improve vote ensemble")

    print()

    # Test 2: E2 vs E19
    e2_acc = original['E2: Best-of-N + Opus (quality)']['accuracy_mean']
    e19_acc = correctness['E19: Best-of-N + Opus (correctness)']['accuracy_mean']
    e2_e19_delta = e19_acc - e2_acc

    print("Test 2: Quality-Based vs Correctness-Based Best-of-N")
    print(f"  E2 (quality):      {e2_acc:.1f}%")
    print(f"  E19 (correctness): {e19_acc:.1f}%")
    print(f"  Improvement:       {e2_e19_delta:+.1f}%")

    if e2_e19_delta > 2.0:
        print(f"  ✓ Correctness-based judging SIGNIFICANTLY improves best-of-N")
    elif e2_e19_delta > 0:
        print(f"  ~ Slight improvement, but not decisive")
    else:
        print(f"  ✗ Correctness-based judging does NOT improve best-of-N")

    print()

    # Test 3: E18 vs E20
    e20_acc = correctness['E20: Two-Stage']['accuracy_mean']
    e18_e20_delta = e20_acc - e18_acc

    print("Test 3: Single-Stage vs Two-Stage Judging")
    print(f"  E18 (single-stage): {e18_acc:.1f}%")
    print(f"  E20 (two-stage):    {e20_acc:.1f}%")
    print(f"  Improvement:        {e18_e20_delta:+.1f}%")

    if e18_e20_delta > 1.0:
        print(f"  ✓ Two-stage judging adds value")
    elif e18_e20_delta > 0:
        print(f"  ~ Marginal benefit from two-stage")
    else:
        print(f"  ✗ Two-stage does NOT improve performance")

    print()

    # Overall verdict
    print("="*70)
    print("VERDICT")
    print("="*70 + "\n")

    # Check if any correctness-based method beats baseline
    best_correctness = max(e18_acc, e19_acc, e20_acc)
    beats_baseline = best_correctness > baseline_acc

    # Check if any correctness-based method approaches self-consistency
    sc_acc = baselines['Self-consistency']['accuracy_mean']
    approaches_sc = best_correctness > (sc_acc - 5.0)  # Within 5% of SC

    if beats_baseline and approaches_sc:
        print("✅ HYPOTHESIS CONFIRMED: Correctness-based judging FIXES ensembles!")
        print()
        print(f"  Best correctness method: {best_correctness:.1f}%")
        print(f"  vs Baseline: {best_correctness - baseline_acc:+.1f}%")
        print(f"  vs Self-consistency: {best_correctness - sc_acc:+.1f}%")
        print()
        print("  The judge was indeed doing the wrong task. Asking it to evaluate")
        print("  CORRECTNESS instead of AGREEMENT significantly improves performance.")
    elif beats_baseline:
        print("⚠️  HYPOTHESIS PARTIALLY CONFIRMED: Correctness judging helps, but not enough")
        print()
        print(f"  Best correctness method: {best_correctness:.1f}%")
        print(f"  vs Baseline: {best_correctness - baseline_acc:+.1f}%")
        print(f"  vs Self-consistency: {best_correctness - sc_acc:+.1f}%")
        print()
        print("  Correctness-based judging beats the baseline, but still falls short of")
        print("  self-consistency. The prompt helps, but doesn't fully solve the problem.")
    else:
        print("❌ HYPOTHESIS REJECTED: Correctness-based judging does NOT fix ensembles")
        print()
        print(f"  Best correctness method: {best_correctness:.1f}%")
        print(f"  vs Baseline: {best_correctness - baseline_acc:+.1f}%")
        print(f"  vs Self-consistency: {best_correctness - sc_acc:+.1f}%")
        print()
        print("  Even when explicitly asked to evaluate correctness, judge-based")
        print("  ensembles still underperform. This suggests:")
        print("  - Evaluation is fundamentally harder than generation")
        print("  - Self-consistency wins for architectural reasons (wisdom of crowds)")
        print("  - Judge-based approaches have inherent limitations")

    # Comparison table
    print("\n" + "="*70)
    print("SUMMARY TABLE")
    print("="*70 + "\n")

    print(f"{'Method':<35} {'Accuracy':<12} {'vs Baseline':<15} {'vs SC':<12}")
    print("-" * 70)
    print(f"{'Opus baseline':<35} {baseline_acc:>5.1f}%      {'baseline':<15} {baseline_acc - sc_acc:+.1f}%")
    print(f"{'Self-consistency':<35} {sc_acc:>5.1f}%      {sc_acc - baseline_acc:+.1f}%          {'baseline':<12}")
    print("-" * 70)
    print(f"{'E1 (vote + agreement)':<35} {e1_acc:>5.1f}%      {e1_acc - baseline_acc:+.1f}%          {e1_acc - sc_acc:+.1f}%")
    print(f"{'E18 (vote + correctness)':<35} {e18_acc:>5.1f}%      {e18_acc - baseline_acc:+.1f}%          {e18_acc - sc_acc:+.1f}%")
    print(f"{'  → Improvement from prompt':<35} {e1_e18_delta:>5.1f}%")
    print("-" * 70)
    print(f"{'E2 (best-of-N + quality)':<35} {e2_acc:>5.1f}%      {e2_acc - baseline_acc:+.1f}%          {e2_acc - sc_acc:+.1f}%")
    print(f"{'E19 (best-of-N + correctness)':<35} {e19_acc:>5.1f}%      {e19_acc - baseline_acc:+.1f}%          {e19_acc - sc_acc:+.1f}%")
    print(f"{'  → Improvement from prompt':<35} {e2_e19_delta:>5.1f}%")
    print("-" * 70)
    print(f"{'E20 (two-stage)':<35} {e20_acc:>5.1f}%      {e20_acc - baseline_acc:+.1f}%          {e20_acc - sc_acc:+.1f}%")

    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    main()
