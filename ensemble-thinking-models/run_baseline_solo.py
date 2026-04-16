#!/usr/bin/env python3
"""
Baseline: Single Model (Opus Solo)

Runs Opus-fast on benchmarks to establish baseline performance.
This gives us ground truth for comparing judge-based ensembles.

Usage:
    python3 run_baseline_solo.py --benchmark gsm8k --run 1
"""

import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ensemble_shared.bedrock_client import BedrockClient, calculate_cost
from benchmarks.evaluators import evaluate_benchmark

MODEL = 'opus-fast'
MODEL_ID = 'us.anthropic.claude-opus-4-6-v1'

BENCHMARKS = {
    'gsm8k': 'prompts/gsm8k_100.json',
    'mmlu': 'prompts/mmlu_100.json',
    'humaneval': 'prompts/humaneval_50.json',
    'gpqa': 'prompts/gpqa_50.json'
}


def run_baseline(benchmark_name: str, prompts_file: str, run_number: int, output_file: str):
    """Run Opus solo baseline on a benchmark"""

    print(f"\n{'='*70}")
    print(f"Baseline: Opus Solo - {benchmark_name.upper()} - Run {run_number}")
    print(f"{'='*70}\n")

    # Load prompts
    with open(prompts_file, 'r') as f:
        data = json.load(f)
    prompts = data.get('prompts', [])

    print(f"Benchmark: {benchmark_name.upper()}")
    print(f"Loaded {len(prompts)} prompts")
    print(f"Model: {MODEL}")
    print()

    # Initialize client
    client = BedrockClient()

    results = []
    total_cost = 0.0
    correct_count = 0

    for i, prompt in enumerate(prompts, 1):
        print(f"[{i}/{len(prompts)}] {prompt['id']}")

        # Generate response
        print(f"  {MODEL}...", end='', flush=True)

        answer, input_tokens, output_tokens, latency = client.call_model(
            model_id=MODEL_ID,
            prompt=prompt['text'],
            max_tokens=2048,
            temperature=0.0
        )

        cost = calculate_cost(MODEL_ID, input_tokens, output_tokens)
        total_cost += cost

        print(f" ${cost:.4f}")

        # Evaluate correctness
        is_correct = evaluate_benchmark(prompt, answer)
        if is_correct:
            correct_count += 1

        print(f"    Correct: {'✓' if is_correct else '✗'}")

        # Store result
        result_dict = {
            'prompt_id': prompt['id'],
            'prompt_text': prompt['text'],
            'ground_truth': prompt.get('ground_truth', ''),
            'benchmark': benchmark_name,
            'model_answer': answer,
            'is_correct': is_correct,
            'cost_usd': cost,
            'latency_ms': latency
        }

        results.append(result_dict)

    # Calculate accuracy
    accuracy = correct_count / len(prompts) if prompts else 0.0

    # Save results
    output = {
        'experiment': 'baseline_opus_solo',
        'benchmark': benchmark_name,
        'run_number': run_number,
        'model': MODEL,
        'config': {
            'model_id': MODEL_ID,
            'temperature': 0.0,
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

    parser = argparse.ArgumentParser(description='Baseline: Opus Solo')
    parser.add_argument('--benchmark', choices=['gsm8k', 'mmlu', 'humaneval', 'gpqa', 'all'],
                       default='all', help='Benchmark to run')
    parser.add_argument('--run', type=int, default=1, help='Run number (1-3)')
    parser.add_argument('--output-dir', default='results/baselines', help='Output directory')

    args = parser.parse_args()

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Determine which benchmarks to run
    if args.benchmark == 'all':
        benchmarks_to_run = BENCHMARKS.items()
    else:
        benchmarks_to_run = [(args.benchmark, BENCHMARKS[args.benchmark])]

    # Run baselines
    for benchmark_name, prompts_file in benchmarks_to_run:
        output_file = f'{args.output_dir}/baseline_{benchmark_name}_run{args.run}.json'
        run_baseline(benchmark_name, prompts_file, args.run, output_file)


if __name__ == '__main__':
    main()
