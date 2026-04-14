#!/usr/bin/env python3
"""
E5: Smart Routing Validation

Test the recommended alternative: Nova-lite/Haiku/Opus routing based on complexity.

The BLOG recommends smart routing as superior to ensembles, but it was never tested.
This validates that recommendation.

Routing logic:
- Simple prompts → Nova-lite ($0.00001)
- Medium prompts → Haiku ($0.00023)
- Complex prompts → Opus ($0.00225)

Estimated cost: ~$15
"""

import json
import sys
import os
from datetime import datetime
import time
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moa.config import ModelConfig
from moa.judge import QualityJudge

def classify_complexity(prompt_text, category):
    """
    Classify prompt complexity using a simple heuristic or LLM.

    For this test, we'll use Haiku to classify (cheap and fast).
    """
    haiku = ModelConfig.get_config('haiku')

    classifier_prompt = f"""Classify this prompt's complexity for an AI assistant.

Category: {category}
Prompt: {prompt_text}

Respond with ONLY one word:
- SIMPLE (factual recall, basic questions, straightforward tasks)
- MEDIUM (analysis, multi-step reasoning, moderate complexity)
- COMPLEX (deep reasoning, creative tasks, expert-level questions)

Classification:"""

    response = haiku.generate(classifier_prompt)
    classification = response['text'].strip().upper()

    # Map to model
    if 'SIMPLE' in classification:
        return 'nova-lite', response['cost']
    elif 'MEDIUM' in classification:
        return 'haiku', response['cost']
    else:
        return 'opus', response['cost']

async def run_smart_routing(prompts, num_runs, judge):
    """Run smart routing across multiple runs for statistics."""
    print(f"\n{'='*80}")
    print("SMART ROUTING VALIDATION")
    print(f"{'='*80}\n")

    all_results = []
    total_cost = 0
    classification_cost = 0

    for run_num in range(1, num_runs + 1):
        print(f"\n--- Run {run_num}/{num_runs} ---\n")

        run_results = []

        for i, prompt_data in enumerate(prompts, 1):
            prompt_id = prompt_data['id']
            category = prompt_data['category']
            prompt_text = prompt_data['prompt']

            print(f"[{i}/{len(prompts)}] {prompt_id}...", end=" ", flush=True)

            # Classify complexity
            selected_model, classify_cost = classify_complexity(prompt_text, category)
            classification_cost += classify_cost

            # Generate response with selected model
            model_config = ModelConfig.get_config(selected_model)
            response = model_config.generate(prompt_text)

            # Judge the response
            score = await judge.score_response(
                prompt=prompt_text,
                response=response['text'],
                expected_answer=None
            )

            run_results.append({
                'prompt_id': prompt_id,
                'category': category,
                'selected_model': selected_model,
                'response': response['text'],
                'cost': response['cost'] + classify_cost,
                'judge_score': {
                    'correctness': score.correctness,
                    'completeness': score.completeness,
                    'clarity': score.clarity,
                    'total': score.total,
                    'justification': score.justification
                },
                'run': run_num
            })

            total_cost += response['cost'] + classify_cost

            print(f"{selected_model:10s} Score: {score.total:.1f}")

            # Rate limit
            if i % 10 == 0:
                time.sleep(2)

        all_results.extend(run_results)

        # Run summary
        run_mean = sum(r['judge_score']['total'] for r in run_results) / len(run_results)
        run_cost = sum(r['cost'] for r in run_results)
        print(f"\nRun {run_num} mean: {run_mean:.1f}, cost: ${run_cost:.2f}")

    return all_results, total_cost, classification_cost

async def main():
    print("=" * 80)
    print("E5: SMART ROUTING VALIDATION")
    print("Testing the recommended alternative to ensembles")
    print("=" * 80)
    print()

    # Load prompts
    with open('benchmark/prompts.json') as f:
        data = json.load(f)
        prompts = data.get('prompts', data)

    print(f"Loaded {len(prompts)} prompts")
    print()

    num_runs = 3
    total_tests = len(prompts) * num_runs

    print(f"Total tests: {total_tests} ({len(prompts)} prompts × {num_runs} runs)")
    print(f"Estimated cost: ~$15")
    print(f"Estimated time: 1-2 hours")
    print()

    if '--yes' not in sys.argv:
        confirm = input("Proceed with smart routing validation? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return
    else:
        print("Auto-confirming (--yes flag provided)")

    print()

    # Initialize judge
    judge = QualityJudge(judge_model="opus")

    # Run smart routing
    results, total_cost, classification_cost = await run_smart_routing(prompts, num_runs, judge)

    print()
    print("=" * 80)
    print("SMART ROUTING VALIDATION COMPLETE")
    print("=" * 80)
    print(f"Total cost: ${total_cost:.2f}")
    print(f"  Classification cost: ${classification_cost:.2f}")
    print(f"  Inference cost: ${total_cost - classification_cost:.2f}")
    print()

    # Save results
    output_file = f"results/e5_smart_routing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, 'w') as f:
        json.dump({
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'num_prompts': len(prompts),
                'num_runs': num_runs,
                'total_cost': total_cost,
                'classification_cost': classification_cost
            },
            'results': results
        }, f, indent=2)

    print(f"Results saved to: {output_file}")
    print()

    # Analyze results
    print("=" * 80)
    print("SMART ROUTING ANALYSIS")
    print("=" * 80)
    print()

    # Calculate statistics across runs
    scores_by_run = {}
    for run_num in range(1, num_runs + 1):
        run_results = [r for r in results if r['run'] == run_num]
        scores = [r['judge_score']['total'] for r in run_results]
        scores_by_run[run_num] = sum(scores) / len(scores)

    mean_score = sum(scores_by_run.values()) / len(scores_by_run)
    variance = sum((s - mean_score) ** 2 for s in scores_by_run.values()) / len(scores_by_run)
    std_dev = variance ** 0.5

    print(f"Mean score across {num_runs} runs: {mean_score:.1f}")
    print(f"Standard deviation: {std_dev:.2f}")
    print(f"Runs: {', '.join(f'{s:.1f}' for s in scores_by_run.values())}")
    print()

    # Model distribution
    from collections import Counter
    model_counts = Counter(r['selected_model'] for r in results)

    print("Model selection distribution:")
    for model, count in sorted(model_counts.items()):
        pct = count / len(results) * 100
        print(f"  {model}: {count} ({pct:.1f}%)")

    print()

    # Cost comparison
    avg_cost_per_prompt = total_cost / len(results)

    print("Cost comparison:")
    print(f"  Smart routing: ${avg_cost_per_prompt:.5f} per prompt")
    print(f"  Opus baseline: ~$0.00225 per prompt")
    print(f"  Ensemble (3-layer): ~$0.00675 per prompt")
    print()

    # Compare to baselines
    print("Quality comparison:")
    print(f"  Smart routing: {mean_score:.1f}")
    print(f"  Opus baseline: 94.5 (from Phase 1)")
    print(f"  Ensembles: 93.1-94.0 (from Phase 1)")
    print()

    if mean_score >= 94.5:
        print("✅ Smart routing MATCHES or BEATS Opus at lower cost")
    elif mean_score >= 90:
        print("⚠️  Smart routing provides good quality with cost savings")
    else:
        print("❌ Smart routing underperforms baseline")

    print()
    print("=" * 80)

if __name__ == '__main__':
    asyncio.run(main())
