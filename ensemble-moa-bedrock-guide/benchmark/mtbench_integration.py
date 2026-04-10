#!/usr/bin/env python3
"""
MT-Bench integration for multi-turn conversation testing.

MT-Bench: 80 multi-turn questions across 8 categories
Each question has 2 turns that test conversation coherence and context tracking.
"""

import json
import requests
import asyncio
import sys
from pathlib import Path
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from moa.core import create_moa_from_recipe, MoA
from moa.models import BEDROCK_MODELS
from moa.judge import QualityJudge
from moa.bedrock_client import BedrockClient

MTBENCH_URL = "https://raw.githubusercontent.com/lm-sys/FastChat/main/fastchat/llm_judge/data/mt_bench/question.jsonl"

def fetch_mtbench_questions() -> List[Dict]:
    """
    Download MT-Bench questions from FastChat repo.

    Returns:
        List of 80 questions with 'turns' array
    """
    print("Fetching MT-Bench questions from FastChat repo...")
    response = requests.get(MTBENCH_URL)

    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch MT-Bench: HTTP {response.status_code}")

    questions = []
    for line in response.text.strip().split('\n'):
        if line.strip():
            questions.append(json.loads(line))

    print(f"✓ Loaded {len(questions)} MT-Bench questions")
    return questions


async def run_config(config_name: str, prompt: str) -> str:
    """
    Run a config (ensemble or single model) on a prompt.

    Args:
        config_name: Recipe name (e.g. 'ultra-cheap') or model key (e.g. 'opus')
        prompt: Input prompt

    Returns:
        Response text
    """
    # Check if it's a recipe name
    from moa.models import RECIPES

    if config_name in RECIPES:
        # Run as ensemble
        moa = create_moa_from_recipe(config_name)
        response = await moa.run(prompt)
        return response.final_response
    elif config_name in BEDROCK_MODELS:
        # Run as single model
        client = BedrockClient()
        model_info = BEDROCK_MODELS[config_name]
        result = await client.invoke_model(
            model_id=model_info.model_id,
            prompt=prompt,
            max_tokens=2048,
            temperature=0.7
        )
        return result['response']
    else:
        raise ValueError(f"Unknown config: {config_name}. Not a recipe or model key.")


async def run_mtbench_conversation(config_name: str, question: Dict) -> Dict:
    """
    Run multi-turn conversation.

    Args:
        config_name: Recipe name or model key
        question: MT-Bench question with 'turns' array

    Returns:
        Dict with turn_1 and turn_2 responses
    """
    question_id = question['question_id']
    category = question['category']

    # Turn 1
    print(f"  [{question_id}] Turn 1...", end='', flush=True)
    response_1 = await run_config(config_name, question['turns'][0])
    print(" ✓")

    # Turn 2 (with context from Turn 1)
    print(f"  [{question_id}] Turn 2...", end='', flush=True)
    context = f"""Previous conversation:

User: {question['turns'][0]}
Assistant: {response_1}

User: {question['turns'][1]}"""

    response_2 = await run_config(config_name, context)
    print(" ✓")

    return {
        'question_id': question_id,
        'category': category,
        'turn_1': {
            'prompt': question['turns'][0],
            'response': response_1
        },
        'turn_2': {
            'prompt': question['turns'][1],
            'response': response_2,
            'context': response_1
        }
    }


