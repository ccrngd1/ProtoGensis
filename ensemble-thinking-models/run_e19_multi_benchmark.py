#!/usr/bin/env python3
"""
E19: Correctness-Based Best-of-N - Multi-Benchmark

Tests the hypothesis: "Do judge failures generalize beyond math?"

Runs correctness-based best-of-N across 4 benchmarks:
- GSM8K-100: Math problems (objective, numeric)
- MMLU-100: Multiple choice knowledge (objective, categorical)
- HumanEval-50: Code generation (objective, executable)
- GPQA-50: Graduate science (objective, hard)

Configuration:
- Samples: 5 × opus-fast
- Judge: opus-fast (evaluating CORRECTNESS, not quality)
- Runs: 3 per benchmark

Expected cost: ~$96 total (~$8 per run × 3 runs × 4 benchmarks)
Expected time: ~12 hours
"""

import json
import sys
import os
from aggregators.best_of_n_correctness import CorrectnessBasedBestOfN
from ensemble_shared.bedrock_client import BedrockClient, calculate_cost
from benchmarks.evaluators import evaluate_benchmark

SAMPLE_MODEL = 'opus-fast'
SAMPLE_MODEL_ID = 'us.anthropic.claude-opus-4-6-v1'
NUM_SAMPLES = 5

JUDGE_MODEL = 'opus-fast'
JUDGE_MODEL_ID = 'us.anthropic.claude-opus-4-6-v1'

BENCHMARKS = {
    'gsm8k': 'prompts/gsm8k_100.json',
    'mmlu': 'prompts/mmlu_100.json',
    'humaneval': 'prompts/humaneval_50.json',
    'gpqa': 'prompts/gpqa_50.json'
}


def run_single_experiment(benchmark_name: str, prompts_file: str, run_number: int, output_file: str):
    """Run one instance of E19 experiment on a specific benchmark"""

    print(f"\n{'='*70}")
    print(f"E19: Correctness-Based Best-of-N - {benchmark_name.upper()} - Run {run_number}")
    print(f"{'='*70}\n")

    # Load prompts
    with open(prompts_file, 'r') as f:
        data = json.load(f)
    prompts = data.get('prompts', [])

    print(f"Benchmark: {benchmark_name.upper()}")
    print(f"Loaded {len(prompts)} prompts")
    print(f"Samples: {NUM_SAMPLES} × {SAMPLE_MODEL}")
    print(f"Judge: {JUDGE_MODEL} (evaluating CORRECTNESS)")
    print()

    # Initialize aggregator
    aggregator = CorrectnessBasedBestOfN(mock_mode=False)

    results = []
    total_cost = 0.0
    correct_count = 0

    for i, prompt in enumerate(prompts, 1):
        print(f"[{i}/{len(prompts)}] {prompt['id']}")

        # Use aggregator to generate samples and judge
        result = aggregator.aggregate(
            model_id=SAMPLE_MODEL_ID,
            model_key=SAMPLE_MODEL,
            judge_model_id=JUDGE_MODEL_ID,
            judge_key=JUDGE_MODEL,
            prompt_text=prompt['text'],
            num_samples=NUM_SAMPLES,
            temperature=1.0,
            max_tokens=2048,
            extended_thinking=False
        )

        result.prompt_id = prompt['id']
        total_cost += result.total_cost_usd

        # Evaluate correctness using benchmark-specific evaluator
        # For HumanEval, use the full selected answer (complete code), not extracted snippet
        if benchmark_name == 'humaneval':
            answer_to_evaluate = result.selected_answer
        else:
            answer_to_evaluate = result.final_answer_extracted or result.selected_answer

        is_correct = evaluate_benchmark(prompt, answer_to_evaluate)
        if is_correct:
            correct_count += 1

        print(f"    Selected: sample_{result.selected_index} → {result.final_answer_extracted or '(full response)'}")
        print(f"    Ground truth: {prompt.get('ground_truth', 'N/A')}")
        print(f"    Correct: {'✓' if is_correct else '✗'}")

        # Store result
        result_dict = {
            'prompt_id': prompt['id'],
            'prompt_text': prompt['text'],
            'ground_truth': prompt.get('ground_truth', ''),
            'benchmark': benchmark_name,
            'selected_answer': result.selected_answer,
            'selected_index': result.selected_index,
            'judge_reasoning': result.judge_reasoning,
            'final_answer_extracted': result.final_answer_extracted,
            'all_samples': result.all_answers,
            'num_samples': result.num_samples,
            'total_cost_usd': result.total_cost_usd,
            'avg_latency_ms': result.avg_latency_ms,
            'is_correct': is_correct
        }

        results.append(result_dict)
        print()

    # Calculate accuracy
    accuracy = correct_count / len(prompts) if prompts else 0.0

    # Save results
    output = {
        'experiment': 'E19_correctness_best_of_n_multi_benchmark',
        'benchmark': benchmark_name,
        'run_number': run_number,
        'config': {
            'sample_model': SAMPLE_MODEL,
            'num_samples': NUM_SAMPLES,
            'judge': JUDGE_MODEL,
            'judge_mode': 'correctness_evaluation',
            'num_prompts': len(prompts)
        },
        'results': results,
        'total_cost_usd': total_cost,
        'accuracy': accuracy,
        'correct_count': correct_count,
        'total_prompts': len(prompts)
    }

    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*70}")
    print(f"Run {run_number} complete!")
    print(f"Benchmark: {benchmark_name.upper()}")
    print(f"Accuracy: {accuracy:.1%} ({correct_count}/{len(prompts)})")
    print(f"Total cost: ${total_cost:.2f}")
    print(f"Saved to: {output_file}")
    print(f"{'='*70}\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='E19: Correctness-Based Best-of-N - Multi-Benchmark')
    parser.add_argument('--benchmark', choices=['gsm8k', 'mmlu', 'humaneval', 'gpqa', 'all'],
                       default='all', help='Benchmark to run')
    parser.add_argument('--run', type=int, default=1, help='Run number (1-3)')
    parser.add_argument('--output-dir', default='results/phase3_multi', help='Output directory')

    args = parser.parse_args()

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Determine which benchmarks to run
    if args.benchmark == 'all':
        benchmarks_to_run = BENCHMARKS.items()
    else:
        benchmarks_to_run = [(args.benchmark, BENCHMARKS[args.benchmark])]

    # Run experiments
    for benchmark_name, prompts_file in benchmarks_to_run:
        output_file = f'{args.output_dir}/e19_{benchmark_name}_run{args.run}.json'
        run_single_experiment(benchmark_name, prompts_file, args.run, output_file)


if __name__ == '__main__':
    main()
