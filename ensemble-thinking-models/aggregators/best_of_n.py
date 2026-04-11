#!/usr/bin/env python3
"""
Best-of-N Aggregator with Judge Verifier

Generates N samples from the same model, then uses a strong judge model
to select the best response.

Key difference from self-consistency:
- Self-consistency: Majority vote (no judge needed)
- Best-of-N: Judge picks the single best response

Use case: When you want diversity but need expert evaluation rather than voting.
"""

import json
import sys
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import re

# Add parent directory to path to import ensemble_shared module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from ensemble_shared.bedrock_client import BedrockClient, calculate_cost


@dataclass
class BestOfNResult:
    """Result of best-of-N aggregation"""
    prompt_id: str
    model_key: str
    judge_key: str
    num_samples: int
    selected_answer: str
    judge_reasoning: str
    all_answers: List[str]
    total_cost_usd: float
    avg_latency_ms: int


class BestOfNAggregator:
    """Generates N samples and uses judge to pick best"""

    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode

        if not mock_mode:
            try:
                self.client = BedrockClient()
                print("✓ Best-of-N aggregator initialized")
            except Exception as e:
                raise ValueError(f"Could not initialize BedrockClient: {e}")
        else:
            self.client = None

    def aggregate(
        self,
        model_id: str,
        model_key: str,
        judge_model_id: str,
        judge_key: str,
        prompt_text: str,
        num_samples: int = 5,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        extended_thinking: bool = False,
        thinking_budget: int = 10000
    ) -> BestOfNResult:
        """
        Generate N samples from model, use judge to pick best.

        Args:
            model_id: Bedrock model ID for candidate generation
            model_key: Human-readable model name
            judge_model_id: Bedrock model ID for judge
            judge_key: Human-readable judge name
            prompt_text: The prompt to run
            num_samples: Number of samples to generate (default 5)
            temperature: Sampling temperature (>0 for diversity)
            max_tokens: Max output tokens
            extended_thinking: Use extended thinking mode
            thinking_budget: Thinking token budget

        Returns:
            BestOfNResult with judge-selected answer
        """
        if self.mock_mode:
            # Mock: return fake judge selection
            return BestOfNResult(
                prompt_id="mock",
                model_key=model_key,
                judge_key=judge_key,
                num_samples=num_samples,
                selected_answer="Mock best answer (judge selected #3)",
                judge_reasoning="Mock reasoning: Answer #3 has best clarity and correctness",
                all_answers=[f"Mock answer {i+1}" for i in range(num_samples)],
                total_cost_usd=0.0,
                avg_latency_ms=0
            )

        # Generate N samples
        print(f"Generating {num_samples} samples from {model_key}...")
        samples = []
        total_cost = 0.0
        total_latency = 0

        for i in range(num_samples):
            print(f"  Sample {i+1}/{num_samples}...", end='', flush=True)

            if extended_thinking:
                answer, input_tokens, output_tokens, latency_ms = self.client.call_model(
                    model_id=model_id,
                    prompt=prompt_text,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    thinking_budget=thinking_budget
                )
            else:
                answer, input_tokens, output_tokens, latency_ms = self.client.call_model(
                    model_id=model_id,
                    prompt=prompt_text,
                    max_tokens=max_tokens,
                    temperature=temperature
                )

            cost = calculate_cost(model_id, input_tokens, output_tokens)
            total_cost += cost
            total_latency += latency_ms

            samples.append(answer)
            print(f" {len(answer)} chars, ${cost:.4f}")

        avg_latency = total_latency // num_samples

        # Judge selects best
        print(f"Judge ({judge_key}) evaluating {num_samples} samples...")
        selected_answer, judge_reasoning, judge_cost = self._judge_best(
            judge_model_id,
            judge_key,
            prompt_text,
            samples
        )

        total_cost += judge_cost

        return BestOfNResult(
            prompt_id="",  # Caller should set this
            model_key=model_key,
            judge_key=judge_key,
            num_samples=num_samples,
            selected_answer=selected_answer,
            judge_reasoning=judge_reasoning,
            all_answers=samples,
            total_cost_usd=total_cost,
            avg_latency_ms=avg_latency
        )

    def _judge_best(
        self,
        judge_model_id: str,
        judge_key: str,
        original_prompt: str,
        candidates: List[str]
    ) -> tuple[str, str, float]:
        """
        Use judge model to select best candidate.

        Returns:
            (selected_answer, reasoning, cost)
        """
        # Format candidates for judge
        candidates_text = ""
        for i, candidate in enumerate(candidates, 1):
            candidates_text += f"\n\n{'='*60}\n[CANDIDATE {i}]\n{'='*60}\n"
            candidates_text += candidate

        judge_prompt = f"""You are evaluating multiple responses to select the best one.

Original Question:
{original_prompt}

Candidate Responses:
{candidates_text}

Your task:
1. Evaluate each candidate on:
   - Correctness: Is the answer factually accurate?
   - Completeness: Does it fully address the question?
   - Clarity: Is it well-explained and easy to understand?
   - Reasoning quality: Is the logic sound?

2. Select the SINGLE BEST candidate (1-{len(candidates)})

3. Provide brief reasoning for your choice

Format your response as:
BEST_CANDIDATE: [number 1-{len(candidates)}]
REASONING: [1-2 sentences explaining why this is best]"""

        try:
            judge_response, input_tokens, output_tokens, latency_ms = self.client.call_model(
                model_id=judge_model_id,
                prompt=judge_prompt,
                max_tokens=500,
                temperature=0.3  # Lower temp for more deterministic evaluation
            )

            judge_cost = calculate_cost(judge_model_id, input_tokens, output_tokens)

            # Parse judge response
            best_idx = self._parse_judge_response(judge_response, len(candidates))
            reasoning = self._extract_reasoning(judge_response)

            selected_answer = candidates[best_idx]

            print(f"  Judge selected candidate {best_idx + 1}: {reasoning[:100]}...")

            return selected_answer, reasoning, judge_cost

        except Exception as e:
            print(f"  Judge evaluation failed: {e}. Defaulting to first candidate.")
            return candidates[0], f"Judge failed: {e}", 0.0

    def _parse_judge_response(self, response: str, num_candidates: int) -> int:
        """Extract selected candidate number from judge response."""
        # Look for BEST_CANDIDATE: N
        match = re.search(r'BEST_CANDIDATE:\s*(\d+)', response, re.IGNORECASE)
        if match:
            idx = int(match.group(1)) - 1  # Convert to 0-indexed
            if 0 <= idx < num_candidates:
                return idx

        # Fallback: look for any number 1-N
        for i in range(1, num_candidates + 1):
            if f"candidate {i}" in response.lower() or f"#{i}" in response:
                return i - 1

        # Default to first
        print(f"  Warning: Could not parse judge response, defaulting to candidate 1")
        return 0

    def _extract_reasoning(self, response: str) -> str:
        """Extract reasoning from judge response."""
        match = re.search(r'REASONING:\s*(.+)', response, re.IGNORECASE | re.DOTALL)
        if match:
            reasoning = match.group(1).strip()
            # Truncate at next section marker or end
            reasoning = reasoning.split('\n\n')[0]
            return reasoning[:500]  # Max 500 chars

        # Fallback: return first 200 chars of response
        return response[:200].strip()


