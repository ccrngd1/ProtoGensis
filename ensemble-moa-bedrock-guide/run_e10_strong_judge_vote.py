#!/usr/bin/env python3
"""
E10: Strong-Judge Vote Ensemble

Test diverse proposers with OPUS as judge (not Haiku).
Fixes the Haiku bottleneck discovered in Phase 1.

Proposers: opus-fast, opus-thinking, sonnet-fast, sonnet-thinking, haiku-fast, haiku-thinking
Judge: Opus (strongest available)

Estimated cost: ~$20
"""

import json
import sys
import os
from datetime import datetime
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moa.config import ModelConfig

def load_prompts():
    """Load Custom-54 prompts."""
    with open('benchmark/prompts.json') as f:
        data = json.load(f)
        return data.get('prompts', data)

def run_vote_ensemble_opus_judge(prompts):
    """Run vote ensemble with Opus as judge."""
    print(f"\n{'='*80}")
    print("STRONG-JUDGE VOTE ENSEMBLE (Opus Judge)")
    print(f"{'='*80}\n")

    # Proposer models
    proposer_keys = ['opus', 'sonnet', 'haiku']  # Will use both fast/thinking modes

    results = []
    total_cost = 0

    for i, prompt_data in enumerate(prompts, 1):
        prompt_id = prompt_data['id']
        category = prompt_data['category']
        prompt_text = prompt_data['prompt']

        print(f"[{i}/{len(prompts)}] {prompt_id}...", end=" ", flush=True)

        # Generate proposer responses (6 models: opus/sonnet/haiku × fast/thinking)
        proposer_responses = []

        for model_key in proposer_keys:
            config = ModelConfig.get_config(model_key)

            # Fast mode
            response_fast = config.generate(prompt_text)
            proposer_responses.append({
                'model': f"{config.name} (Fast)",
                'model_key': f"{model_key}-fast",
                'text': response_fast['text'],
                'cost': response_fast['cost']
            })
            total_cost += response_fast['cost']

            # Thinking mode (if available)
            if model_key in ['opus', 'sonnet']:  # Only Opus and Sonnet have thinking modes
                response_thinking = config.generate(prompt_text, extended_thinking=True)
                proposer_responses.append({
                    'model': f"{config.name} (Thinking)",
                    'model_key': f"{model_key}-thinking",
                    'text': response_thinking['text'],
                    'cost': response_thinking['cost']
                })
                total_cost += response_thinking['cost']

        # Use Opus as judge to select best response
        opus_judge = ModelConfig.get_config('opus')

        judge_prompt = f"""You are an expert judge evaluating multiple AI responses to select the best one.

**Original Prompt:**
{prompt_text}

**Candidate Responses:**
"""
        for j, resp in enumerate(proposer_responses, 1):
            judge_prompt += f"\n**Response {j} ({resp['model']}):**\n{resp['text']}\n"

        judge_prompt += """
**Your Task:** Select the single best response by number (1-6). Consider:
- Correctness and accuracy
- Completeness
- Clarity and organization

Respond with ONLY the number of the best response (1-6)."""

        judge_response = opus_judge.generate(judge_prompt)
        total_cost += judge_response['cost']

        # Parse judge selection
        try:
            selected_idx = int(judge_response['text'].strip()) - 1
            if 0 <= selected_idx < len(proposer_responses):
                selected_response = proposer_responses[selected_idx]
            else:
                # Fallback to first response if invalid selection
                selected_response = proposer_responses[0]
        except:
            # Fallback
            selected_response = proposer_responses[0]

        # Judge the selected response for scoring
        from moa.judge import judge_response
        judge_score = judge_response(prompt_text, selected_response['text'], category, model_key='opus')

        results.append({
            'prompt_id': prompt_id,
            'category': category,
            'proposer_responses': [{'model': p['model'], 'text': p['text']} for p in proposer_responses],
            'selected_response': selected_response['text'],
            'selected_model': selected_response['model'],
            'cost': sum(p['cost'] for p in proposer_responses) + judge_response['cost'],
            'judge_score': judge_score
        })

        print(f"Score: {judge_score.get('total', 0)} (selected: {selected_response['model_key']})")

        # Rate limit
        if i % 3 == 0:
            time.sleep(3)

    return results, total_cost

def main():
    print("=" * 80)
    print("E10: STRONG-JUDGE VOTE ENSEMBLE")
    print("Testing vote ensemble with Opus judge (vs Haiku in Phase 1)")
    print("=" * 80)
    print()

    # Load prompts
    prompts = load_prompts()
    print(f"Loaded {len(prompts)} prompts")
    print()

    print("Proposers: Opus, Sonnet, Haiku (fast + thinking modes)")
    print("Judge: Opus (strongest available)")
    print()
    print(f"Total tests: {len(prompts)}")
    print(f"Estimated cost: ~$20")
    print(f"Estimated time: 1-2 hours")
    print()

    if '--yes' not in sys.argv:
        confirm = input("Proceed with strong-judge vote ensemble? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return
    else:
        print("Auto-confirming (--yes flag provided)")

    print()

    # Run vote ensemble with Opus judge
    results, total_cost = run_vote_ensemble_opus_judge(prompts)

    print()
    print("=" * 80)
    print("STRONG-JUDGE VOTE ENSEMBLE COMPLETE")
    print("=" * 80)
    print(f"Total cost: ${total_cost:.2f}")
    print()

    # Save results
    output_file = f"results/e10_strong_judge_vote_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, 'w') as f:
        json.dump({
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'num_prompts': len(prompts),
                'total_cost': total_cost,
                'judge_model': 'opus'
            },
            'results': results
        }, f, indent=2)

    print(f"Results saved to: {output_file}")
    print()

    # Analyze results
    print("=" * 80)
    print("STRONG-JUDGE ANALYSIS")
    print("=" * 80)
    print()

    scores = [r['judge_score']['total'] for r in results]
    mean_score = sum(scores) / len(scores)

    print(f"Strong-judge vote ensemble mean: {mean_score:.1f}")
    print()

    # Compare to Phase 1 weak-judge vote (if available)
    print("Comparison to Phase 1:")
    print("  Weak-judge vote (Haiku): ~72.7 (from ENSEMBLE_COMPARISON_RESULTS.md)")
    print(f"  Strong-judge vote (Opus): {mean_score:.1f}")
    print(f"  Difference: {mean_score - 72.7:+.1f}")
    print()

    if mean_score > 85:
        print("✅ Strong judge DRAMATICALLY improves ensemble performance")
    elif mean_score > 75:
        print("⚠️  Strong judge provides MODERATE improvement")
    else:
        print("❌ Strong judge does NOT fix ensemble failure")

    print()
    print("=" * 80)

if __name__ == '__main__':
    main()
