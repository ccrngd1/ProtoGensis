#!/usr/bin/env python3
"""
Vote Aggregator

Two strategies:
1. Majority vote for discrete/factual answers
2. Judge model (Haiku) selects best whole response for open-ended questions

Surfaces the irony: if you need a strong judge model, why not just use it directly?
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
class VoteResult:
    """Result of vote aggregation"""
    prompt_id: str
    strategy: str  # "majority_vote" or "judge_selection"
    selected_answer: str
    vote_counts: Optional[Dict[str, int]] = None  # For majority vote
    judge_reasoning: Optional[str] = None  # For judge selection
    convergence: bool = False  # True if all models agreed
    models_agreeing: List[str] = None  # Which models agreed with result
    judge_cost_usd: float = 0.0  # Cost of judge model call
    judge_latency_ms: int = 0  # Latency of judge call


class VoteAggregator:
    """Aggregates model responses via voting or judge selection"""

    def __init__(self, mock_mode: bool = True, use_semantic_vote: bool = True, judge_model: str = "haiku-fast"):
        self.mock_mode = mock_mode
        self.use_semantic_vote = use_semantic_vote  # True = majority vote, False = judge selection
        self.judge_model = judge_model  # Which model to use as judge (haiku-fast, opus-fast, sonnet-fast)

        if not mock_mode:
            try:
                self.client = BedrockClient()
                if use_semantic_vote:
                    print(f"✓ Semantic majority vote ({judge_model} judge) initialized")
                else:
                    print(f"✓ Judge selection ({judge_model} judge) initialized")
            except ValueError as e:
                print(f"ERROR: {e}")
                raise
        else:
            self.client = None

    def _extract_discrete_answer(self, text: str, prompt_id: str) -> Optional[str]:
        """
        Attempt to extract a discrete answer (yes/no, choice, number) from response.
        Returns None if answer appears to be open-ended.
        """

        # For specific known prompt types, apply extraction logic
        if "monty_hall" in prompt_id:
            # Look for "door" selection
            match = re.search(r'(door\s*[1-4]|switch|stay)', text.lower())
            if match:
                return match.group(1).strip()

        if "deadlock" in prompt_id or "mutex" in prompt_id:
            # Look for who's right (first/second/third developer)
            if "first developer" in text.lower() or "developer claims.*deadlock" in text.lower():
                return "first_developer"
            elif "second developer" in text.lower() or "race condition" in text.lower():
                return "second_developer"
            elif "third developer" in text.lower():
                return "third_developer"

        if "regex" in prompt_id:
            # Look for behavior predictions
            if "exponential" in text.lower() or "catastrophic backtracking" in text.lower():
                return "exponential_backtracking"
            elif "instant" in text.lower() or "fail immediately" in text.lower():
                return "instant_fail"

        if "bayes" in prompt_id or "medical" in prompt_id:
            # Look for probability or who's correct
            prob_match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
            if prob_match:
                return f"{prob_match.group(1)}%"

            if "friend" in text.lower() and "correct" in text.lower():
                return "friend_correct"
            elif "doctor" in text.lower() and "correct" in text.lower():
                return "doctor_correct"

        # If no discrete answer found, return None (triggers judge selection)
        return None

    def majority_vote(self, responses: Dict[str, Dict[str, Any]],
                      prompt_id: str) -> Optional[VoteResult]:
        """
        Perform majority vote for discrete answers.
        Returns the most common answer or None if discrete extraction fails.
        """

        # Extract discrete answers from each model
        answers = {}
        for model_key, response in responses.items():
            if response.get('error'):
                continue

            answer_text = response.get('answer', '')
            discrete_answer = self._extract_discrete_answer(answer_text, prompt_id)

            if discrete_answer:
                answers[model_key] = discrete_answer
            else:
                # Can't extract discrete answer, return None to signal judge needed
                return None

        if not answers:
            return None

        # Count votes
        vote_counts = Counter(answers.values())
        most_common_answer, count = vote_counts.most_common(1)[0]

        # Determine which models agreed
        models_agreeing = [m for m, a in answers.items() if a == most_common_answer]

        # Check convergence (all agreed)
        convergence = len(models_agreeing) == len(answers)

        # Get full answer text from one of the agreeing models
        selected_answer = responses[models_agreeing[0]]['answer']

        return VoteResult(
            prompt_id=prompt_id,
            strategy="majority_vote",
            selected_answer=selected_answer,
            vote_counts=dict(vote_counts),
            convergence=convergence,
            models_agreeing=models_agreeing
        )

    def _judge_selection_mock(self, responses: Dict[str, Dict[str, Any]],
                               prompt: Dict[str, Any]) -> VoteResult:
        """
        Mock judge selection (simulates a judge model choosing best response).
        In reality, this would call Haiku as judge.
        """

        prompt_id = prompt['id']

        # Mock judge reasoning (would be actual LLM call in production)
        judge_reasoning = f"""Judge evaluation for {prompt_id}:

