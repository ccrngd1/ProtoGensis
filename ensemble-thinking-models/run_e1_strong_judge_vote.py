#!/usr/bin/env python3
"""
E1: Strong-Judge Vote Ensemble

Test if vote ensemble failure is architectural (weak Haiku judge)
or fundamental by using Opus as judge instead.

Configuration:
- Proposers: 6 models (opus-fast, sonnet-fast, haiku-fast, opus-thinking, sonnet-thinking, haiku-thinking)
- Judge: opus-fast (strongest model, not Haiku)
- Benchmark: GSM8K-100
- Runs: 3 independent runs

Expected cost: ~$20 total (~$7 per run)
Expected time: ~2 hours
"""

import json
import sys
import os
from aggregators.vote import VoteAggregator
from ensemble_shared.bedrock_client import BedrockClient

# Model configurations
PROPOSER_MODELS = {
    'opus-fast': 'us.anthropic.claude-opus-4-6-20250929-v1:0',
    'sonnet-fast': 'us.anthropic.claude-sonnet-4-6-20250929-v1:0',
    'haiku-fast': 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
    'opus-thinking': 'us.anthropic.claude-opus-4-6-20250929-v1:0',
    'sonnet-thinking': 'us.anthropic.claude-sonnet-4-6-20250929-v1:0',
    'haiku-thinking': 'us.anthropic.claude-haiku-4-5-20251001-v1:0'
}

JUDGE_MODEL = 'opus-fast'
JUDGE_MODEL_ID = 'us.anthropic.claude-opus-4-6-20250929-v1:0'


def run_single_experiment(prompts_file: str, run_number: int, output_file: str):
    """Run one instance of E1 experiment"""

    print(f"\n{'='*60}")
    print(f"E1: Strong-Judge Vote Ensemble - Run {run_number}")
    print(f"{'='*60}\n")

    # Load prompts
    with open(prompts_file, 'r') as f:
        data = json.load(f)
    prompts = data.get('prompts', [])

    print(f"Loaded {len(prompts)} prompts")
    print(f"Judge model: {JUDGE_MODEL} (strongest)")
    print(f"Proposers: {len(PROPOSER_MODELS)} models\n")

    # Initialize client and aggregator
    client = BedrockClient()
    aggregator = VoteAggregator(mock_mode=False, use_semantic_vote=True, judge_model=JUDGE_MODEL)

    results = []
    total_cost = 0.0

    for i, prompt in enumerate(prompts, 1):
        print(f"[{i}/{len(prompts)}] {prompt['id']}")

        # Generate responses from all proposers
        responses = {}
        for model_key, model_id in PROPOSER_MODELS.items():
            print(f"  {model_key}...", end='', flush=True)

            # Use thinking mode for thinking variants
            if 'thinking' in model_key:
                answer, input_tokens, output_tokens, latency = client.call_model(
                    model_id=model_id,
                    prompt=prompt['text'],
                    max_tokens=2048,
                    temperature=0.0,
                    thinking_budget=10000
                )
            else:
                answer, input_tokens, output_tokens, latency = client.call_model(
                    model_id=model_id,
                    prompt=prompt['text'],
                    max_tokens=2048,
                    temperature=0.0
                )

            from ensemble_shared.bedrock_client import calculate_cost
            cost = calculate_cost(model_id, input_tokens, output_tokens)
            total_cost += cost

            responses[model_key] = {
                'answer': answer,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'latency_ms': latency,
                'cost_usd': cost
            }

            print(f" ${cost:.4f}")

        # Vote aggregation with Opus judge
        print(f"  Judge ({JUDGE_MODEL}) evaluating...")
        vote_result = aggregator.aggregate(responses, prompt)

        total_cost += vote_result.judge_cost_usd

        result = {
            'prompt_id': prompt['id'],
            'prompt_text': prompt['text'],
            'ground_truth': prompt.get('ground_truth', ''),
            'responses': responses,
            'vote_result': {
                'strategy': vote_result.strategy,
                'selected_answer': vote_result.selected_answer,
                'vote_counts': vote_result.vote_counts,
                'judge_reasoning': vote_result.judge_reasoning,
                'convergence': vote_result.convergence,
                'models_agreeing': vote_result.models_agreeing,
                'judge_cost_usd': vote_result.judge_cost_usd
            }
        }

        results.append(result)
        print(f"  Total cost this prompt: ${sum(r['cost_usd'] for r in responses.values()) + vote_result.judge_cost_usd:.4f}")
        print()

    # Save results
    output = {
        'experiment': 'E1_strong_judge_vote',
        'run_number': run_number,
        'config': {
            'proposer_models': list(PROPOSER_MODELS.keys()),
            'judge_model': JUDGE_MODEL,
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

    parser = argparse.ArgumentParser(description='E1: Strong-Judge Vote Ensemble')
    parser.add_argument('--prompts', default='prompts/gsm8k_100.json', help='Prompts file')
    parser.add_argument('--run', type=int, default=1, help='Run number (1-3)')
    parser.add_argument('--output', help='Output file (auto-generated if not specified)')

    args = parser.parse_args()

    if not args.output:
        args.output = f'results/phase2/e1_strong_judge_vote_run{args.run}.json'

    # Create output directory
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    run_single_experiment(args.prompts, args.run, args.output)


if __name__ == '__main__':
    main()
