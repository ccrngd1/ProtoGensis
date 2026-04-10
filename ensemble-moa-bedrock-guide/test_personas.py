#!/usr/bin/env python3
"""
Quick test: Do personas create response diversity?

Tests same model (Opus) with different personas to see if responses differ.
"""

import asyncio
import json
import sys
from pathlib import Path
from difflib import SequenceMatcher

sys.path.insert(0, str(Path(__file__).parent))

from moa.bedrock_client import BedrockClient
from moa.models import BEDROCK_MODELS


PERSONAS = {
    "baseline": None,  # No persona

    "critical-analyst": """You are a critical analyst. When answering questions:
- Focus on identifying logical flaws and inconsistencies
- Question assumptions and point out missing information
- Be precise, rigorous, and cautious
- Favor well-justified answers over speculation
- Acknowledge uncertainty when appropriate""",

    "creative-generalist": """You are a creative generalist. When answering questions:
- Provide comprehensive, complete answers
- Consider multiple perspectives and approaches
- Make connections between different concepts
- Be expansive and thorough in your response
- Favor breadth and exploring possibilities""",

    "domain-expert": """You are a domain expert. When answering questions:
- Emphasize technical accuracy and precision
- Draw on deep domain knowledge and best practices
- Focus on practical implementation details
- Favor depth and specificity over generality
- Use precise terminology and standards"""
}


