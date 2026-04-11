#!/usr/bin/env python3
"""
Recalculate GSM8K accuracies using fixed extraction.

Compares extracted numeric answers against ground truth to determine:
1. Phase 2 self-consistency accuracies (3 runs of 100 prompts each)
2. GSM8K-20 pilot accuracies (opus-fast vs opus-thinking)
"""

import json
from pathlib import Path

def normalize_answer(answer):
    """Normalize answer for comparison (handle numbers with/without commas, etc.)"""
    if answer is None:
        return None
    answer_str = str(answer).strip().replace(',', '').replace('$', '').lower()
    try:
        # Try to parse as number for numeric comparison
        if '.' in answer_str:
            return str(float(answer_str))
        else:
            return str(int(answer_str))
    except (ValueError, TypeError):
        return answer_str

def load_ground_truth():
    """Load ground truth answers from the prompts file."""
    prompts_file = 'prompts/gsm8k_100.json'

    with open(prompts_file) as f:
        data = json.load(f)

    ground_truth = {}
    # Handle both dict with 'prompts' key or direct list
    prompts = data.get('prompts', data) if isinstance(data, dict) else data

    for prompt in prompts:
        prompt_id = prompt['id']
        answer = prompt.get('ground_truth', '')
        ground_truth[prompt_id] = normalize_answer(answer)

    return ground_truth

def calculate_selfcons_accuracy(result_file, ground_truth):
    """Calculate accuracy for a self-consistency run."""
    with open(result_file) as f:
        data = json.load(f)

    results = data.get('results', [])
    correct = 0
    total = len(results)

    details = []
    for result in results:
        prompt_id = result.get('prompt_id', '')
        selected = normalize_answer(result.get('selected_answer', ''))
        expected = ground_truth.get(prompt_id, '')

        is_correct = (selected == expected)
        if is_correct:
            correct += 1

        details.append({
            'prompt_id': prompt_id,
            'selected': selected,
            'expected': expected,
            'correct': is_correct
        })

    accuracy = (correct / total * 100) if total > 0 else 0
    return accuracy, correct, total, details

def calculate_pilot_accuracy(pilot_file, ground_truth):
    """Calculate accuracy for pilot (both opus-fast and opus-thinking)."""
    with open(pilot_file) as f:
        data = json.load(f)

    results_by_model = {}

    for item in data:
        prompt_id = item['prompt']['id']
        expected = normalize_answer(item['prompt'].get('ground_truth', ''))
        responses = item.get('responses', {})

        for model_key, response_data in responses.items():
            if model_key not in results_by_model:
                results_by_model[model_key] = {'correct': 0, 'total': 0, 'details': []}

            extracted = normalize_answer(response_data.get('extracted_answer', ''))
            is_correct = (extracted == expected)

            results_by_model[model_key]['total'] += 1
            if is_correct:
                results_by_model[model_key]['correct'] += 1

            results_by_model[model_key]['details'].append({
                'prompt_id': prompt_id,
                'extracted': extracted,
                'expected': expected,
                'correct': is_correct
            })

    # Calculate accuracies
    accuracies = {}
    for model_key, stats in results_by_model.items():
        accuracy = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
        accuracies[model_key] = {
            'accuracy': accuracy,
            'correct': stats['correct'],
            'total': stats['total'],
            'details': stats['details']
        }

    return accuracies

