#!/usr/bin/env python3
"""
E20: Two-Stage Judging - Multi-Benchmark

Tests the hypothesis: "Do judge failures generalize beyond math?"

Runs two-stage judging (agreement → correctness) across 4 benchmarks:
- GSM8K-100: Math problems (objective, numeric)
- MMLU-100: Multiple choice knowledge (objective, categorical)
- HumanEval-50: Code generation (objective, executable)
- GPQA-50: Graduate science (objective, hard)

Configuration:
- Proposers: opus-fast, sonnet-fast, haiku-fast
- Judge: opus-fast (two-stage: agreement filtering → correctness evaluation)
- Runs: 3 per benchmark

Expected cost: ~$96 total (~$8 per run × 3 runs × 4 benchmarks)
Expected time: ~15 hours
"""

import json
import sys
import os
from aggregators.two_stage import TwoStageAggregator
from ensemble_shared.bedrock_client import BedrockClient, calculate_cost
from benchmarks.evaluators import evaluate_benchmark

PROPOSER_MODELS = {
    'opus-fast': 'us.anthropic.claude-opus-4-6-v1',
    'sonnet-fast': 'us.anthropic.claude-sonnet-4-6',
    'haiku-fast': 'us.anthropic.claude-haiku-4-5-20251001-v1:0'
}

JUDGE_MODEL = 'opus-fast'
JUDGE_MODEL_ID = 'us.anthropic.claude-opus-4-6-v1'

BENCHMARKS = {
    'gsm8k': 'prompts/gsm8k_100.json',
    'mmlu': 'prompts/mmlu_100.json',
    'humaneval': 'prompts/humaneval_50.json',
    'gpqa': 'prompts/gpqa_50.json'
}


def run_single_experiment(benchmark_name: str, prompts_file: str, run_number: int, output_file: str):
    """Run one instance of E20 experiment on a specific benchmark"""

    print(f"\n{'='*70}")
    print(f"E20: Two-Stage Judging - {benchmark_name.upper()} - Run {run_number}")
    print(f"{'='*70}\n")

    # Load prompts
    with open(prompts_file, 'r') as f:
        data = json.load(f)
    prompts = data.get('prompts', [])

    print(f"Benchmark: {benchmark_name.upper()}")
    print(f"Loaded {len(prompts)} prompts")
    print(f"Proposers: {list(PROPOSER_MODELS.keys())}")
    print(f"Judge: {JUDGE_MODEL} (TWO-STAGE: agreement → correctness)")
    print()

    # Initialize client and aggregator
    client = BedrockClient()
    aggregator = TwoStageAggregator(mock_mode=False, judge_model=JUDGE_MODEL)

    results = []
    total_cost = 0.0
    correct_count = 0

    for i, prompt in enumerate(prompts, 1):
        print(f"[{i}/{len(prompts)}] {prompt['id']}")

        # Generate responses from all proposers
        responses = {}
        for model_key, model_id in PROPOSER_MODELS.items():
            print(f"  {model_key}...", end='', flush=True)

            answer, input_tokens, output_tokens, latency = client.call_model(
                model_id=model_id,
                prompt=prompt['text'],
                max_tokens=2048,
                temperature=0.0
            )

            cost = calculate_cost(model_id, input_tokens, output_tokens)
            total_cost += cost

            responses[model_key] = {
                'answer': answer,
                'cost_usd': cost,
                'latency_ms': latency
            }

            print(f" ${cost:.4f}")

        # Judge uses two-stage approach
        print(f"  Judge ({JUDGE_MODEL}) TWO-STAGE judging...", end='', flush=True)

        two_stage_result = aggregator.aggregate(responses, prompt)
        total_cost += two_stage_result.total_cost_usd

        print(f" ${two_stage_result.total_cost_usd:.4f}")

        # Evaluate correctness using benchmark-specific evaluator
        # TwoStageResult doesn't have final_answer_extracted, just use selected_answer
        is_correct = evaluate_benchmark(prompt, two_stage_result.selected_answer)
        if is_correct:
            correct_count += 1

        print(f"    Strategy: {two_stage_result.strategy}")
        print(f"    Selected: {two_stage_result.selected_model}")
        print(f"    Ground truth: {prompt.get('ground_truth', 'N/A')}")
        print(f"    Correct: {'✓' if is_correct else '✗'}")

        # Store result
        result_dict = {
            'prompt_id': prompt['id'],
            'prompt_text': prompt['text'],
            'ground_truth': prompt.get('ground_truth', ''),
            'benchmark': benchmark_name,
            'responses': responses,
            'two_stage_result': {
                'strategy': two_stage_result.strategy,
                'selected_answer': two_stage_result.selected_answer,
                'selected_model': two_stage_result.selected_model,
                'stage1_groups': two_stage_result.stage1_groups,
                'stage1_majority': two_stage_result.stage1_majority,
                'stage1_reasoning': two_stage_result.stage1_reasoning,
                'stage1_cost_usd': two_stage_result.stage1_cost_usd,
                'stage2_evaluated': two_stage_result.stage2_evaluated,
                'stage2_reasoning': two_stage_result.stage2_reasoning,
                'stage2_cost_usd': two_stage_result.stage2_cost_usd,
                'total_cost_usd': two_stage_result.total_cost_usd,
                'total_latency_ms': two_stage_result.total_latency_ms
            },
            'is_correct': is_correct
        }

        results.append(result_dict)
        print()

    # Calculate accuracy
    accuracy = correct_count / len(prompts) if prompts else 0.0

    # Save results
    output = {
        'experiment': 'E20_two_stage_multi_benchmark',
        'benchmark': benchmark_name,
        'run_number': run_number,
        'config': {
            'proposers': list(PROPOSER_MODELS.keys()),
            'judge': JUDGE_MODEL,
            'judge_mode': 'two_stage_agreement_then_correctness',
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

    parser = argparse.ArgumentParser(description='E20: Two-Stage Judging - Multi-Benchmark')
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
        output_file = f'{args.output_dir}/e20_{benchmark_name}_run{args.run}.json'
        run_single_experiment(benchmark_name, prompts_file, args.run, output_file)


if __name__ == '__main__':
    main()
