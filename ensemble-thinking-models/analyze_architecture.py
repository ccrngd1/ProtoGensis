#!/usr/bin/env python3
"""
Architecture Analysis: E1 and E2 Results

Tests the "architecture matters" hypothesis:
- E1: Does strong judge (Opus) beat weak judge (Haiku)?
- E2: Does best-of-N architecture beat baseline?

Compares against Phase 2 baselines:
- Opus-fast individual (89.7%)
- Vote with Haiku judge (87.0%)
- Self-consistency (93.3%)
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
    # Look for patterns that indicate a final answer, prioritizing those at the end
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


# Global ground truth map (loaded in main)
GROUND_TRUTH_MAP = {}


def normalize_results(run) -> tuple[List[Dict], float]:
    """
    Normalize different result formats to a common structure.

    Returns:
        (results_list, total_cost)
    """
    results = []
    total_cost = 0.0

    # Format 1: List at top level (harness or ensemble format)
    if isinstance(run, list):
        for item in run:
            # Check if harness format (has 'prompt' and 'responses')
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
            # Check if ensemble format (has 'selected_answer')
            elif 'selected_answer' in item:
                # Ensemble format - add ground truth from map
                prompt_id = item.get('prompt_id', '')
                ground_truth = GROUND_TRUTH_MAP.get(prompt_id, '')

                results.append({
                    'ground_truth': ground_truth,
                    'selected_answer': item['selected_answer']
                })
                # Ensemble doesn't have per-prompt cost in list, need to calculate from judge_cost
                total_cost += item.get('judge_cost_usd', 0.0)
            else:
                # Unknown format, pass through
                results.append(item)

    # Format 2: Runner script format (E1, E2, self-consistency) - dict with 'results' key
    elif isinstance(run, dict) and 'results' in run:
        results = run['results']
        total_cost = run.get('total_cost_usd', 0.0)

        # Add ground truth if missing (some runner formats don't include it)
        for result in results:
            if 'ground_truth' not in result or not result['ground_truth']:
                prompt_id = result.get('prompt_id', '')
                if prompt_id in GROUND_TRUTH_MAP:
                    result['ground_truth'] = GROUND_TRUTH_MAP[prompt_id]

    # Format 3: Ensemble format - list inside dict
    elif isinstance(run, dict) and 'prompts' in run:
        # Shouldn't hit this, but handle just in case
        results = run.get('prompts', [])
        total_cost = run.get('total_cost_usd', 0.0)

    return results, total_cost


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
    print("ARCHITECTURE ANALYSIS: E1 & E2 Results")
    print("="*70 + "\n")

    # Load prompts for ground truth matching
    print("Loading prompts for ground truth...")
    with open('prompts/gsm8k_100.json', 'r') as f:
        prompts_data = json.load(f)
    prompts = prompts_data.get('prompts', [])

    # Create ground truth mapping
    GROUND_TRUTH_MAP = {p['id']: p['ground_truth'] for p in prompts}
    print(f"Loaded {len(GROUND_TRUTH_MAP)} ground truths\n")

    # Baselines from Phase 2
    baselines = {
        'Opus-fast (baseline)': analyze_experiment('opus-fast', 'gsm8k_100_run*.json'),
        'Vote + Haiku judge': analyze_experiment('vote-haiku', 'gsm8k_100_ensemble_run*.json'),
        'Self-consistency': analyze_experiment('self-cons', 'gsm8k_100_selfcons_run*_fixed.json'),
    }

    # New experiments
    experiments = {
        'E1: Vote + Opus judge': analyze_experiment('e1-strong-judge', 'e1_strong_judge_vote_run*.json'),
        'E2: Best-of-N + Opus judge': analyze_experiment('e2-best-of-n', 'e2_best_of_n_opus_run*.json'),
    }

    # Print results table
    print("BASELINES (Phase 2)")
    print("-" * 70)
    print(f"{'Method':<30} {'Accuracy':<15} {'Δ vs Baseline':<15} {'Cost':<10}")
    print("-" * 70)

    baseline_acc = baselines['Opus-fast (baseline)']['accuracy_mean']

    for name, data in baselines.items():
        if 'error' in data:
            print(f"{name:<30} ERROR: {data['error']}")
            continue

        acc = data['accuracy_mean']
        delta = acc - baseline_acc
        cost = data['cost_mean']

        delta_str = f"{delta:+.1f}%" if name != 'Opus-fast (baseline)' else "baseline"

        print(f"{name:<30} {acc:>5.1f}%  ({data['runs']} runs)  {delta_str:<15} ${cost:.2f}")

    print("\n" + "="*70)
    print("NEW EXPERIMENTS")
    print("-" * 70)
    print(f"{'Method':<30} {'Accuracy':<15} {'Δ vs Baseline':<15} {'Cost':<10}")
    print("-" * 70)

    for name, data in experiments.items():
        if 'error' in data:
            print(f"{name:<30} ERROR: {data['error']}")
            continue

        acc = data['accuracy_mean']
        delta = acc - baseline_acc
        cost = data['cost_mean']

        print(f"{name:<30} {acc:>5.1f}%  ({data['runs']} runs)  {delta:+.1f}%        ${cost:.2f}")

    # Analysis
    print("\n" + "="*70)
    print("ANALYSIS")
    print("="*70 + "\n")

    # E1: Strong judge vs weak judge
    e1_acc = experiments['E1: Vote + Opus judge']['accuracy_mean']
    haiku_judge_acc = baselines['Vote + Haiku judge']['accuracy_mean']
    strong_judge_gain = e1_acc - haiku_judge_acc

    print("E1: Strong Judge Hypothesis")
    print(f"  Vote + Haiku judge: {haiku_judge_acc:.1f}%")
    print(f"  Vote + Opus judge:  {e1_acc:.1f}%")
    print(f"  Gain from strong judge: {strong_judge_gain:+.1f}%")

    if strong_judge_gain > 1.0:
        print(f"  ✓ Strong judge IMPROVES performance significantly")
    elif strong_judge_gain > 0:
        print(f"  ~ Strong judge shows slight improvement")
    else:
        print(f"  ✗ Strong judge does NOT improve performance")

    print()

    # E2: Best-of-N vs baseline
    e2_acc = experiments['E2: Best-of-N + Opus judge']['accuracy_mean']
    baseline_acc = baselines['Opus-fast (baseline)']['accuracy_mean']
    best_of_n_gain = e2_acc - baseline_acc

    print("E2: Best-of-N Architecture")
    print(f"  Opus-fast baseline:        {baseline_acc:.1f}%")
    print(f"  Best-of-N (Opus × 5 + judge): {e2_acc:.1f}%")
    print(f"  Gain from best-of-N: {best_of_n_gain:+.1f}%")

    if best_of_n_gain > 1.0:
        print(f"  ✓ Best-of-N IMPROVES performance")
    elif best_of_n_gain > 0:
        print(f"  ~ Best-of-N shows slight improvement")
    else:
        print(f"  ✗ Best-of-N does NOT improve performance")

    print()

    # Self-consistency comparison
    sc_acc = baselines['Self-consistency']['accuracy_mean']
    print("Comparison to Self-Consistency")
    print(f"  Self-consistency:     {sc_acc:.1f}%")
    print(f"  E1 (Vote + Opus):     {e1_acc:.1f}% ({e1_acc - sc_acc:+.1f}%)")
    print(f"  E2 (Best-of-N):       {e2_acc:.1f}% ({e2_acc - sc_acc:+.1f}%)")

    print("\n" + "="*70)
    print("CONCLUSIONS")
    print("="*70 + "\n")

    # Determine if architecture matters
    if strong_judge_gain > 1.0 or best_of_n_gain > 1.0:
        print("✓ ARCHITECTURE MATTERS: Improved ensemble designs show gains")
        print()
        if strong_judge_gain > 1.0:
            print(f"  - Strong judge (Opus) beats weak judge (Haiku): +{strong_judge_gain:.1f}%")
        if best_of_n_gain > 1.0:
            print(f"  - Best-of-N beats baseline: +{best_of_n_gain:.1f}%")
    else:
        print("✗ ARCHITECTURE DOES NOT MATTER: No significant gains from improved designs")
        print()
        print("  This suggests the issue is fundamental to ensemble approaches,")
        print("  not just poor implementation choices.")

    print()

    # Cost analysis
    print("Cost Analysis:")
    e1_cost = experiments['E1: Vote + Opus judge']['cost_mean']
    e2_cost = experiments['E2: Best-of-N + Opus judge']['cost_mean']
    baseline_cost = baselines['Opus-fast (baseline)']['cost_mean']

    print(f"  Opus baseline:       ${baseline_cost:.2f}")
    print(f"  E1 (Vote + Opus):    ${e1_cost:.2f} ({e1_cost/baseline_cost:.1f}× baseline)")
    print(f"  E2 (Best-of-N):      ${e2_cost:.2f} ({e2_cost/baseline_cost:.1f}× baseline)")
    print(f"  Self-consistency:    ${baselines['Self-consistency']['cost_mean']:.2f} ({baselines['Self-consistency']['cost_mean']/baseline_cost:.1f}× baseline)")

    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    main()
