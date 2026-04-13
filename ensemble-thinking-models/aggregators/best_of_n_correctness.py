#!/usr/bin/env python3
"""
Best-of-N Aggregator with Correctness-Based Judging

Key difference from best_of_n.py:
- Original: Judge evaluates "quality" (clarity, completeness, explanation)
- This: Judge evaluates CORRECTNESS of the final answer

Tests the hypothesis: "Does best-of-N work if we judge correctness instead of quality?"
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
    """Result of best-of-N aggregation with correctness judging"""
    prompt_id: str
    model_key: str
    judge_key: str
    num_samples: int
    selected_answer: str
    selected_index: int  # Which candidate (1-N) was selected
    judge_reasoning: str
    final_answer_extracted: str  # Numerical answer extracted by judge
    all_answers: List[str]
    total_cost_usd: float
    avg_latency_ms: int


class CorrectnessBasedBestOfN:
    """Generates N samples and uses judge to pick most likely CORRECT answer"""

    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode

        if not mock_mode:
            try:
                self.client = BedrockClient()
                print("✓ Correctness-based Best-of-N aggregator initialized")
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
        Generate N samples from model, use judge to pick most likely CORRECT answer.

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
            BestOfNResult with judge-selected most likely correct answer
        """
        if self.mock_mode:
            # Mock: return fake judge selection
            return BestOfNResult(
                prompt_id="mock",
                model_key=model_key,
                judge_key=judge_key,
                num_samples=num_samples,
                selected_answer="Mock best answer (judge selected #3 as most correct)",
                selected_index=3,
                judge_reasoning="Mock reasoning: Answer #3 has correct calculations",
                final_answer_extracted="42",
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

        # Judge selects most likely correct answer
        print(f"Judge ({judge_key}) evaluating {num_samples} samples for CORRECTNESS...")
        selected_answer, selected_idx, reasoning, final_answer, judge_cost = self._judge_correctness(
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
            selected_index=selected_idx,
            judge_reasoning=reasoning,
            final_answer_extracted=final_answer,
            all_answers=samples,
            total_cost_usd=total_cost,
            avg_latency_ms=avg_latency
        )

    def _judge_correctness(
        self,
        judge_model_id: str,
        judge_key: str,
        original_prompt: str,
        candidates: List[str]
    ) -> tuple[str, int, str, str, float]:
        """
        Use judge model to select most likely CORRECT candidate.

        Returns:
            (selected_answer, selected_index, reasoning, final_answer, cost)
        """
        # Format candidates for judge
        candidates_text = ""
        for i, candidate in enumerate(candidates, 1):
            candidates_text += f"\n\n{'='*60}\n[CANDIDATE {i}]\n{'='*60}\n"
            candidates_text += candidate

        judge_prompt = f"""You are evaluating multiple solutions to select the one most likely to be CORRECT.

Original Question:
{original_prompt}

Candidate Solutions:
{candidates_text}

Your task: Determine which candidate has the CORRECT final answer.

Evaluation process:
1. For each candidate:
   - Extract the final numerical answer
   - Verify the calculations step-by-step
   - Check if the reasoning is sound
   - Identify any mathematical errors

2. Select the candidate with the CORRECT answer
   - If multiple candidates are correct, pick any of them
   - If all candidates appear wrong, pick the one closest to correct
   - Ignore explanation style or formatting

3. Provide verification reasoning
   - Explain which calculations you checked
   - Mention specific errors you found (if any)
   - State why the selected answer is most likely correct

Important:
- Focus ONLY on mathematical/logical correctness
- Verify calculations independently when possible
- Don't assume the most detailed explanation is correct
- The candidates may all agree but still be wrong - think independently

Format your response as:
SELECTED_CANDIDATE: [number 1-{len(candidates)}]
FINAL_ANSWER: [the numerical answer you're selecting]
REASONING: [2-3 sentences explaining your verification process and why this is most likely correct]"""

        try:
            judge_response, input_tokens, output_tokens, latency_ms = self.client.call_model(
                model_id=judge_model_id,
                prompt=judge_prompt,
                max_tokens=1000,
                temperature=0.3  # Lower temp for more deterministic evaluation
            )

            judge_cost = calculate_cost(judge_model_id, input_tokens, output_tokens)

            # Parse judge response
            best_idx = self._parse_selected_candidate(judge_response, len(candidates))
            final_answer = self._parse_final_answer(judge_response)
            reasoning = self._extract_reasoning(judge_response)

            selected_answer = candidates[best_idx]

            print(f"  Judge selected candidate {best_idx + 1}: {reasoning[:100]}...")

            return selected_answer, best_idx + 1, reasoning, final_answer, judge_cost

        except Exception as e:
            print(f"  Judge evaluation failed: {e}. Defaulting to first candidate.")
            return candidates[0], 1, f"Judge failed: {e}", "", 0.0

    def _parse_selected_candidate(self, response: str, num_candidates: int) -> int:
        """Extract selected candidate number from judge response (0-indexed)"""
        # Look for SELECTED_CANDIDATE: N
        match = re.search(r'SELECTED_CANDIDATE:\s*(\d+)', response, re.IGNORECASE)
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

    def _parse_final_answer(self, response: str) -> str:
        """Extract final answer from judge response"""
        match = re.search(r'FINAL_ANSWER:\s*([^\n]+)', response, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_reasoning(self, response: str) -> str:
        """Extract reasoning from judge response"""
        match = re.search(r'REASONING:\s*(.+)', response, re.IGNORECASE | re.DOTALL)
        if match:
            reasoning = match.group(1).strip()
            # Truncate at next section marker or end
            reasoning = reasoning.split('\n\n')[0]
            return reasoning[:500]  # Max 500 chars

        # Fallback: return first 200 chars of response
        return response[:200].strip()


def main():
    """CLI for best-of-N with correctness judging"""
    import argparse

    parser = argparse.ArgumentParser(description='Best-of-N with correctness-based judge selection')
    parser.add_argument('prompt_file', help='JSON file with prompts')
    parser.add_argument('--model', default='opus-fast', help='Model to sample from')
    parser.add_argument('--judge', default='opus-fast', help='Judge model')
    parser.add_argument('--samples', type=int, default=5, help='Number of samples')
    parser.add_argument('--temperature', type=float, default=0.7, help='Sampling temperature')
    parser.add_argument('--output', help='Output JSON file')
    parser.add_argument('--live', action='store_true', help='Use live API (default: mock)')

    args = parser.parse_args()

    print(f"\nBest-of-N with Correctness Judging:")
    print(f"  Model: {args.model}")
    print(f"  Judge: {args.judge}")
    print(f"  Samples: {args.samples}")
    print(f"  Mode: {'LIVE' if args.live else 'MOCK'}")
    print()

    aggregator = CorrectnessBasedBestOfN(mock_mode=not args.live)
    print("✓ Aggregator initialized")


if __name__ == "__main__":
    main()