Comparing three responses:

**Opus**: Strong reasoning trace with step-by-step probability calculations.
Correctly applies Bayes' theorem. Clear final answer.

**Nova**: Good structural analysis. Similar conclusion to Opus.
Slightly less detailed in showing intermediate steps.

**Sonnet**: Comprehensive probability tree approach. Reaches same conclusion.
Good explanation of why the analysis matters.

All three models converge on strong reasoning.
Selecting Opus for most thorough explanation of the methodology.
"""

        # In mock mode, just select based on simple heuristic
        # (in production, this would be judge model's decision)
        selected_model = "opus"  # Default to Opus as "judge's choice"

        # Check if all models actually agree (for convergence metric)
        answers = [r['answer'] for r in responses.values() if not r.get('error')]
        convergence = len(set(answers)) == 1

        return VoteResult(
            prompt_id=prompt_id,
            strategy="judge_selection",
            selected_answer=responses[selected_model]['answer'],
            judge_reasoning=judge_reasoning,
            convergence=convergence,
            models_agreeing=[selected_model]
        )

    def _semantic_majority_vote(self, responses: Dict[str, Dict[str, Any]],
                                 prompt: Dict[str, Any]) -> VoteResult:
        """
        Use LLM to identify which answers semantically agree, then pick the majority.
        Uses confidence weighting: models with higher confidence have more influence.
        """

        # Format responses for analysis, including confidence scores
        responses_text = ""
        valid_models = []
        model_confidences = {}

        for model_key, response in responses.items():
            if response.get('error'):
                continue
            valid_models.append(model_key)
            confidence = response.get('confidence', 0.5)
            model_confidences[model_key] = confidence

            responses_text += f"\n\n{'='*60}\n[{model_key.upper()}] - Confidence: {confidence:.2f}\n{'='*60}\n"
            responses_text += response['answer']

        semantic_vote_prompt = f"""You are analyzing responses from multiple AI models to identify which answers AGREE with each other (even if worded differently).

Original Question:
{prompt['text']}

Responses from models (with confidence scores):
{responses_text}

Your task:
1. Identify the CORE CONCLUSION of each response (ignore stylistic differences)
2. Group responses that reach the SAME conclusion (semantic agreement)
3. Apply CONFIDENCE WEIGHTING: Models with higher confidence should have more influence
4. Determine the weighted majority

Confidence weighting rules:
- A model with confidence 0.9 has 1.8x the weight of a model with confidence 0.5
- When calculating majority, sum the confidence scores of agreeing models
- The group with the highest total confidence wins

Example:
- ModelA (0.9 conf) + ModelB (0.8 conf) agree → total weight = 1.7
- ModelC (0.6 conf) disagrees → weight = 0.6
- Majority: ModelA + ModelB (higher weight)

Important:
- Focus on CONCLUSIONS, not wording or explanation style
- Two responses AGREE if they reach the same final answer/recommendation
- Use confidence scores to weight the votes
- If all models disagree, pick the one with highest confidence

