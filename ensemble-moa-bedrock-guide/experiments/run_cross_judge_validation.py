#!/usr/bin/env python3
"""
E1: Cross-Judge Validation

Re-score all 216 Phase 1 responses using Sonnet as judge (instead of Opus).
Tests if Opus self-bias affects rankings.

Phase 1 configs:
- Opus baseline (54 prompts)
- High-end reasoning (54 prompts)
- Mixed capability (54 prompts)
- Same-model-premium (54 prompts)
Total: 216 responses to re-judge

Estimated cost: ~$5
"""

import json
import boto3
import time
import sys
from pathlib import Path
from datetime import datetime

# Initialize Bedrock client
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

# Model configuration for Sonnet judge
SONNET_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
SONNET_INPUT_PRICE = 0.003 / 1000  # $3 per 1M input tokens
SONNET_OUTPUT_PRICE = 0.015 / 1000  # $15 per 1M output tokens

def call_sonnet_judge(prompt_text, response_text, category):
    """Call Sonnet to judge a response."""

    judge_prompt = f"""You are an expert evaluator assessing the quality of AI model responses.

**Prompt Category:** {category}

**Original Prompt:**
{prompt_text}

**Model Response to Evaluate:**
{response_text}

**Task:** Rate this response on three criteria:

1. **Correctness (0-40 points):** Is the answer factually accurate and logically sound?
2. **Completeness (0-30 points):** Does it fully address all parts of the question?
3. **Clarity (0-30 points):** Is it well-organized, clear, and easy to understand?

Provide your evaluation in this exact JSON format:
{{
  "correctness": <score 0-40>,
  "completeness": <score 0-30>,
  "clarity": <score 0-30>,
  "total": <sum of above>,
  "justification": "<1-2 sentence explanation>"
}}

Be objective and consistent across all responses."""

    try:
        response = bedrock.invoke_model(
            modelId=SONNET_MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "messages": [{
                    "role": "user",
                    "content": judge_prompt
                }],
                "temperature": 0.0
            })
        )

        response_body = json.loads(response['body'].read())
        judge_text = response_body['content'][0]['text']

        # Extract JSON from response
        import re
        json_match = re.search(r'\{[^{}]*\}', judge_text, re.DOTALL)
        if json_match:
            judge_scores = json.loads(json_match.group())
        else:
            # Fallback parsing
            raise ValueError("Could not extract JSON from judge response")

        # Calculate cost
        input_tokens = response_body['usage']['input_tokens']
        output_tokens = response_body['usage']['output_tokens']
        cost = (input_tokens * SONNET_INPUT_PRICE) + (output_tokens * SONNET_OUTPUT_PRICE)

        return {
            'scores': judge_scores,
            'cost': cost,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens
        }

    except Exception as e:
        print(f"  ⚠️  Judge error: {e}")
        return None

def load_phase1_responses():
    """Load all Phase 1 responses from premium_tier.json."""

    with open('results/premium_tier.json') as f:
        data = json.load(f)

    # Load prompts to get prompt text
    with open('benchmark/prompts.json') as f:
        prompts_data = json.load(f)
        prompts = prompts_data.get('prompts', prompts_data)
        prompt_lookup = {p['id']: p for p in prompts}

    responses_to_judge = []

    # Opus baseline (from single_models)
    if 'opus' in data['single_models']:
        for item in data['single_models']['opus']:
            prompt_id = item['prompt_id']
            prompt_data = prompt_lookup.get(prompt_id, {})

            responses_to_judge.append({
                'config': 'opus-baseline',
                'prompt_id': prompt_id,
                'prompt_text': prompt_data.get('prompt', ''),
                'category': item.get('category', 'unknown'),
                'response': item['response'],
                'opus_judge_score': item.get('judge_score', {})
            })

    # Ensembles
    configs_to_test = ['high-end-reasoning', 'mixed-capability', 'same-model-premium']

    for config in configs_to_test:
        if config in data['ensembles']:
            for item in data['ensembles'][config]:
                prompt_id = item['prompt_id']
                prompt_data = prompt_lookup.get(prompt_id, {})

                # Get the final response (aggregated)
                final_response = item.get('aggregated_response', item.get('response', ''))

                responses_to_judge.append({
                    'config': config,
                    'prompt_id': prompt_id,
                    'prompt_text': prompt_data.get('prompt', ''),
                    'category': item.get('category', 'unknown'),
                    'response': final_response,
                    'opus_judge_score': item.get('judge_score', {})
                })

    return responses_to_judge

