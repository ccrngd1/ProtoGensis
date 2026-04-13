#!/usr/bin/env python3
"""
Vote Aggregator with Correctness-Based Judging

Key difference from vote.py:
- Original: Judge identifies which answers AGREE (semantic majority voting)
- This: Judge evaluates which answer is MOST LIKELY CORRECT

Tests the hypothesis: "Is the judge doing the wrong task?"
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
class VoteResult:
    """Result of correctness-based vote aggregation"""
    prompt_id: str
    strategy: str  # "correctness_judging"
    selected_answer: str
    selected_model: str
    judge_reasoning: str
    final_answer_extracted: str  # Numerical answer extracted by judge
    judge_cost_usd: float
    judge_latency_ms: int


class CorrectnessVoteAggregator:
    """Aggregates model responses via correctness-based judging"""

    def __init__(self, mock_mode: bool = True, judge_model: str = "opus-fast"):
        self.mock_mode = mock_mode
        self.judge_model = judge_model

        if not mock_mode:
            try:
                self.client = BedrockClient()
                print(f"✓ Correctness-based vote aggregator ({judge_model} judge) initialized")
            except ValueError as e:
                print(f"ERROR: {e}")
                raise
        else:
            self.client = None

    def aggregate(self, responses: Dict[str, Dict[str, Any]], prompt: Dict[str, Any]) -> VoteResult:
        """
        Use judge to evaluate which response is MOST LIKELY CORRECT.

        Args:
            responses: Dict of {model_key: {answer, cost_usd, latency_ms}}
            prompt: Dict with {id, text, ground_truth (optional)}

        Returns:
            VoteResult with judge's selection
        """
        if self.mock_mode:
            return self._mock_correctness_judge(responses, prompt)

        return self._correctness_judge(responses, prompt)

    def _correctness_judge(self, responses: Dict[str, Dict[str, Any]],
                          prompt: Dict[str, Any]) -> VoteResult:
        """Use LLM judge to evaluate correctness of responses"""

        # Format responses for evaluation
        responses_text = ""
        valid_models = []

        for model_key, response in responses.items():
            if response.get('error'):
                continue
            valid_models.append(model_key)

            responses_text += f"\n\n{'='*60}\n[{model_key.upper()}]\n{'='*60}\n"
            responses_text += response['answer']

        judge_prompt = f"""You are evaluating multiple mathematical solutions to determine which is MOST LIKELY CORRECT.

Original Question:
{prompt['text']}

Proposed Solutions:
{responses_text}

Your task: Select the solution that is most likely to give the CORRECT final answer.

Evaluation criteria:
1. **Mathematical accuracy** - Are the calculations correct?
2. **Logical reasoning** - Is the approach sound?
3. **Completeness** - Does it address all parts of the question?
4. **Final answer** - Is the numerical answer reasonable?

Important:
- Ignore writing style, formatting, or explanation length
- Focus ONLY on correctness of the final answer
- You may see multiple correct solutions - if so, pick any of them
- If all solutions appear wrong, pick the one closest to correct
- VERIFY calculations step-by-step when possible
- The models may disagree - your job is to determine which is RIGHT, not which has majority

