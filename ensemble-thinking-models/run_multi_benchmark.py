#!/usr/bin/env python3
"""
Multi-Benchmark Runner

Runs all 4 configurations (opus-fast, opus-thinking, vote, self-consistency)
across multiple benchmarks.

Experiments:
- E6: MMLU-100 (knowledge tasks)
- E7: GPQA-50 (below capability limit, ~70% baseline)
- E8: HumanEval-50 (very low baseline, ~30%)
- E9-E10: Individual baselines for GPQA and HumanEval
- E11-E13: Thinking mode on MMLU, GPQA, HumanEval

Usage:
  python3 run_multi_benchmark.py --benchmark mmlu --run 1
  python3 run_multi_benchmark.py --benchmark gpqa --run 1
  python3 run_multi_benchmark.py --benchmark humaneval --run 1
"""

import json
import sys
import os
import argparse
from ensemble_shared.bedrock_client import BedrockClient, calculate_cost
from aggregators.vote import VoteAggregator
from aggregators.self_consistency import SelfConsistencyAggregator

BENCHMARKS = {
    'mmlu': {
        'file': 'prompts/mmlu_100_full.json',
        'name': 'MMLU-100',
        'type': 'knowledge'
    },
    'gpqa': {
        'file': 'prompts/gpqa_50.json',
        'name': 'GPQA-50',
        'type': 'graduate_science'
    },
    'humaneval': {
        'file': 'prompts/humaneval_50.json',
        'name': 'HumanEval-50',
        'type': 'code'
    }
}

MODELS = {
    'opus-fast': 'us.anthropic.claude-opus-4-6-v1',
    'opus-thinking': 'us.anthropic.claude-opus-4-6-v1',
    'sonnet-fast': 'us.anthropic.claude-sonnet-4-6',
    'haiku-fast': 'us.anthropic.claude-haiku-4-5-20251001-v1:0'
}


def run_individual(client, model_key, model_id, prompts, extended_thinking=False):
    """Run individual model"""
    results = []
    total_cost = 0.0

    for i, prompt in enumerate(prompts, 1):
        print(f"  [{i}/{len(prompts)}] {prompt['id']}...", end='', flush=True)

        if extended_thinking:
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

        cost = calculate_cost(model_id, input_tokens, output_tokens)
        total_cost += cost

        results.append({
            'prompt_id': prompt['id'],
            'prompt_text': prompt['text'],
            'ground_truth': prompt.get('ground_truth', ''),
            'answer': answer,
            'cost_usd': cost,
            'latency_ms': latency
        })

        print(f" ${cost:.4f}")

    return results, total_cost


def run_vote_ensemble(client, prompts, judge_model='haiku-fast'):
    """Run vote ensemble"""
    aggregator = VoteAggregator(mock_mode=False, use_semantic_vote=True, judge_model=judge_model)

    # Proposers: opus, sonnet, haiku (all fast mode)
    proposer_models = {
        'opus-fast': MODELS['opus-fast'],
        'sonnet-fast': MODELS['sonnet-fast'],
        'haiku-fast': MODELS['haiku-fast']
    }

    results = []
    total_cost = 0.0

    for i, prompt in enumerate(prompts, 1):
        print(f"  [{i}/{len(prompts)}] {prompt['id']}")

        # Generate responses from proposers
        responses = {}
        for model_key, model_id in proposer_models.items():
            print(f"    {model_key}...", end='', flush=True)

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

        # Vote
        print(f"    Judge ({judge_model})...", end='', flush=True)
        vote_result = aggregator.aggregate(responses, prompt)
        total_cost += vote_result.judge_cost_usd

        results.append({
            'prompt_id': prompt['id'],
            'prompt_text': prompt['text'],
            'ground_truth': prompt.get('ground_truth', ''),
            'selected_answer': vote_result.selected_answer,
            'vote_counts': vote_result.vote_counts,
            'judge_reasoning': vote_result.judge_reasoning,
            'judge_cost_usd': vote_result.judge_cost_usd
        })

        print(f" ${vote_result.judge_cost_usd:.4f}")

    return results, total_cost