Format your response as:
MAJORITY: [list of model names that form the weighted majority, e.g., "NOVA, MISTRAL, HAIKU"]
CONFIDENCE_WEIGHTS: [sum of confidence scores for majority group]
REASONING: [brief explanation of what they agree on and why this group won]"""

        # Map judge model key to Bedrock model ID
        judge_model_ids = {
            "haiku-fast": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
            "sonnet-fast": "us.anthropic.claude-sonnet-4-6-20250929-v1:0",
            "opus-fast": "us.anthropic.claude-opus-4-6-20250929-v1:0"
        }
        judge_model_id = judge_model_ids.get(self.judge_model, judge_model_ids["haiku-fast"])

        try:
            vote_response, input_tokens, output_tokens, latency_ms = self.client.call_model(
                model_id=judge_model_id,
                prompt=semantic_vote_prompt,
                max_tokens=1000,
                temperature=0.3  # Lower temp for more deterministic grouping
            )

            vote_cost = calculate_cost(
                judge_model_id,
                input_tokens,
                output_tokens
            )

            # Parse the majority from response
            selected_models = []
            if "MAJORITY:" in vote_response:
                majority_line = vote_response.split("MAJORITY:")[1].split("\n")[0]
                # Extract model names
                for model_key in valid_models:
                    if model_key.upper() in majority_line.upper():
                        selected_models.append(model_key)

            # If parsing failed or no majority, fall back to first valid model
            if not selected_models:
                if "NO MAJORITY" in vote_response.upper() or "ALL MODELS DISAGREE" in vote_response.upper():
                    # True disagreement, pick first model
                    selected_models = [valid_models[0]] if valid_models else ["opus"]
                    convergence = False
                else:
                    # Parsing failed, try to extract from reasoning
                    selected_models = [valid_models[0]] if valid_models else ["opus"]
                    convergence = False
            else:
                # Check convergence: did all models agree?
                convergence = len(selected_models) == len(valid_models)

            # Pick first model from majority group
            selected_model = selected_models[0] if selected_models else "opus"

            return VoteResult(
                prompt_id=prompt['id'],
                strategy="semantic_majority_vote",
                selected_answer=responses[selected_model]['answer'],
                judge_reasoning=vote_response,
                convergence=convergence,
                models_agreeing=selected_models,
                judge_cost_usd=vote_cost,
                judge_latency_ms=latency_ms
            )

        except Exception as e:
            print(f"  ⚠️  Error calling semantic vote model: {e}")
            # Fall back to judge selection
            return self._judge_selection_live(responses, prompt)

    def _judge_selection_live(self, responses: Dict[str, Dict[str, Any]],
                               prompt: Dict[str, Any]) -> VoteResult:
        """
        Use actual judge model (Haiku - cheap but capable) to select best response.
        This highlights the irony: if you need a strong model to judge,
        why not just use it directly?
        """

        # Format responses for judge
        responses_text = ""
        valid_models = []
        for model_key, response in responses.items():
            if response.get('error'):
                continue
            valid_models.append(model_key)
            responses_text += f"\n\n{'='*60}\nModel: {model_key.upper()}\n{'='*60}\n"
            responses_text += response['answer']

        judge_prompt = f"""You are evaluating responses from three AI models to select the best answer.

Original Question:
{prompt['text']}

Responses from three models:
{responses_text}

Analyze each response and select the best one. Consider:
- Correctness of reasoning
- Clarity of explanation
- Handling of edge cases and nuance
- Quality of the final answer