Format your response as:
SELECTED: [model name with the correct/best answer, e.g., OPUS-FAST or SONNET-FAST]
FINAL_ANSWER: [the numerical answer you're selecting]
REASONING: [2-3 sentences explaining why this solution is most likely correct, mentioning specific calculation checks]"""

        # Map judge model key to Bedrock model ID
        judge_model_ids = {
            "haiku-fast": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
            "sonnet-fast": "us.anthropic.claude-sonnet-4-6",
            "opus-fast": "us.anthropic.claude-opus-4-6-v1"
        }
        judge_model_id = judge_model_ids.get(self.judge_model, judge_model_ids["opus-fast"])

        try:
            judge_response, input_tokens, output_tokens, latency_ms = self.client.call_model(
                model_id=judge_model_id,
                prompt=judge_prompt,
                max_tokens=1000,
                temperature=0.3  # Lower temp for more deterministic evaluation
            )

            judge_cost = calculate_cost(judge_model_id, input_tokens, output_tokens)

            # Parse judge response
            selected_model = self._parse_selected_model(judge_response, valid_models)
            final_answer = self._parse_final_answer(judge_response)
            reasoning = self._parse_reasoning(judge_response)

            # Get the selected answer
            selected_answer = responses[selected_model]['answer']

            return VoteResult(
                prompt_id=prompt['id'],
                strategy="correctness_judging",
                selected_answer=selected_answer,
                selected_model=selected_model,
                judge_reasoning=reasoning,
                final_answer_extracted=final_answer,
                judge_cost_usd=judge_cost,
                judge_latency_ms=latency_ms
            )

        except Exception as e:
            print(f"  ERROR in correctness judge: {e}")
            # Fallback to first valid model
            fallback_model = valid_models[0] if valid_models else "opus-fast"
            return VoteResult(
                prompt_id=prompt['id'],
                strategy="correctness_judging",
                selected_answer=responses[fallback_model]['answer'],
                selected_model=fallback_model,
                judge_reasoning=f"Judge failed: {e}. Defaulted to {fallback_model}.",
                final_answer_extracted="",
                judge_cost_usd=0.0,
                judge_latency_ms=0
            )

    def _parse_selected_model(self, response: str, valid_models: List[str]) -> str:
        """Extract selected model from judge response"""
        # Look for SELECTED: MODEL_NAME
        match = re.search(r'SELECTED:\s*([A-Z\-]+)', response, re.IGNORECASE)
        if match:
            selected = match.group(1).lower()
            # Match against valid models
            for model in valid_models:
                if model.replace('-', '').replace('_', '') in selected.replace('-', '').replace('_', ''):
                    return model

        # Fallback: look for model names in text
        for model in valid_models:
            if model.upper() in response.upper():
                return model

        # Default to first model
        return valid_models[0] if valid_models else "opus-fast"

    def _parse_final_answer(self, response: str) -> str:
        """Extract final numerical answer from judge response"""
        match = re.search(r'FINAL_ANSWER:\s*([^\n]+)', response, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    def _parse_reasoning(self, response: str) -> str:
        """Extract reasoning from judge response"""
        match = re.search(r'REASONING:\s*(.+)', response, re.IGNORECASE | re.DOTALL)
        if match:
            reasoning = match.group(1).strip()
            # Truncate at next section or after reasonable length
            reasoning = reasoning.split('\n\n')[0]
            return reasoning[:500]
        return response[:200]

    def _mock_correctness_judge(self, responses: Dict[str, Dict[str, Any]],
                                prompt: Dict[str, Any]) -> VoteResult:
        """Mock correctness judging for testing"""
        return VoteResult(
            prompt_id=prompt['id'],
            strategy="correctness_judging",
            selected_answer="Mock answer selected by correctness evaluation",
            selected_model="opus-fast",
            judge_reasoning="Mock: Selected based on calculation verification",
            final_answer_extracted="42",
            judge_cost_usd=0.0,
            judge_latency_ms=0
        )


def main():
    """CLI for testing correctness-based voting"""
    import argparse

    parser = argparse.ArgumentParser(description='Correctness-based vote aggregation')
    parser.add_argument('prompt_file', help='JSON file with prompts')
    parser.add_argument('--judge', default='opus-fast', help='Judge model')
    parser.add_argument('--output', help='Output JSON file')
    parser.add_argument('--live', action='store_true', help='Use live API (default: mock)')

    args = parser.parse_args()

    print(f"\nCorrectness-Based Vote Aggregation:")
    print(f"  Judge: {args.judge}")
    print(f"  Mode: {'LIVE' if args.live else 'MOCK'}")
    print()

    # This would be used in a full experiment runner
    # For now, just demonstrate the aggregator initialization
    aggregator = CorrectnessVoteAggregator(mock_mode=not args.live, judge_model=args.judge)
    print("✓ Aggregator initialized")


if __name__ == "__main__":
    main()