def run_self_consistency(client, model_key, model_id, prompts, benchmark_type='numeric'):
    """Run self-consistency"""
    aggregator = SelfConsistencyAggregator(mock_mode=False)

    results = []
    total_cost = 0.0

    for i, prompt in enumerate(prompts, 1):
        print(f"  [{i}/{len(prompts)}] {prompt['id']}")

        result = aggregator.aggregate(
            model_id=model_id,
            model_key=model_key,
            prompt_text=prompt['text'],
            num_samples=5,
            temperature=0.7,
            max_tokens=2048,
            extended_thinking=False,
            benchmark=benchmark_type
        )

        result.prompt_id = prompt['id']
        total_cost += result.total_cost_usd

        results.append({
            'prompt_id': prompt['id'],
            'prompt_text': prompt['text'],
            'ground_truth': prompt.get('ground_truth', ''),
            'selected_answer': result.selected_answer,
            'vote_counts': result.vote_counts,
            'agreement_rate': result.agreement_rate,
            'all_answers': result.all_answers,
            'cost_usd': result.total_cost_usd
        })

    return results, total_cost


def main():
    parser = argparse.ArgumentParser(description='Multi-Benchmark Runner')
    parser.add_argument('--benchmark', required=True, choices=['mmlu', 'gpqa', 'humaneval'],
                       help='Which benchmark to run')
    parser.add_argument('--config', required=True,
                       choices=['opus-fast', 'opus-thinking', 'vote', 'self-consistency'],
                       help='Which configuration to run')
    parser.add_argument('--run', type=int, default=1, help='Run number (1-3)')
    parser.add_argument('--output-dir', default='results/phase2', help='Output directory')

    args = parser.parse_args()

    benchmark_info = BENCHMARKS[args.benchmark]
    prompts_file = benchmark_info['file']

    print(f"\n{'='*60}")
    print(f"Multi-Benchmark Runner")
    print(f"Benchmark: {benchmark_info['name']}")
    print(f"Config: {args.config}")
    print(f"Run: {args.run}")
    print(f"{'='*60}\n")

    # Load prompts
    with open(prompts_file, 'r') as f:
        data = json.load(f)
    prompts = data.get('prompts', [])

    print(f"Loaded {len(prompts)} prompts\n")

    # Initialize client
    client = BedrockClient()

    # Run configuration
    results = None
    total_cost = 0.0

    if args.config == 'opus-fast':
        print("Running opus-fast individual...")
        results, total_cost = run_individual(client, 'opus-fast', MODELS['opus-fast'], prompts)

    elif args.config == 'opus-thinking':
        print("Running opus-thinking individual...")
        results, total_cost = run_individual(client, 'opus-thinking', MODELS['opus-thinking'],
                                            prompts, extended_thinking=True)

    elif args.config == 'vote':
        print("Running vote ensemble (Haiku judge)...")
        results, total_cost = run_vote_ensemble(client, prompts, judge_model='haiku-fast')

    elif args.config == 'self-consistency':
        print("Running self-consistency (opus-fast × 5)...")
        # Determine benchmark type for extraction
        benchmark_type = 'numeric' if args.benchmark == 'gpqa' else 'mc'  # MMLU/GPQA are MC
        results, total_cost = run_self_consistency(client, 'opus-fast', MODELS['opus-fast'],
                                                   prompts, benchmark_type)

    # Save results
    output_file = f"{args.output_dir}/{args.benchmark}_{args.config}_run{args.run}.json"
    os.makedirs(args.output_dir, exist_ok=True)

    output = {
        'experiment': f'E6-E13_{args.benchmark}',
        'benchmark': benchmark_info['name'],
        'config': args.config,
        'run_number': args.run,
        'num_prompts': len(prompts),
        'results': results,
        'total_cost_usd': total_cost
    }

    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Complete!")
    print(f"Total cost: ${total_cost:.2f}")
    print(f"Saved to: {output_file}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