def main():
    print("=" * 80)
    print("GSM8K ACCURACY RECALCULATION")
    print("=" * 80)

    # Load ground truth
    print("\nLoading ground truth answers...")
    ground_truth = load_ground_truth()
    print(f"  Loaded {len(ground_truth)} ground truth answers")

    # Phase 2 Self-Consistency
    print("\n" + "=" * 80)
    print("PHASE 2: SELF-CONSISTENCY (GSM8K-100)")
    print("=" * 80)

    selfcons_files = [
        'results/phase2/gsm8k_100_selfcons_run1_fixed.json',
        'results/phase2/gsm8k_100_selfcons_run2_fixed.json',
        'results/phase2/gsm8k_100_selfcons_run3_fixed.json',
    ]

    selfcons_accuracies = []

    for i, filepath in enumerate(selfcons_files, 1):
        if not Path(filepath).exists():
            print(f"\n⚠️  File not found: {filepath}")
            continue

        accuracy, correct, total, details = calculate_selfcons_accuracy(filepath, ground_truth)
        selfcons_accuracies.append(accuracy)

        print(f"\nRun {i}: {Path(filepath).name}")
        print(f"  Correct: {correct}/{total}")
        print(f"  Accuracy: {accuracy:.1f}%")

        # Show first 3 incorrect
        incorrect = [d for d in details if not d['correct']]
        if incorrect:
            print(f"  First few incorrect:")
            for detail in incorrect[:3]:
                print(f"    [{detail['prompt_id']}] got {detail['selected']}, expected {detail['expected']}")

    if selfcons_accuracies:
        mean_accuracy = sum(selfcons_accuracies) / len(selfcons_accuracies)
        print(f"\n{'='*80}")
        print(f"SELF-CONSISTENCY MEAN ACCURACY: {mean_accuracy:.1f}%")
        print(f"  Individual runs: {', '.join(f'{a:.1f}%' for a in selfcons_accuracies)}")
        print(f"{'='*80}")

    # GSM8K-20 Pilot
    print("\n" + "=" * 80)
    print("GSM8K-20 PILOT (THINKING MODE COMPARISON)")
    print("=" * 80)

    pilot_file = 'results/benchmarks/gsm8k/pilot_responses_fixed.json'

    if not Path(pilot_file).exists():
        print(f"\n⚠️  File not found: {pilot_file}")
    else:
        pilot_accuracies = calculate_pilot_accuracy(pilot_file, ground_truth)

        for model_key, stats in pilot_accuracies.items():
            print(f"\n{model_key}:")
            print(f"  Correct: {stats['correct']}/{stats['total']}")
            print(f"  Accuracy: {stats['accuracy']:.1f}%")

            # Show incorrect
            incorrect = [d for d in stats['details'] if not d['correct']]
            if incorrect:
                print(f"  Incorrect answers ({len(incorrect)}):")
                for detail in incorrect[:5]:  # Show up to 5
                    print(f"    [{detail['prompt_id']}] got {detail['extracted']}, expected {detail['expected']}")

        print(f"\n{'='*80}")
        print("PILOT COMPARISON:")
        print(f"{'='*80}")
        for model_key, stats in pilot_accuracies.items():
            print(f"  {model_key}: {stats['accuracy']:.1f}%")

    # Summary for BLOG update
    print("\n" + "=" * 80)
    print("SUMMARY FOR BLOG.md UPDATE")
    print("=" * 80)

    if selfcons_accuracies:
        mean_selfcons = sum(selfcons_accuracies) / len(selfcons_accuracies)
        print(f"\nPhase 2 Self-Consistency:")
        print(f"  Mean Accuracy: {mean_selfcons:.1f}%")
        print(f"  Note: This replaces any previous self-consistency claims")

    if Path(pilot_file).exists():
        pilot_accuracies_loaded = calculate_pilot_accuracy(pilot_file, ground_truth)
        print(f"\nGSM8K-20 Pilot:")
        for model_key, stats in pilot_accuracies_loaded.items():
            model_display = "Thinking Mode" if "thinking" in model_key else "Fast Mode"
            print(f"  Opus {model_display}: {stats['accuracy']:.1f}%")

        if 'opus-thinking' in pilot_accuracies_loaded and 'opus-fast' in pilot_accuracies_loaded:
            thinking_acc = pilot_accuracies_loaded['opus-thinking']['accuracy']
            fast_acc = pilot_accuracies_loaded['opus-fast']['accuracy']
            diff = thinking_acc - fast_acc
            print(f"  Difference: {diff:+.1f} percentage points")

            if abs(diff) < 5:
                print(f"  → No significant difference between modes")
            elif thinking_acc > fast_acc:
                print(f"  → Thinking mode performs better")
            else:
                print(f"  → Fast mode performs better")

    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()