async def test_persona(model_key: str, prompt: str, persona_name: str, persona_text: str | None):
    """Test a model with a specific persona."""
    client = BedrockClient()
    model_info = BEDROCK_MODELS[model_key]

    # Build full prompt
    if persona_text:
        full_prompt = f"{persona_text}\n\n{prompt}"
    else:
        full_prompt = prompt

    print(f"  Testing: {persona_name}...", end='', flush=True)

    result = await client.invoke_model(
        model_id=model_info.model_id,
        prompt=full_prompt,
        max_tokens=2048,
        temperature=0.7
    )

    print(f" ✓ ({len(result['response'])} chars)")

    return {
        'persona': persona_name,
        'response': result['response'],
        'length': len(result['response']),
        'input_tokens': result['input_tokens'],
        'output_tokens': result['output_tokens']
    }


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two texts (0-1 scale)."""
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


async def test_prompt_with_personas(prompt_id: str, prompt_text: str, model_key: str = "opus"):
    """Test a single prompt with all personas."""
    print(f"\n{'='*80}")
    print(f"Testing prompt: {prompt_id}")
    print(f"{'='*80}")
    print(f"Prompt: {prompt_text[:150]}...")
    print()

    results = []

    for persona_name, persona_text in PERSONAS.items():
        result = await test_persona(model_key, prompt_text, persona_name, persona_text)
        results.append(result)

    return {
        'prompt_id': prompt_id,
        'prompt': prompt_text,
        'model': model_key,
        'persona_results': results
    }


def analyze_diversity(test_results):
    """Analyze how diverse the persona responses are."""
    print(f"\n{'='*80}")
    print("DIVERSITY ANALYSIS")
    print(f"{'='*80}\n")

    for test in test_results:
        print(f"Prompt: {test['prompt_id']}")
        print("-"*80)

        responses = test['persona_results']

        # Show response lengths
        print("\nResponse Lengths:")
        for r in responses:
            print(f"  {r['persona']:20s} {r['length']:5d} chars")

        # Calculate pairwise similarities
        print("\nPairwise Similarity (0=completely different, 1=identical):")
        personas = [r['persona'] for r in responses]

        similarities = []
        for i, r1 in enumerate(responses):
            for j, r2 in enumerate(responses):
                if i < j:
                    sim = calculate_similarity(r1['response'], r2['response'])
                    similarities.append(sim)
                    print(f"  {r1['persona']:20s} vs {r2['persona']:20s} {sim:.3f}")

        avg_similarity = sum(similarities) / len(similarities) if similarities else 0
        print(f"\nAverage Similarity: {avg_similarity:.3f}")

        if avg_similarity > 0.80:
            print("❌ HIGH similarity - personas don't create much diversity")
        elif avg_similarity > 0.60:
            print("⚠️  MODERATE similarity - some diversity but limited")
        else:
            print("✅ LOW similarity - personas create meaningful diversity")

        print()

    # Overall assessment
    all_similarities = []
    for test in test_results:
        responses = test['persona_results']
        for i, r1 in enumerate(responses):
            for j, r2 in enumerate(responses):
                if i < j:
                    sim = calculate_similarity(r1['response'], r2['response'])
                    all_similarities.append(sim)

    overall_avg = sum(all_similarities) / len(all_similarities) if all_similarities else 0

    print("="*80)
    print("OVERALL ASSESSMENT")
    print("="*80)
    print(f"Average similarity across all prompts: {overall_avg:.3f}")
    print()

    if overall_avg > 0.70:
        print("❌ VERDICT: Personas do NOT create sufficient diversity")
        print("   Responses are too similar (>70% match)")
        print("   Recommendation: Don't proceed with full persona experiment")
        return False
    else:
        print("✅ VERDICT: Personas DO create meaningful diversity")
        print(f"   Responses differ by {(1-overall_avg)*100:.1f}%")
        print("   Recommendation: Proceed with full persona experiment")
        return True


def show_example_responses(test_results):
    """Show example responses for manual inspection."""
    print(f"\n{'='*80}")
    print("EXAMPLE RESPONSES (First Prompt)")
    print(f"{'='*80}\n")

    test = test_results[0]
    print(f"Prompt: {test['prompt'][:200]}...\n")

    for result in test['persona_results']:
        print("-"*80)
        print(f"{result['persona'].upper()}")
        print("-"*80)
        print(result['response'][:400])
        if len(result['response']) > 400:
            print(f"... [truncated, {len(result['response']) - 400} more chars]")
        print()


async def main():
    """Run persona diversity test."""
    # Load test prompts
    with open('benchmark/prompts.json') as f:
        data = json.load(f)
        all_prompts = data['prompts']

    # Select diverse test prompts
    test_prompt_ids = [
        'adversarial-2',  # Hallucination test (GDP of Lesotho)
        'reasoning-1',    # Logic puzzle
        'code-3'          # Code generation
    ]

    test_prompts = {p['id']: p['prompt'] for p in all_prompts if p['id'] in test_prompt_ids}

    print("="*80)
    print("PERSONA DIVERSITY TEST")
    print("="*80)
    print(f"\nTesting {len(test_prompts)} prompts with {len(PERSONAS)} personas each")
    print(f"Model: Opus")
    print(f"Cost estimate: ~${0.08 * len(test_prompts) * len(PERSONAS):.2f}")
    print()

    # Run tests
    results = []
    for prompt_id in test_prompt_ids:
        if prompt_id in test_prompts:
            result = await test_prompt_with_personas(prompt_id, test_prompts[prompt_id])
            results.append(result)

    # Save results
    output_file = 'results/persona_test.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Results saved to {output_file}")

    # Analyze diversity
    personas_work = analyze_diversity(results)

    # Show examples
    show_example_responses(results)

    # Final recommendation
    print("="*80)
    print("NEXT STEPS")
    print("="*80)
    if personas_work:
        print("\n✅ Personas create diversity - proceed with full experiment:")
        print("   python benchmark/run.py \\")
        print("     --recipes persona-diverse reasoning-with-personas \\")
        print("     --output results/reasoning_experiment.json")
        print(f"\n   Cost: ~$50, Time: 3 hours")
    else:
        print("\n❌ Personas don't create enough diversity - stop here")
        print("   AWS Bedrock cannot replicate Wang et al.'s cross-vendor diversity")
        print("   Recommendation: Use standalone models instead of ensembles")
    print("="*80)


if __name__ == "__main__":
    import os
    if not os.environ.get('AWS_BEARER_TOKEN_BEDROCK'):
        print("❌ Error: AWS_BEARER_TOKEN_BEDROCK environment variable not set")
        sys.exit(1)

    asyncio.run(main())
