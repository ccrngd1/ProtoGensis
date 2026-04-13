#!/usr/bin/env python3
"""
E19: Best-of-N with Correctness-Based Judging

Tests the hypothesis: "Does best-of-N work if we judge correctness instead of quality?"

Key difference from E2:
- E2: Judge evaluates "quality" (clarity, completeness, explanation)
- E19: Judge evaluates CORRECTNESS of the final answer

Configuration:
- Candidate model: opus-fast
- Judge model: opus-fast (evaluating CORRECTNESS, not quality)
- Samples: 5 per prompt
- Temperature: 0.7 (for diversity)
- Benchmark: GSM8K-100
- Runs: 3

Expected cost: ~$24 total (~$8 per run, same as E2)
Expected time: ~3 hours
"""

import json
import sys
import os
from aggregators.best_of_n_correctness import CorrectnessBasedBestOfN
from ensemble_shared.bedrock_client import BedrockClient, calculate_cost

MODEL_KEY = 'opus-fast'
MODEL_ID = 'us.anthropic.claude-opus-4-6-v1'
JUDGE_KEY = 'opus-fast'
JUDGE_ID = 'us.anthropic.claude-opus-4-6-v1'
NUM_SAMPLES = 5
TEMPERATURE = 0.7


def run_single_experiment(prompts_file: str, run_number: int, output_file: str):
    """Run one instance of E19 experiment"""

    print(f"\n{'='*60}")
    print(f"E19: Best-of-N with Correctness Judging - Run {run_number}")
    print(f"{'='*60}\n")

    # Load prompts
    with open(prompts_file, 'r') as f:
        data = json.load(f)
    prompts = data.get('prompts', [])

    print(f"Loaded {len(prompts)} prompts")
    print(f"Candidate model: {MODEL_KEY}")
    print(f"Judge model: {JUDGE_KEY} (evaluating CORRECTNESS)")
    print(f"Samples per prompt: {NUM_SAMPLES}")
    print(f"Temperature: {TEMPERATURE}\n")

    # Initialize aggregator
    aggregator = CorrectnessBasedBestOfN(mock_mode=False)

    results = []
    total_cost = 0.0

    for i, prompt in enumerate(prompts, 1):
        print(f"[{i}/{len(prompts)}] {prompt['id']}")

        result = aggregator.aggregate(
            model_id=MODEL_ID,
            model_key=MODEL_KEY,
            judge_model_id=JUDGE_ID,
            judge_key=JUDGE_KEY,
            prompt_text=prompt['text'],
            num_samples=NUM_SAMPLES,
            temperature=TEMPERATURE,
            max_tokens=2048,
            extended_thinking=False
        )

        result.prompt_id = prompt['id']
        total_cost += result.total_cost_usd

        result_dict = {
            'prompt_id': prompt['id'],
            'prompt_text': prompt['text'],
            'ground_truth': prompt.get('ground_truth', ''),
            'selected_answer': result.selected_answer,
            'selected_index': result.selected_index,
            'judge_reasoning': result.judge_reasoning,
            'final_answer_extracted': result.final_answer_extracted,
            'all_samples': result.all_answers,
            'num_samples': result.num_samples,
            'total_cost_usd': result.total_cost_usd,
            'avg_latency_ms': result.avg_latency_ms
        }

        results.append(result_dict)
        print()

    # Save results
    output = {
        'experiment': 'E19_correctness_best_of_n',
        'run_number': run_number,
        'config': {
            'model': MODEL_KEY,
            'judge': JUDGE_KEY,
            'judge_mode': 'correctness_evaluation',
            'num_samples': NUM_SAMPLES,
            'temperature': TEMPERATURE,
            'benchmark': 'GSM8K-100',
            'num_prompts': len(prompts)
        },
        'results': results,
        'total_cost_usd': total_cost
    }

    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Run {run_number} complete!")
    print(f"Total cost: ${total_cost:.2f}")
    print(f"Saved to: {output_file}")
    print(f"{'='*60}\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='E19: Best-of-N with Correctness Judging')
    parser.add_argument('--prompts', default='prompts/gsm8k_100.json', help='Prompts file')
    parser.add_argument('--run', type=int, default=1, help='Run number (1-3)')
    parser.add_argument('--output', help='Output file (auto-generated if not specified)')

    args = parser.parse_args()

    if not args.output:
        args.output = f'results/phase2/e19_correctness_best_of_n_run{args.run}.json'

    # Create output directory
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    run_single_experiment(args.prompts, args.run, args.output)


if __name__ == '__main__':
    main()