Provide your selection (just the model name in CAPS: OPUS, NOVA, or SONNET) followed by your reasoning."""

        try:
            judge_response, input_tokens, output_tokens, latency_ms = self.client.call_model(
                model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
                prompt=judge_prompt,
                max_tokens=2000,
                temperature=0.7
            )

            judge_cost = calculate_cost(
                "us.anthropic.claude-haiku-4-5-20251001-v1:0",
                input_tokens,
                output_tokens
            )

            # Extract which model was selected (look at the end of the response)
            selected_model = None

            # Get last part of response for analysis
            last_500 = judge_response[-500:]
            last_200 = judge_response[-200:]

            # Strategy 1: Look for explicit positive selection phrases (last 200 chars)
            for model_key in valid_models:
                model_upper = model_key.upper()
                last_upper = last_200.upper()

                # Strong positive selection phrases
                positive_phrases = [
                    f"{model_upper}'S CLEAR",
                    f"{model_upper}'S EXPLANATION",
                    f"MAKES {model_upper} THE BEST",
                    f"{model_upper} IS THE BEST",
                    f"{model_upper} PROVIDES THE MOST",
                    f"SELECTING {model_upper}",
                    f"CHOICE: {model_upper}",
                ]

                for phrase in positive_phrases:
                    if phrase in last_upper:
                        selected_model = model_key
                        break

                if selected_model:
                    break

            # Strategy 2: Look for model name on a line by itself (check beginning AND end)
            if not selected_model:
                lines = judge_response.strip().split('\n')

                # First check the very first line (common pattern: "NOVA\n\n**Reasoning:**")
                if lines:
                    first_line = lines[0].strip().strip('*').strip()
                    for model_key in valid_models:
                        if first_line.upper() == model_key.upper():
                            selected_model = model_key
                            break

                # Then check last 5 lines
                if not selected_model:
                    for line in reversed(lines[-5:]):
                        stripped = line.strip().strip('*').strip()
                        for model_key in valid_models:
                            if stripped.upper() == model_key.upper():
                                selected_model = model_key
                                break
                        if selected_model:
                            break

            # Strategy 3: Count positive vs negative mentions in last 500 chars
            if not selected_model:
                scores = {}
                for model_key in valid_models:
                    model_upper = model_key.upper()
                    last_upper = last_500.upper()

                    # Positive indicators (worth +1 each)
                    positive = sum([
                        last_upper.count(f"{model_upper} PROVIDES THE MOST"),
                        last_upper.count(f"{model_upper} IS SUPERIOR"),
                        last_upper.count(f"{model_upper} IS THE BETTER"),
                        last_upper.count(f"{model_upper}'S") * 0.5,  # Possessive often indicates selection
                    ])

                    # Negative indicators (worth -2 each, stronger signal)
                    negative = sum([
                        last_upper.count(f"{model_upper} PROVIDES NO") * 2,
                        last_upper.count(f"{model_upper} IS COMPLETELY EMPTY") * 2,
                        last_upper.count(f"{model_upper} PROVIDES NOTHING") * 2,
                        last_upper.count(f"{model_upper} FAILS") * 2,
                    ])

                    scores[model_key] = positive - negative

                # Select model with highest positive score that has a non-empty answer
                valid_scores = [(k, v) for k, v in scores.items()
                               if v > 0 and responses.get(k, {}).get('answer', '').strip()]

                if valid_scores:
                    selected_model = max(valid_scores, key=lambda x: x[1])[0]
                else:
                    # Fallback: select any model with highest score
                    selected_model = max(scores.items(), key=lambda x: x[1])[0]

            # Check convergence by analyzing judge's assessment
            convergence = "all three" in judge_response.lower() or "all models" in judge_response.lower()

            return VoteResult(
                prompt_id=prompt['id'],
                strategy="judge_selection",
                selected_answer=responses[selected_model]['answer'],
                judge_reasoning=judge_response,
                convergence=convergence,
                models_agreeing=[selected_model],
                judge_cost_usd=judge_cost,
                judge_latency_ms=latency_ms
            )

        except Exception as e:
            print(f"  ⚠️  Error calling judge model: {e}")
            # Fall back to mock if live call fails
            return self._judge_selection_mock(responses, prompt)

    def aggregate(self, responses: Dict[str, Dict[str, Any]],
                  prompt: Dict[str, Any]) -> VoteResult:
        """
        Main aggregation method.
        Tries heuristic majority vote first; falls back to LLM-based approach.
        """

        # Try heuristic majority vote for discrete answers
        vote_result = self.majority_vote(responses, prompt['id'])

        if vote_result:
            return vote_result

        # Fall back to LLM-based approach
        if self.mock_mode:
            return self._judge_selection_mock(responses, prompt)
        else:
            if self.use_semantic_vote:
                # Semantic majority vote: identify agreement, pick most common
                return self._semantic_majority_vote(responses, prompt)
            else:
                # Judge selection: pick the best quality answer
                return self._judge_selection_live(responses, prompt)


def main():
    """Demo of vote aggregator"""
    import argparse
    from concurrent.futures import ThreadPoolExecutor, as_completed

    parser = argparse.ArgumentParser(description="Vote Aggregator")
    parser.add_argument("responses_file", help="Path to responses JSON file")
    parser.add_argument("--live", action="store_true", help="Use live judge model")
    parser.add_argument("--judge-selection", action="store_true",
                       help="Use judge selection (pick best) instead of semantic majority vote (pick most common)")
    parser.add_argument("--sequential", action="store_true",
                       help="Process prompts sequentially instead of in parallel")
    args = parser.parse_args()

    with open(args.responses_file, 'r') as f:
        data = json.load(f)

    mock_mode = not args.live
    use_semantic_vote = not args.judge_selection
    aggregator = VoteAggregator(mock_mode=mock_mode, use_semantic_vote=use_semantic_vote)

    mode_desc = "MOCK" if mock_mode else ("JUDGE SELECTION" if args.judge_selection else "SEMANTIC MAJORITY VOTE")
    parallel_desc = "(sequential)" if args.sequential else "(parallel)"
    print(f"Running vote aggregation in {mode_desc} mode {parallel_desc}...")

    if args.sequential:
        # Original sequential processing
        results = []
        total_judge_cost = 0.0

        for item in data:
            prompt = item['prompt']
            responses = item['responses']

            vote_result = aggregator.aggregate(responses, prompt)
            results.append(asdict(vote_result))

            total_judge_cost += vote_result.judge_cost_usd

            print(f"\n{'='*80}")
            print(f"Prompt: {prompt['id']}")
            print(f"Strategy: {vote_result.strategy}")
            print(f"Convergence: {vote_result.convergence}")
            if vote_result.vote_counts:
                print(f"Vote counts: {vote_result.vote_counts}")
            if vote_result.judge_reasoning:
                print(f"Judge reasoning: {vote_result.judge_reasoning[:200]}...")
            if vote_result.judge_cost_usd > 0:
                print(f"Judge cost: ${vote_result.judge_cost_usd:.6f}")
            print(f"Models agreeing: {vote_result.models_agreeing}")
    else:
        # Parallel processing
        print(f"⚡ Processing {len(data)} prompts in parallel...")

        def process_prompt(item):
            prompt = item['prompt']
            responses = item['responses']
            vote_result = aggregator.aggregate(responses, prompt)
            return prompt['id'], vote_result

        results_dict = {}
        total_judge_cost = 0.0

        with ThreadPoolExecutor(max_workers=min(10, len(data))) as executor:
            futures = {executor.submit(process_prompt, item): item['prompt']['id']
                      for item in data}

            for future in as_completed(futures):
                prompt_id = futures[future]
                try:
                    returned_id, vote_result = future.result()
                    results_dict[returned_id] = vote_result
                    total_judge_cost += vote_result.judge_cost_usd

                    print(f"  ✓ {prompt_id}: {vote_result.strategy} | {', '.join(vote_result.models_agreeing)}")
                except Exception as e:
                    print(f"  ❌ {prompt_id}: Error - {e}")

        # Convert to list in original order
        results = [asdict(results_dict[item['prompt']['id']]) for item in data]

    # Save results
    output_file = args.responses_file.replace('responses.json', 'vote_results.json')
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n✓ Vote results saved to {output_file}")
    if total_judge_cost > 0:
        print(f"Total judge cost: ${total_judge_cost:.6f}")


if __name__ == "__main__":
    main()