async def run_mtbench_suite(configs: List[str], output_file: str):
    """Run all configs on MT-Bench."""
    questions = fetch_mtbench_questions()

    results = {
        'metadata': {
            'benchmark': 'MT-Bench',
            'total_questions': len(questions),
            'configs_tested': configs,
            'judge_model': 'opus'
        },
        'results': {}
    }

    print(f"\n{'='*60}")
    print(f"RUNNING MT-BENCH")
    print(f"{'='*60}")
    print(f"Questions: {len(questions)}")
    print(f"Configs: {', '.join(configs)}")
    print(f"{'='*60}\n")

    for config_name in configs:
        print(f"\nTesting {config_name} on MT-Bench...")
        print("-"*60)
        config_results = []

        for i, question in enumerate(questions, 1):
            try:
                result = await run_mtbench_conversation(config_name, question)
                config_results.append(result)
                print(f"  [{i}/{len(questions)}] {question['question_id']} ({question['category']}) - Complete")
            except Exception as e:
                print(f"  [{i}/{len(questions)}] {question['question_id']} - ERROR: {e}")
                config_results.append({
                    'question_id': question['question_id'],
                    'category': question['category'],
                    'error': str(e)
                })

        results['results'][config_name] = config_results
        print(f"✓ Completed {config_name}")

    # Score with judge
    print(f"\n{'='*60}")
    print("SCORING RESPONSES WITH JUDGE MODEL (Opus)")
    print(f"{'='*60}\n")

    judge = QualityJudge(judge_model="opus")

    for config_name, config_results in results['results'].items():
        print(f"Scoring {config_name}...")

        successful_results = [r for r in config_results if 'error' not in r]

        for i, result in enumerate(successful_results, 1):
            # Score both turns
            for turn_name in ['turn_1', 'turn_2']:
                turn_data = result[turn_name]

                # MT-Bench has no reference answers, so pass None
                score = await judge.score_response(
                    prompt=turn_data['prompt'],
                    response=turn_data['response'],
                    expected_answer=None
                )

                turn_data['judge_score'] = {
                    'correctness': score.correctness,
                    'completeness': score.completeness,
                    'clarity': score.clarity,
                    'total': score.total,
                    'justification': score.justification
                }

            if i % 10 == 0:
                print(f"  Scored {i}/{len(successful_results)}")

        print(f"✓ Scored {config_name}")

    # Calculate summary statistics
    print(f"\n{'='*60}")
    print("CALCULATING SUMMARY STATISTICS")
    print(f"{'='*60}\n")

    results['summary'] = {}

    for config_name, config_results in results['results'].items():
        successful_results = [r for r in config_results if 'error' not in r]

        if not successful_results:
            print(f"⚠️  {config_name}: No successful results")
            continue

        # Aggregate scores across both turns
        all_scores = []
        for result in successful_results:
            if 'turn_1' in result and 'judge_score' in result['turn_1']:
                all_scores.append(result['turn_1']['judge_score']['total'])
            if 'turn_2' in result and 'judge_score' in result['turn_2']:
                all_scores.append(result['turn_2']['judge_score']['total'])

        # Per-category breakdown
        category_scores = {}
        for result in successful_results:
            category = result['category']
            if category not in category_scores:
                category_scores[category] = []

            if 'turn_1' in result and 'judge_score' in result['turn_1']:
                category_scores[category].append(result['turn_1']['judge_score']['total'])
            if 'turn_2' in result and 'judge_score' in result['turn_2']:
                category_scores[category].append(result['turn_2']['judge_score']['total'])

        import numpy as np

        results['summary'][config_name] = {
            'total_questions': len(successful_results),
            'total_turns': len(all_scores),
            'avg_quality': float(np.mean(all_scores)),
            'std_quality': float(np.std(all_scores)),
            'min_quality': float(np.min(all_scores)),
            'max_quality': float(np.max(all_scores)),
            'category_breakdown': {
                cat: {
                    'avg': float(np.mean(scores)),
                    'std': float(np.std(scores)),
                    'count': len(scores)
                }
                for cat, scores in category_scores.items()
            }
        }

    # Save results
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n✓ Results saved to {output_file}")

    # Print summary
    print(f"\n{'='*60}")
    print("MT-BENCH SUMMARY")
    print(f"{'='*60}\n")

    for config_name, summary in results['summary'].items():
        print(f"{config_name}:")
        print(f"  Quality: {summary['avg_quality']:.1f} ± {summary['std_quality']:.1f}")
        print(f"  Questions: {summary['total_questions']}")
        print(f"  Turns scored: {summary['total_turns']}")
        print()

    print(f"{'='*60}\n")

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python benchmark/mtbench_integration.py <config1> <config2> ...")
        print("\nExample:")
        print("  python benchmark/mtbench_integration.py ultra-cheap opus")
        print("\nAvailable configs:")
        print("  - ultra-cheap")
        print("  - code-generation")
        print("  - reasoning")
        print("  - same-model-baseline")
        print("  - high-end-reasoning")
        print("  - mixed-capability")
        print("  - same-model-premium")
        print("  - Baseline models: nova-lite, haiku, sonnet, opus")
        sys.exit(1)

    configs = sys.argv[1:]

    # Check for AWS token
    import os
    if not os.environ.get('AWS_BEARER_TOKEN_BEDROCK'):
        print("❌ Error: AWS_BEARER_TOKEN_BEDROCK environment variable not set")
        sys.exit(1)

    print(f"✓ AWS bearer token found")

    asyncio.run(run_mtbench_suite(
        configs=configs,
        output_file="results/mtbench_results.json"
    ))


if __name__ == "__main__":
    main()
