#!/usr/bin/env python3
"""
Run persona diversity experiment: Test if personas create ensemble benefit.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from moa.core import create_moa_from_recipe
from moa.bedrock_client import BedrockClient
from moa.models import BEDROCK_MODELS
from moa.judge import QualityJudge

async def run_single_model(model_key: str, prompt: str):
    """Run single model as baseline."""
    client = BedrockClient()
    model_info = BEDROCK_MODELS[model_key]

    result = await client.invoke_model(
        model_id=model_info.model_id,
        prompt=prompt,
        max_tokens=2048,
        temperature=0.7
    )

    return {
        "model_key": model_key,
        "response": result['response'],
        "input_tokens": result['input_tokens'],
        "output_tokens": result['output_tokens']
    }

async def run_ensemble(recipe_name: str, prompt: str):
    """Run ensemble recipe."""
    moa = create_moa_from_recipe(recipe_name)
    response = await moa.run(prompt)

    return {
        "recipe": recipe_name,
        "response": response.final_response,
        "cost": response.cost_summary.get('total_cost', 0),
        "latency_ms": response.latency_summary.get('total_ms', 0)
    }

async def main():
    # Load prompts
    with open('benchmark/prompts.json') as f:
        data = json.load(f)
        all_prompts = data['prompts']

    print("="*80)
    print("PERSONA DIVERSITY EXPERIMENT")
    print("="*80)
    print(f"\nPrompts: {len(all_prompts)}")
    print("Configs: 4 (opus baseline + 3 persona experiments)")
    print()

    configs = {
        "baseline": "opus",
        "ensembles": ["persona-diverse", "reasoning-cross-vendor", "reasoning-with-personas"]
    }

    results = {
        "metadata": {
            "total_prompts": len(all_prompts),
            "configs": configs
        },
        "baseline": {},
        "ensembles": {}
    }

    # Run baseline
    print("Testing baseline (opus)...")
    print("-"*80)
    results['baseline']['opus'] = []

    for i, prompt_data in enumerate(all_prompts, 1):
        print(f"  [{i}/{len(all_prompts)}] {prompt_data['id']}...", end='', flush=True)
        result = await run_single_model("opus", prompt_data['prompt'])
        result.update({
            'prompt_id': prompt_data['id'],
            'category': prompt_data['category'],
            'prompt': prompt_data['prompt']
        })
        results['baseline']['opus'].append(result)
        print(" ✓")

    print("✓ Baseline complete\n")

    # Run ensembles
    for recipe_name in configs['ensembles']:
        print(f"Testing ensemble: {recipe_name}...")
        print("-"*80)
        results['ensembles'][recipe_name] = []

        for i, prompt_data in enumerate(all_prompts, 1):
            print(f"  [{i}/{len(all_prompts)}] {prompt_data['id']}...", end='', flush=True)
            try:
                result = await run_ensemble(recipe_name, prompt_data['prompt'])
                result.update({
                    'prompt_id': prompt_data['id'],
                    'category': prompt_data['category'],
                    'prompt': prompt_data['prompt']
                })
                results['ensembles'][recipe_name].append(result)
                print(f" ✓ (${result['cost']:.4f}, {result['latency_ms']:.0f}ms)")
            except Exception as e:
                print(f" ✗ ERROR: {e}")
                results['ensembles'][recipe_name].append({
                    'prompt_id': prompt_data['id'],
                    'error': str(e)
                })

        print(f"✓ {recipe_name} complete\n")

    # Judge scoring
    print("="*80)
    print("SCORING WITH JUDGE MODEL (Opus)")
    print("="*80)

    judge = QualityJudge(judge_model="opus")

    # Score baseline
    print("\nScoring opus baseline...")
    for result in results['baseline']['opus']:
        if 'response' in result:
            score = await judge.score_response(
                prompt=result['prompt'],
                response=result['response'],
                expected_answer=None
            )
            result['judge_score'] = {
                'correctness': score.correctness,
                'completeness': score.completeness,
                'clarity': score.clarity,
                'total': score.total,
                'justification': score.justification
            }
    print("✓ Opus scored")

    # Score ensembles
    for recipe_name in configs['ensembles']:
        print(f"\nScoring {recipe_name}...")
        for result in results['ensembles'][recipe_name]:
            if 'response' in result:
                score = await judge.score_response(
                    prompt=result['prompt'],
                    response=result['response'],
                    expected_answer=None
                )
                result['judge_score'] = {
                    'correctness': score.correctness,
                    'completeness': score.completeness,
                    'clarity': score.clarity,
                    'total': score.total,
                    'justification': score.justification
                }
        print(f"✓ {recipe_name} scored")

    # Save results
    output_file = "results/persona_experiment.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n✓ Results saved to {output_file}")

    # Calculate summary
    import numpy as np

    print("\n" + "="*80)
    print("EXPERIMENT SUMMARY")
    print("="*80)

    opus_scores = [r['judge_score']['total'] for r in results['baseline']['opus'] if 'judge_score' in r]
    print(f"\nOpus baseline:  {np.mean(opus_scores):.1f} ± {np.std(opus_scores):.1f}")

    for recipe_name in configs['ensembles']:
        scores = [r['judge_score']['total'] for r in results['ensembles'][recipe_name] if 'judge_score' in r]
        delta = np.mean(scores) - np.mean(opus_scores)
        print(f"{recipe_name:30s}  {np.mean(scores):.1f} ± {np.std(scores):.1f}  ({delta:+.1f})")

    print("="*80)

if __name__ == "__main__":
    import os
    if not os.environ.get('AWS_BEARER_TOKEN_BEDROCK'):
        print("❌ Error: AWS_BEARER_TOKEN_BEDROCK not set")
        sys.exit(1)

    asyncio.run(main())