def main():
    """CLI for best-of-N aggregation"""
    import argparse

    parser = argparse.ArgumentParser(description='Best-of-N with judge selection')
    parser.add_argument('prompt_file', help='JSON file with prompts')
    parser.add_argument('--model', default='opus-fast', help='Model to sample from')
    parser.add_argument('--judge', default='opus-fast', help='Judge model')
    parser.add_argument('--samples', type=int, default=5, help='Number of samples')
    parser.add_argument('--temperature', type=float, default=0.7, help='Sampling temperature')
    parser.add_argument('--output', help='Output JSON file')
    parser.add_argument('--live', action='store_true', help='Use live API (default: mock)')

    args = parser.parse_args()

    # Load prompts
    with open(args.prompt_file, 'r') as f:
        data = json.load(f)

    prompts = data.get('prompts', [])

    # Model configurations (match harness.py)
    model_configs = {
        'opus-fast': 'us.anthropic.claude-opus-4-6-v1',
        'sonnet-fast': 'us.anthropic.claude-sonnet-4-6',
        'haiku-fast': 'us.anthropic.claude-haiku-4-5-20251001-v1:0'
    }

    model_id = model_configs.get(args.model, model_configs['opus-fast'])
    judge_id = model_configs.get(args.judge, model_configs['opus-fast'])

    # Run aggregation
    aggregator = BestOfNAggregator(mock_mode=not args.live)

    results = []
    total_cost = 0.0

    print(f"\nBest-of-N Aggregation:")
    print(f"  Model: {args.model}")
    print(f"  Judge: {args.judge}")
    print(f"  Samples per prompt: {args.samples}")
    print(f"  Temperature: {args.temperature}")
    print(f"  Prompts: {len(prompts)}")
    print()

    for i, prompt in enumerate(prompts, 1):
        print(f"[{i}/{len(prompts)}] {prompt['id']}")

        result = aggregator.aggregate(
            model_id=model_id,
            model_key=args.model,
            judge_model_id=judge_id,
            judge_key=args.judge,
            prompt_text=prompt['text'],
            num_samples=args.samples,
            temperature=args.temperature
        )

        result.prompt_id = prompt['id']
        total_cost += result.total_cost_usd

        results.append(asdict(result))

        print(f"  Selected: {result.selected_answer[:100]}...")
        print(f"  Cost: ${result.total_cost_usd:.4f}")
        print()

    # Save results
    output_data = {
        'config': {
            'model': args.model,
            'judge': args.judge,
            'num_samples': args.samples,
            'temperature': args.temperature
        },
        'results': results,
        'total_cost_usd': total_cost
    }

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"Saved to {args.output}")

    print(f"\nTotal cost: ${total_cost:.2f}")


if __name__ == "__main__":
    main()
