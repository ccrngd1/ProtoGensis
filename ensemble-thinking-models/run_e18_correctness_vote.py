#!/usr/bin/env python3
"""
E18: Correctness-Based Vote Ensemble

Tests the hypothesis: "Is the judge doing the wrong task?"

Key difference from E1:
- E1: Judge identifies which answers AGREE (semantic majority voting)
- E18: Judge evaluates which answer is most likely CORRECT

Configuration:
- Proposers: opus-fast, sonnet-fast, haiku-fast
- Judge: opus-fast (evaluating CORRECTNESS, not agreement)
- Benchmark: GSM8K-100
- Runs: 3

Expected cost: ~$18 total (~$6 per run, same as E1)
Expected time: ~3 hours
"""

import json
import sys
import os
from aggregators.vote_correctness import CorrectnessVoteAggregator
from ensemble_shared.bedrock_client import BedrockClient, calculate_cost

PROPOSER_MODELS = {
    'opus-fast': 'us.anthropic.claude-opus-4-6-v1',
    'sonnet-fast': 'us.anthropic.claude-sonnet-4-6',
    'haiku-fast': 'us.anthropic.claude-haiku-4-5-20251001-v1:0'
}

JUDGE_MODEL = 'opus-fast'
JUDGE_MODEL_ID = 'us.anthropic.claude-opus-4-6-v1'


def run_single_experiment(prompts_file: str, run_number: int, output_file: str):
    """Run one instance of E18 experiment"""

    print(f"\n{'='*60}")
    print(f"E18: Correctness-Based Vote - Run {run_number}")
    print(f"{'='*60}\n")

    # Load prompts
    with open(prompts_file, 'r') as f:
        data = json.load(f)
    prompts = data.get('prompts', [])

    print(f"Loaded {len(prompts)} prompts")
    print(f"Proposers: {list(PROPOSER_MODELS.keys())}")
    print(f"Judge: {JUDGE_MODEL} (evaluating CORRECTNESS)")
    print()

    # Initialize client and aggregator
    client = BedrockClient()
    aggregator = CorrectnessVoteAggregator(mock_mode=False, judge_model=JUDGE_MODEL)

    results = []
    total_cost = 0.0

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

        # Judge evaluates for correctness
        print(f"  Judge ({JUDGE_MODEL}) evaluating CORRECTNESS...", end='', flush=True)

        vote_result = aggregator.aggregate(responses, prompt)
        total_cost += vote_result.judge_cost_usd

        print(f" ${vote_result.judge_cost_usd:.4f}")
        print(f"    Selected: {vote_result.selected_model} → {vote_result.final_answer_extracted}")

        # Store result
        result_dict = {
            'prompt_id': prompt['id'],
            'prompt_text': prompt['text'],
            'ground_truth': prompt.get('ground_truth', ''),
            'responses': responses,
            'vote_result': {
                'strategy': vote_result.strategy,
                'selected_answer': vote_result.selected_answer,
                'selected_model': vote_result.selected_model,
                'judge_reasoning': vote_result.judge_reasoning,
                'final_answer_extracted': vote_result.final_answer_extracted,
                'judge_cost_usd': vote_result.judge_cost_usd,
                'judge_latency_ms': vote_result.judge_latency_ms
            }
        }

        results.append(result_dict)
        print()

    # Save results
    output = {
        'experiment': 'E18_correctness_vote',
        'run_number': run_number,
        'config': {
            'proposers': list(PROPOSER_MODELS.keys()),
            'judge': JUDGE_MODEL,
            'judge_mode': 'correctness_evaluation',
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

    parser = argparse.ArgumentParser(description='E18: Correctness-Based Vote Ensemble')
    parser.add_argument('--prompts', default='prompts/gsm8k_100.json', help='Prompts file')
    parser.add_argument('--run', type=int, default=1, help='Run number (1-3)')
    parser.add_argument('--output', help='Output file (auto-generated if not specified)')

    args = parser.parse_args()

    if not args.output:
        args.output = f'results/phase2/e18_correctness_vote_run{args.run}.json'

    # Create output directory
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    run_single_experiment(args.prompts, args.run, args.output)


if __name__ == '__main__':
    main()