def main():
    print("=" * 80)
    print("E1: CROSS-JUDGE VALIDATION")
    print("Re-scoring Phase 1 responses with Sonnet judge")
    print("=" * 80)
    print()

    # Load responses
    print("Loading Phase 1 responses...")
    responses = load_phase1_responses()
    print(f"  Loaded {len(responses)} responses across 4 configs")
    print()

    # Count by config
    from collections import Counter
    config_counts = Counter(r['config'] for r in responses)
    for config, count in sorted(config_counts.items()):
        print(f"  {config}: {count} responses")
    print()

    # Estimate cost
    est_cost = len(responses) * 0.025  # ~$0.025 per judge call
    print(f"Estimated cost: ${est_cost:.2f}")
    print()

    # Check for --yes flag
    if '--yes' not in sys.argv:
        confirm = input("Proceed with cross-judge validation? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return
        print()
    else:
        print("Auto-confirming (--yes flag provided)")
        print()
    print("Starting cross-judge validation...")
    print("-" * 80)

    # Re-judge all responses
    total_cost = 0
    failed = 0

    for i, resp in enumerate(responses, 1):
        config = resp['config']
        prompt_id = resp['prompt_id']

        print(f"[{i}/{len(responses)}] {config} / {prompt_id}", end=" ")

        result = call_sonnet_judge(
            resp['prompt_text'],
            resp['response'],
            resp['category']
        )

        if result:
            resp['sonnet_judge_score'] = result['scores']
            resp['sonnet_judge_cost'] = result['cost']
            total_cost += result['cost']
            print(f"✓ (Opus: {resp['opus_judge_score'].get('total', 0)}, Sonnet: {result['scores']['total']})")
        else:
            failed += 1
            print("✗ Failed")

        # Rate limit (avoid throttling)
        if i % 10 == 0:
            time.sleep(1)

    print()
    print("=" * 80)
    print("CROSS-JUDGE VALIDATION COMPLETE")
    print("=" * 80)
    print(f"Total responses judged: {len(responses) - failed}/{len(responses)}")
    print(f"Failed: {failed}")
    print(f"Total cost: ${total_cost:.2f}")
    print()

    # Save results
    output_file = f"results/cross_judge_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, 'w') as f:
        json.dump({
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'total_responses': len(responses),
                'failed': failed,
                'total_cost': total_cost,
                'judge_model': SONNET_MODEL_ID
            },
            'responses': responses
        }, f, indent=2)

    print(f"Results saved to: {output_file}")
    print()

    # Analyze differences
    print("=" * 80)
    print("SCORE COMPARISON ANALYSIS")
    print("=" * 80)
    print()

    # Calculate mean scores by config
    config_scores = {}
    for config in ['opus-baseline', 'high-end-reasoning', 'mixed-capability', 'same-model-premium']:
        config_responses = [r for r in responses if r['config'] == config and 'sonnet_judge_score' in r]

        if config_responses:
            opus_scores = [r['opus_judge_score']['total'] for r in config_responses]
            sonnet_scores = [r['sonnet_judge_score']['total'] for r in config_responses]

            opus_mean = sum(opus_scores) / len(opus_scores)
            sonnet_mean = sum(sonnet_scores) / len(sonnet_scores)

            config_scores[config] = {
                'opus_mean': opus_mean,
                'sonnet_mean': sonnet_mean,
                'diff': sonnet_mean - opus_mean,
                'n': len(config_responses)
            }

    # Print comparison table
    print("Mean Scores by Configuration:")
    print()
    print(f"{'Configuration':<25} {'Opus Judge':<12} {'Sonnet Judge':<12} {'Difference':<12}")
    print("-" * 65)

    for config, scores in sorted(config_scores.items()):
        diff_str = f"{scores['diff']:+.1f}"
        print(f"{config:<25} {scores['opus_mean']:>10.1f}  {scores['sonnet_mean']:>10.1f}  {diff_str:>10}")

    print()

    # Check if rankings change
    print("Ranking Comparison:")
    print()

    opus_ranking = sorted(config_scores.items(), key=lambda x: x[1]['opus_mean'], reverse=True)
    sonnet_ranking = sorted(config_scores.items(), key=lambda x: x[1]['sonnet_mean'], reverse=True)

    print("Opus Judge Ranking:")
    for i, (config, scores) in enumerate(opus_ranking, 1):
        print(f"  {i}. {config}: {scores['opus_mean']:.1f}")

    print()
    print("Sonnet Judge Ranking:")
    for i, (config, scores) in enumerate(sonnet_ranking, 1):
        print(f"  {i}. {config}: {scores['sonnet_mean']:.1f}")

    print()

    # Check if rankings match
    opus_order = [c for c, _ in opus_ranking]
    sonnet_order = [c for c, _ in sonnet_ranking]

    if opus_order == sonnet_order:
        print("✅ Rankings MATCH - No evidence of Opus self-bias")
    else:
        print("⚠️  Rankings DIFFER - Possible judge bias detected")
        print()
        print("Ranking differences:")
        for config in opus_order:
            opus_pos = opus_order.index(config) + 1
            sonnet_pos = sonnet_order.index(config) + 1
            if opus_pos != sonnet_pos:
                print(f"  {config}: Opus ranked #{opus_pos}, Sonnet ranked #{sonnet_pos}")

    print()
    print("=" * 80)

if __name__ == '__main__':
    main()
