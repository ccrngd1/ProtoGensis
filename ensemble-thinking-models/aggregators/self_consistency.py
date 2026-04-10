#!/usr/bin/env python3
"""
Self-Consistency Ensemble

Runs the SAME model multiple times and takes majority vote on answers.
No judge model needed - the model verifies itself through multiple samples.

Based on: Wang et al. (2023) "Self-Consistency Improves Chain of Thought Reasoning in Language Models"

Key advantage over vote.py: No weak judge bottleneck. The model is its own verifier.
"""

import json
import sys
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from collections import Counter
import re

# Add parent directory to path to import ensemble_shared module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from ensemble_shared.bedrock_client import BedrockClient, calculate_cost


@dataclass
class SelfConsistencyResult:
    """Result of self-consistency aggregation"""
    prompt_id: str
    model_key: str
    num_samples: int
    selected_answer: str
    vote_counts: Dict[str, int]  # Answer -> count
    agreement_rate: float  # 0-1, how many agreed with majority
    all_answers: List[str]  # All raw answers
    total_cost_usd: float
    avg_latency_ms: int


class SelfConsistencyAggregator:
    """Runs same model multiple times and takes majority vote"""

    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode

        if not mock_mode:
            try:
                self.client = BedrockClient()
                print("✓ Self-consistency aggregator initialized")
            except Exception as e:
                raise ValueError(f"Could not initialize BedrockClient: {e}")
        else:
            self.client = None

    def _extract_answer_key(self, answer: str) -> str:
        """
        Extract the core answer for comparison.

        For multiple choice: extract letter (check FIRST to avoid extracting numbers from reasoning)
        For numeric answers: extract numbers
        For text: normalize and take key phrases
        """
        if not answer:
            return ""

        # Try to extract multiple choice letter FIRST (for MMLU, GPQA)
        # Must check before numbers to avoid extracting "1,2,3,4" from reasoning
        mc_match = re.search(r'\b([A-D])\b', answer.upper())
        if mc_match:
            return mc_match.group(1)

        # Try to extract number (for GSM8K, numeric answers)
        numbers = re.findall(r'-?\d+(?:,\d+)*(?:\.\d+)?', answer)
        if numbers:
            # Use last number as answer key
            return numbers[-1].replace(',', '')

        # Fallback: normalize text and take first 50 chars
        normalized = answer.lower().strip()
        # Remove common filler words
        normalized = re.sub(r'\b(the|a|an|is|are|was|were|to|of|and|or|but)\b', '', normalized)
        return normalized[:50]

    def aggregate(
        self,
        model_id: str,
        model_key: str,
        prompt_text: str,
        num_samples: int = 5,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        extended_thinking: bool = False,
        thinking_budget: int = 10000
    ) -> SelfConsistencyResult:
        """
        Run same model multiple times and take majority vote.

        Args:
            model_id: Bedrock model ID
            model_key: Human-readable model name
            prompt_text: The prompt to run
            num_samples: Number of samples to generate (default 5)
            temperature: Sampling temperature (>0 for diversity)
            max_tokens: Max output tokens
            extended_thinking: Use extended thinking mode
            thinking_budget: Thinking token budget

        Returns:
            SelfConsistencyResult with majority answer
        """
        if self.mock_mode:
            # Mock: return fake majority vote
            return SelfConsistencyResult(
                prompt_id="mock",
                model_key=model_key,
                num_samples=num_samples,
                selected_answer="Mock answer (3/5 agree)",
                vote_counts={"Mock answer": 3, "Alternative": 2},
                agreement_rate=0.6,
                all_answers=["Mock answer"] * 3 + ["Alternative"] * 2,
                total_cost_usd=0.0,
                avg_latency_ms=0
            )

        # Run model multiple times
        answers = []
        total_cost = 0.0
        total_latency = 0

        print(f"  Running {num_samples} samples...")
        for i in range(num_samples):
            try:
                response, input_tokens, output_tokens, latency_ms = self.client.call_model(
                    model_id=model_id,
                    prompt=prompt_text,
                    max_tokens=max_tokens,
                    temperature=temperature if not extended_thinking else None,
                    extended_thinking=extended_thinking,
                    thinking_budget=thinking_budget
                )

                answers.append(response)
                total_latency += latency_ms

                # Calculate cost (will vary by model)
                if extended_thinking:
                    # Extended thinking uses different pricing
                    cost = calculate_cost(model_id, input_tokens, output_tokens, extended_thinking=True)
                else:
                    cost = calculate_cost(model_id, input_tokens, output_tokens)

                total_cost += cost

                print(f"    Sample {i+1}/{num_samples}: {latency_ms}ms, ${cost:.4f}")

            except Exception as e:
                print(f"    Sample {i+1}/{num_samples}: ERROR - {e}")
                answers.append(f"ERROR: {e}")

        # Extract answer keys for voting
        answer_keys = [self._extract_answer_key(ans) for ans in answers]

        # Count votes
        vote_counts = Counter(answer_keys)

        # Get majority answer
        if vote_counts:
            majority_key, majority_count = vote_counts.most_common(1)[0]
            # Find first full answer that matches majority key
            majority_answer = answers[answer_keys.index(majority_key)]
            agreement_rate = majority_count / len(answers)
        else:
            majority_answer = "No valid answers"
            agreement_rate = 0.0

        return SelfConsistencyResult(
            prompt_id="",  # Will be set by caller
            model_key=model_key,
            num_samples=num_samples,
            selected_answer=majority_answer,
            vote_counts=dict(vote_counts),
            agreement_rate=agreement_rate,
            all_answers=answers,
            total_cost_usd=total_cost,
            avg_latency_ms=int(total_latency / num_samples) if answers else 0
        )


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Self-Consistency Ensemble Aggregator')
    parser.add_argument('prompts_file', help='Path to prompts JSON file')
    parser.add_argument('--model', required=True,
                       help='Model to use (e.g., opus-fast, sonnet-thinking)')
    parser.add_argument('--samples', type=int, default=5,
                       help='Number of samples per prompt (default: 5)')
    parser.add_argument('--output', default='results/self_consistency_results.json',
                       help='Output file for results')
    parser.add_argument('--live', action='store_true',
                       help='Use live API calls (default: mock mode)')
    parser.add_argument('--max-prompts', type=int, default=None,
                       help='Limit number of prompts to process (for testing)')

    args = parser.parse_args()

    # Load prompts
    with open(args.prompts_file, 'r') as f:
        prompts_data = json.load(f)

    prompts = prompts_data['prompts']
    if args.max_prompts:
        prompts = prompts[:args.max_prompts]

    # Map model key to model ID and config
    model_configs = {
        'opus-fast': {
            'model_id': 'us.anthropic.claude-opus-4-6-v1',
            'extended_thinking': False,
            'max_tokens': 4096
        },
        'opus-thinking': {
            'model_id': 'us.anthropic.claude-opus-4-6-v1',
            'extended_thinking': True,
            'max_tokens': 16000,
            'thinking_budget': 10000
        },
        'sonnet-fast': {
            'model_id': 'us.anthropic.claude-sonnet-4-6-v1',
            'extended_thinking': False,
            'max_tokens': 4096
        },
        'sonnet-thinking': {
            'model_id': 'us.anthropic.claude-sonnet-4-6-v1',
            'extended_thinking': True,
            'max_tokens': 16000,
            'thinking_budget': 5000
        },
        'haiku-fast': {
            'model_id': 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
            'extended_thinking': False,
            'max_tokens': 4096
        },
        'haiku-thinking': {
            'model_id': 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
            'extended_thinking': True,
            'max_tokens': 16000,
            'thinking_budget': 2000
        }
    }

    if args.model not in model_configs:
        print(f"Error: Unknown model '{args.model}'")
        print(f"Available: {', '.join(model_configs.keys())}")
        sys.exit(1)

    config = model_configs[args.model]

    # Initialize aggregator
    mock_mode = not args.live
    aggregator = SelfConsistencyAggregator(mock_mode=mock_mode)

    mode_desc = "LIVE" if args.live else "MOCK"
    print(f"Running self-consistency in {mode_desc} mode...")
    print(f"Model: {args.model}")
    print(f"Samples per prompt: {args.samples}")
    print(f"Processing {len(prompts)} prompts")
    print()

    # Process each prompt
    results = []
    total_cost = 0.0

    for i, prompt in enumerate(prompts, 1):
        prompt_id = prompt['id']
        prompt_text = prompt.get('text', prompt.get('question', ''))

        print(f"{'='*80}")
        print(f"Prompt {i}/{len(prompts)}: {prompt_id}")
        print(f"{'='*80}")

        result = aggregator.aggregate(
            model_id=config['model_id'],
            model_key=args.model,
            prompt_text=prompt_text,
            num_samples=args.samples,
            temperature=0.7,
            max_tokens=config['max_tokens'],
            extended_thinking=config['extended_thinking'],
            thinking_budget=config.get('thinking_budget', 10000)
        )

        result.prompt_id = prompt_id
        results.append(asdict(result))
        total_cost += result.total_cost_usd

        print(f"  Selected: {result.selected_answer[:80]}...")
        print(f"  Agreement: {result.agreement_rate:.1%} ({dict(result.vote_counts)})")
        print(f"  Cost: ${result.total_cost_usd:.4f}")
        print()

    # Save results
    output_data = {
        'model': args.model,
        'num_samples': args.samples,
        'total_prompts': len(prompts),
        'total_cost_usd': total_cost,
        'results': results
    }

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"{'='*80}")
    print(f"✓ Results saved to {args.output}")
    print(f"Total cost: ${total_cost:.4f}")
    print(f"Average agreement rate: {sum(r['agreement_rate'] for r in results) / len(results):.1%}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
