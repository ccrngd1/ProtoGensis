#!/usr/bin/env python3
"""
Two-Stage Aggregator

Stage 1: Agreement-based grouping (semantic majority voting)
Stage 2: Correctness evaluation among the majority group

Hypothesis: Combining both approaches might work better than either alone.
- Stage 1 filters out outliers via agreement
- Stage 2 evaluates correctness among the consensus group
"""

import json
import sys
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import re

# Add parent directory to path to import ensemble_shared module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from ensemble_shared.bedrock_client import BedrockClient, calculate_cost


@dataclass
class TwoStageResult:
    """Result of two-stage aggregation"""
    prompt_id: str
    strategy: str  # "two_stage_judging"
    selected_answer: str
    selected_model: str

    # Stage 1: Agreement grouping
    stage1_groups: Dict[str, List[str]]  # {group_name: [model_names]}
    stage1_majority: str  # Which group was the majority
    stage1_reasoning: str
    stage1_cost_usd: float

    # Stage 2: Correctness evaluation
    stage2_evaluated: List[str]  # Models evaluated in stage 2
    stage2_reasoning: str
    stage2_cost_usd: float

    total_cost_usd: float
    total_latency_ms: int


class TwoStageAggregator:
    """Two-stage aggregation: agreement first, then correctness"""

    def __init__(self, mock_mode: bool = True, judge_model: str = "opus-fast"):
        self.mock_mode = mock_mode
        self.judge_model = judge_model

        if not mock_mode:
            try:
                self.client = BedrockClient()
                print(f"✓ Two-stage aggregator ({judge_model} judge) initialized")
            except ValueError as e:
                print(f"ERROR: {e}")
                raise
        else:
            self.client = None

    def aggregate(self, responses: Dict[str, Dict[str, Any]], prompt: Dict[str, Any]) -> TwoStageResult:
        """
        Two-stage aggregation:
        1. Group responses by semantic agreement
        2. Evaluate correctness within the majority group

        Args:
            responses: Dict of {model_key: {answer, cost_usd, latency_ms}}
            prompt: Dict with {id, text, ground_truth (optional)}

        Returns:
            TwoStageResult with both stages' outputs
        """
        if self.mock_mode:
            return self._mock_two_stage(responses, prompt)

        # Stage 1: Group by agreement
        groups, majority_group, stage1_reasoning, stage1_cost, stage1_latency = self._stage1_agreement(
            responses, prompt
        )

        # Stage 2: Evaluate correctness within majority group
        selected_model, selected_answer, stage2_reasoning, stage2_cost, stage2_latency = self._stage2_correctness(
            responses, prompt, majority_group
        )

        return TwoStageResult(
            prompt_id=prompt['id'],
            strategy="two_stage_judging",
            selected_answer=selected_answer,
            selected_model=selected_model,
            stage1_groups=groups,
            stage1_majority=majority_group,
            stage1_reasoning=stage1_reasoning,
            stage1_cost_usd=stage1_cost,
            stage2_evaluated=majority_group,
            stage2_reasoning=stage2_reasoning,
            stage2_cost_usd=stage2_cost,
            total_cost_usd=stage1_cost + stage2_cost,
            total_latency_ms=stage1_latency + stage2_latency
        )

    def _stage1_agreement(
        self,
        responses: Dict[str, Dict[str, Any]],
        prompt: Dict[str, Any]
    ) -> Tuple[Dict[str, List[str]], List[str], str, float, int]:
        """
        Stage 1: Group responses by semantic agreement.

        Returns:
            (groups, majority_group_models, reasoning, cost, latency)
        """
        # Format responses for analysis
        responses_text = ""
        valid_models = []

        for model_key, response in responses.items():
            if response.get('error'):
                continue
            valid_models.append(model_key)

            responses_text += f"\n\n{'='*60}\n[{model_key.upper()}]\n{'='*60}\n"
            responses_text += response['answer']

        stage1_prompt = f"""You are grouping AI model responses by semantic agreement.

Original Question:
{prompt['text']}

Model Responses:
{responses_text}

Your task: Identify which models AGREE with each other (even if worded differently).

Step 1: Identify the core conclusion/answer of each response
Step 2: Group models that reach the SAME conclusion
Step 3: Determine which group has the most models (majority)

Important:
- Focus on CONCLUSIONS, not wording
- Two responses agree if they reach the same final answer
- Ignore stylistic differences
- We need to know which models form the majority consensus

Format your response as:
GROUPS:
Group A: [model1, model2, ...] - [brief description of their shared conclusion]
Group B: [model3, model4, ...] - [brief description of their shared conclusion]

MAJORITY: Group [A/B/C] with [X] models
MAJORITY_MODELS: [list of model names in majority group, e.g., OPUS-FAST, SONNET-FAST]"""

        # Map judge model key to Bedrock model ID
        judge_model_ids = {
            "haiku-fast": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
            "sonnet-fast": "us.anthropic.claude-sonnet-4-6",
            "opus-fast": "us.anthropic.claude-opus-4-6-v1"
        }
        judge_model_id = judge_model_ids.get(self.judge_model, judge_model_ids["opus-fast"])

        try:
            stage1_response, input_tokens, output_tokens, latency_ms = self.client.call_model(
                model_id=judge_model_id,
                prompt=stage1_prompt,
                max_tokens=1000,
                temperature=0.3
            )

            stage1_cost = calculate_cost(judge_model_id, input_tokens, output_tokens)

            # Parse majority models
            majority_models = self._parse_majority_models(stage1_response, valid_models)

            # Parse groups (for reporting)
            groups = self._parse_groups(stage1_response)

            print(f"  Stage 1: Majority group = {majority_models}")

            return groups, majority_models, stage1_response[:500], stage1_cost, latency_ms

        except Exception as e:
            print(f"  ERROR in stage 1: {e}")
            # Fallback: all models in one group
            return {"A": valid_models}, valid_models, f"Stage 1 failed: {e}", 0.0, 0

    def _stage2_correctness(
        self,
        responses: Dict[str, Dict[str, Any]],
        prompt: Dict[str, Any],
        majority_models: List[str]
    ) -> Tuple[str, str, str, float, int]:
        """
        Stage 2: Evaluate correctness within majority group.

        Returns:
            (selected_model, selected_answer, reasoning, cost, latency)
        """
        # Format only majority group responses
        responses_text = ""
        for model_key in majority_models:
            if model_key not in responses or responses[model_key].get('error'):
                continue

            responses_text += f"\n\n{'='*60}\n[{model_key.upper()}]\n{'='*60}\n"
            responses_text += responses[model_key]['answer']

        stage2_prompt = f"""You are evaluating solutions that have been identified as semantically agreeing. Your task is to determine which is most likely CORRECT.

Original Question:
{prompt['text']}

Candidate Solutions (all reach similar conclusions):
{responses_text}

Your task: Select the solution most likely to have the CORRECT final answer.

Evaluation criteria:
1. **Mathematical accuracy** - Verify calculations step-by-step
2. **Logical soundness** - Check if reasoning is valid
3. **Completeness** - Ensure all parts are addressed
4. **Answer verification** - Is the final number reasonable?

Important:
- These solutions already agree conceptually
- Look for calculation errors or logic gaps
- Verify intermediate steps independently
- If multiple are correct, pick any of them

Format your response as:
SELECTED: [model name, e.g., OPUS-FAST]
FINAL_ANSWER: [the numerical answer]
REASONING: [2-3 sentences explaining verification and why this is most correct]"""

        judge_model_ids = {
            "haiku-fast": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
            "sonnet-fast": "us.anthropic.claude-sonnet-4-6",
            "opus-fast": "us.anthropic.claude-opus-4-6-v1"
        }
        judge_model_id = judge_model_ids.get(self.judge_model, judge_model_ids["opus-fast"])

        try:
            stage2_response, input_tokens, output_tokens, latency_ms = self.client.call_model(
                model_id=judge_model_id,
                prompt=stage2_prompt,
                max_tokens=800,
                temperature=0.3
            )

            stage2_cost = calculate_cost(judge_model_id, input_tokens, output_tokens)

            # Parse selection
            selected_model = self._parse_selected_model(stage2_response, majority_models)
            selected_answer = responses[selected_model]['answer']
            reasoning = self._parse_reasoning(stage2_response)

            print(f"  Stage 2: Selected {selected_model}")

            return selected_model, selected_answer, reasoning, stage2_cost, latency_ms

        except Exception as e:
            print(f"  ERROR in stage 2: {e}")
            # Fallback to first model in majority
            fallback_model = majority_models[0] if majority_models else "opus-fast"
            return fallback_model, responses[fallback_model]['answer'], f"Stage 2 failed: {e}", 0.0, 0

    def _parse_majority_models(self, response: str, valid_models: List[str]) -> List[str]:
        """Extract majority group models from stage 1 response"""
        # Look for MAJORITY_MODELS: [list]
        match = re.search(r'MAJORITY_MODELS:\s*([^\n]+)', response, re.IGNORECASE)
        if match:
            models_text = match.group(1)
            majority = []
            for model in valid_models:
                if model.upper() in models_text.upper():
                    majority.append(model)
            if majority:
                return majority

        # Fallback: return all valid models
        return valid_models

    def _parse_groups(self, response: str) -> Dict[str, List[str]]:
        """Parse group structure from stage 1 response (for reporting)"""
        groups = {}
        # This is simplified - just create one group for now
        groups["majority"] = []
        return groups

    def _parse_selected_model(self, response: str, candidates: List[str]) -> str:
        """Extract selected model from stage 2 response"""
        match = re.search(r'SELECTED:\s*([A-Z\-]+)', response, re.IGNORECASE)
        if match:
            selected = match.group(1).lower()
            for model in candidates:
                if model.replace('-', '') in selected.replace('-', ''):
                    return model

        # Fallback
        for model in candidates:
            if model.upper() in response.upper():
                return model

        return candidates[0] if candidates else "opus-fast"

    def _parse_reasoning(self, response: str) -> str:
        """Extract reasoning from response"""
        match = re.search(r'REASONING:\s*(.+)', response, re.IGNORECASE | re.DOTALL)
        if match:
            reasoning = match.group(1).strip()
            reasoning = reasoning.split('\n\n')[0]
            return reasoning[:500]
        return response[:200]

    def _mock_two_stage(self, responses: Dict[str, Dict[str, Any]],
                       prompt: Dict[str, Any]) -> TwoStageResult:
        """Mock two-stage judging for testing"""
        valid_models = [k for k in responses.keys() if not responses[k].get('error')]

        return TwoStageResult(
            prompt_id=prompt['id'],
            strategy="two_stage_judging",
            selected_answer="Mock answer from two-stage selection",
            selected_model=valid_models[0] if valid_models else "opus-fast",
            stage1_groups={"A": valid_models[:2], "B": valid_models[2:]},
            stage1_majority=valid_models[:2],
            stage1_reasoning="Mock stage 1: Grouped by agreement",
            stage1_cost_usd=0.0,
            stage2_evaluated=valid_models[:2],
            stage2_reasoning="Mock stage 2: Selected for correctness",
            stage2_cost_usd=0.0,
            total_cost_usd=0.0,
            total_latency_ms=0
        )


def main():
    """CLI for testing two-stage aggregation"""
    import argparse

    parser = argparse.ArgumentParser(description='Two-stage aggregation (agreement + correctness)')
    parser.add_argument('prompt_file', help='JSON file with prompts')
    parser.add_argument('--judge', default='opus-fast', help='Judge model')
    parser.add_argument('--output', help='Output JSON file')
    parser.add_argument('--live', action='store_true', help='Use live API (default: mock)')

    args = parser.parse_args()

    print(f"\nTwo-Stage Aggregation:")
    print(f"  Stage 1: Agreement-based grouping")
    print(f"  Stage 2: Correctness evaluation")
    print(f"  Judge: {args.judge}")
    print(f"  Mode: {'LIVE' if args.live else 'MOCK'}")
    print()

    aggregator = TwoStageAggregator(mock_mode=not args.live, judge_model=args.judge)
    print("✓ Aggregator initialized")


if __name__ == "__main__":
    main()
