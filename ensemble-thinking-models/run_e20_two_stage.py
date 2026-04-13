#!/usr/bin/env python3
"""
E20: Two-Stage Judging

Tests the hypothesis: "Does combining both approaches work better?"

Stage 1: Agreement-based grouping (like E1 original)
Stage 2: Correctness evaluation within majority group (like E18)

Configuration:
- Proposers: opus-fast, sonnet-fast, haiku-fast
- Judge: opus-fast (used for both stages)
- Stage 1: Group by semantic agreement
- Stage 2: Evaluate correctness within majority
- Benchmark: GSM8K-100
- Runs: 3

Expected cost: ~$24 total (~$8 per run, 2× judge calls per prompt)
Expected time: ~4 hours
"""

import json
import sys
import os
from aggregators.two_stage import TwoStageAggregator
from ensemble_shared.bedrock_client import BedrockClient, calculate_cost

PROPOSER_MODELS = {
    'opus-fast': 'us.anthropic.claude-opus-4-6-v1',
    'sonnet-fast': 'us.anthropic.claude-sonnet-4-6',
    'haiku-fast': 'us.anthropic.claude-haiku-4-5-20251001-v1:0'
}

JUDGE_MODEL = 'opus-fast'


def run_single_experiment(prompts_file: str, run_number: int, output_file: str):
    """Run one instance of E20 experiment"""

    print(f"\n{'='*60}")
    print(f"E20: Two-Stage Judging - Run {run_number}")
    print(f"{'='*60}\n")

    # Load prompts
    with open(prompts_file, 'r') as f:
        data = json.load(f)
    prompts = data.get('prompts', [])

    print(f"Loaded {len(prompts)} prompts")
    print(f"Proposers: {list(PROPOSER_MODELS.keys())}")
    print(f"Judge: {JUDGE_MODEL}")
    print(f"Stage 1: Agreement-based grouping")
    print(f"Stage 2: Correctness evaluation\n")

    # Initialize client and aggregator
    client = BedrockClient()
    aggregator = TwoStageAggregator(mock_mode=False, judge_model=JUDGE_MODEL)

    results = []
    total_cost = 0.0

    for i, prompt in enumerate(prompts, 1):
        print(f"[{i}/{len(prompts)}] {prompt['id']}")

        # Generate responses from all proposers
        responses = {}
        proposer_cost = 0.0

        for model_key, model_id in PROPOSER_MODELS.items():
            print(f"  {model_key}...", end='', flush=True)

            answer, input_tokens, output_tokens, latency = client.call_model(
                model_id=model_id,
                prompt=prompt['text'],
                max_tokens=2048,
                temperature=0.0
            )

            cost = calculate_cost(model_id, input_tokens, output_tokens)
            proposer_cost += cost

            responses[model_key] = {
                'answer': answer,
                'cost_usd': cost,
                'latency_ms': latency
            }

            print(f" ${cost:.4f}")

        # Two-stage judging
        print(f"  Two-stage judge ({JUDGE_MODEL})...", end='', flush=True)

        two_stage_result = aggregator.aggregate(responses, prompt)
        total_cost += proposer_cost + two_stage_result.total_cost_usd

        print(f" ${two_stage_result.total_cost_usd:.4f}")
        print(f"    Stage 1: Majority = {two_stage_result.stage1_majority}")
        print(f"    Stage 2: Selected = {two_stage_result.selected_model}")

        # Store result
        result_dict = {
            'prompt_id': prompt['id'],
            'prompt_text': prompt['text'],
            'ground_truth': prompt.get('ground_truth', ''),
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
            'proposer_cost_usd': proposer_cost
        }

        results.append(result_dict)
        print()

    # Save results
    output = {
        'experiment': 'E20_two_stage',
        'run_number': run_number,
        'config': {
            'proposers': list(PROPOSER_MODELS.keys()),
            'judge': JUDGE_MODEL,
            'stage1': 'agreement_grouping',
            'stage2': 'correctness_evaluation',
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

    parser = argparse.ArgumentParser(description='E20: Two-Stage Judging')
    parser.add_argument('--prompts', default='prompts/gsm8k_100.json', help='Prompts file')
    parser.add_argument('--run', type=int, default=1, help='Run number (1-3)')
    parser.add_argument('--output', help='Output file (auto-generated if not specified)')

    args = parser.parse_args()

    if not args.output:
        args.output = f'results/phase2/e20_two_stage_run{args.run}.json'

    # Create output directory
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    run_single_experiment(args.prompts, args.run, args.output)


if __name__ == '__main__':
    main()
