#!/usr/bin/env python3
"""
Theory Testing Runner

E14: Budget model baselines (Haiku, Sonnet on GSM8K)
E15-E17: Self-consistency at different capability levels

Tests the systematic error theory:
- Does self-consistency help below capability limit?
- Where is the help→hurt threshold?

Usage:
  # E14: Budget baselines
  python3 run_theory_tests.py --experiment e14 --model haiku-fast --run 1
  python3 run_theory_tests.py --experiment e14 --model sonnet-fast --run 1

  # E15-E17: Self-consistency at different baselines
  python3 run_theory_tests.py --experiment e15 --model haiku-fast --run 1
  python3 run_theory_tests.py --experiment e17 --model sonnet-fast --run 1
"""

import json
import sys
import os
import argparse

# Add parent directory to path to import ensemble_shared
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ensemble_shared.bedrock_client import BedrockClient, calculate_cost
from aggregators.self_consistency import SelfConsistencyAggregator

MODELS = {
    'haiku-fast': 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
    'sonnet-fast': 'us.anthropic.claude-sonnet-4-6',
    'opus-fast': 'us.anthropic.claude-opus-4-6-v1'
}

EXPERIMENTS = {
    'e14': {
        'name': 'Budget Baselines',
        'description': 'Individual baselines to map capability spectrum',
        'method': 'individual'
    },
    'e15': {
        'name': 'Self-Consistency Low Baseline',
        'description': 'SC on Haiku (~60-70% baseline)',
        'method': 'self-consistency'
    },
    'e17': {
        'name': 'Self-Consistency Mid Baseline',
        'description': 'SC on Sonnet (~80% baseline)',
        'method': 'self-consistency'
    }
}


def run_individual(client, model_key, model_id, prompts):
    """Run individual model"""
    results = []
    total_cost = 0.0

    print(f"Running {model_key} individual baseline...\n")

    for i, prompt in enumerate(prompts, 1):
        print(f"  [{i}/{len(prompts)}] {prompt['id']}...", end='', flush=True)

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


def run_self_consistency(client, model_key, model_id, prompts):
    """Run self-consistency"""
    aggregator = SelfConsistencyAggregator(mock_mode=False)

    results = []
    total_cost = 0.0

    print(f"Running {model_key} self-consistency (5 samples)...\n")

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
            benchmark='numeric'  # GSM8K is numeric
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

        print(f"    Selected: {result.selected_answer[:50]}... (${result.total_cost_usd:.4f})")

    return results, total_cost


def main():
    parser = argparse.ArgumentParser(description='Theory Testing Runner')
    parser.add_argument('--experiment', required=True, choices=['e14', 'e15', 'e17'],
                       help='Which experiment to run')
    parser.add_argument('--model', required=True, choices=['haiku-fast', 'sonnet-fast'],
                       help='Which model to test')
    parser.add_argument('--run', type=int, default=1, help='Run number (1-3)')
    parser.add_argument('--prompts', default='prompts/gsm8k_100.json', help='Prompts file')
    parser.add_argument('--output-dir', default='results/phase2', help='Output directory')

    args = parser.parse_args()

    exp_info = EXPERIMENTS[args.experiment]

    print(f"\n{'='*60}")
    print(f"{exp_info['name']} ({args.experiment.upper()})")
    print(f"{exp_info['description']}")
    print(f"Model: {args.model}")
    print(f"Run: {args.run}")
    print(f"{'='*60}\n")

    # Load prompts
    with open(args.prompts, 'r') as f:
        data = json.load(f)
    prompts = data.get('prompts', [])

    print(f"Loaded {len(prompts)} prompts\n")

    # Initialize client
    client = BedrockClient()
    model_id = MODELS[args.model]

    # Run experiment
    results = None
    total_cost = 0.0

    if exp_info['method'] == 'individual':
        results, total_cost = run_individual(client, args.model, model_id, prompts)
    elif exp_info['method'] == 'self-consistency':
        results, total_cost = run_self_consistency(client, args.model, model_id, prompts)

    # Save results
    output_file = f"{args.output_dir}/{args.experiment}_{args.model}_run{args.run}.json"
    os.makedirs(args.output_dir, exist_ok=True)

    output = {
        'experiment': args.experiment.upper(),
        'name': exp_info['name'],
        'model': args.model,
        'method': exp_info['method'],
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
