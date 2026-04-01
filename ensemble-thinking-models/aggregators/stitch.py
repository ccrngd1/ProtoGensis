#!/usr/bin/env python3
"""
Stitch Synthesizer

Extracts strongest reasoning elements from each model's response
and synthesizes a combined answer that draws on multiple perspectives.

This is the most sophisticated aggregation strategy but also the most expensive
(requires orchestrator model to synthesize).
"""

import json
import sys
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import hashlib

# Add parent directory to path to import shared module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from shared.bedrock_client import BedrockClient, calculate_cost


@dataclass
class StitchResult:
    """Result of stitch synthesis"""
    prompt_id: str
    strategy: str = "stitch_synthesis"
    synthesized_answer: str = ""
    synthesis_reasoning: str = ""  # How orchestrator combined insights
    extracted_insights: Dict[str, List[str]] = None  # Key insights from each model
    convergence_analysis: str = ""  # Where models agreed/diverged
    cost_usd: float = 0.0  # Cost of orchestrator call
    latency_ms: int = 0  # Latency of orchestrator call
    models_used: List[str] = None


class StitchSynthesizer:
    """Synthesizes responses by extracting and combining reasoning elements"""

    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode

        if not mock_mode:
            try:
                self.client = BedrockClient()
                print("✓ Orchestrator model (Haiku) initialized")
            except ValueError as e:
                print(f"ERROR: {e}")
                raise
        else:
            self.client = None

    def _extract_key_insights(self, response: Dict[str, Any]) -> List[str]:
        """
        Extract key reasoning insights from a response.
        In production, this might use NLP or another model call.
        """

        answer = response.get('answer', '')
        reasoning = response.get('reasoning_trace', '')

        # Simple heuristic: look for numbered points, key phrases, conclusions
        insights = []

        # Extract sentences with key indicators
        key_phrases = [
            'therefore', 'thus', 'because', 'the key insight',
            'importantly', 'crucially', 'note that', 'consider that',
            'the reason', 'this means', 'it follows'
        ]

        full_text = reasoning + "\n\n" + answer

        sentences = full_text.split('.')
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check if sentence contains key reasoning phrases
            if any(phrase in sentence.lower() for phrase in key_phrases):
                insights.append(sentence + '.')

            # Also extract sentences with probability/math
            if any(marker in sentence for marker in ['=', '%', 'probability', 'expected']):
                insights.append(sentence + '.')

        # Limit to top insights
        return insights[:5] if insights else ["No clear reasoning structure extracted"]

    def _analyze_convergence(self, responses: Dict[str, Dict[str, Any]]) -> str:
        """
        Analyze where models converge and diverge.
        This is key insight for understanding ensemble value.
        """

        analyses = []

        # Extract answers
        answers = {k: v.get('answer', '') for k, v in responses.items() if not v.get('error')}

        if not answers:
            return "Insufficient responses to analyze convergence"

        # Check for agreement on conclusion
        # Simple heuristic: do they all recommend the same action?
        keywords_per_model = {}
        for model_key, answer_text in answers.items():
            # Extract key decision words
            decision_words = []
            for word in ['switch', 'stay', 'door', 'swerve', 'straight', 'yes', 'no',
                        'correct', 'wrong', 'should', 'should not', 'agree', 'disagree']:
                if word in answer_text.lower():
                    decision_words.append(word)
            keywords_per_model[model_key] = set(decision_words)

        # Compare keyword overlap
        all_keywords = set()
        for keywords in keywords_per_model.values():
            all_keywords.update(keywords)

        common_keywords = all_keywords.copy()
        for keywords in keywords_per_model.values():
            common_keywords &= keywords

        if len(common_keywords) >= len(all_keywords) * 0.7:
            analyses.append("**High convergence**: Models largely agree on approach and conclusion.")
        elif len(common_keywords) >= len(all_keywords) * 0.4:
            analyses.append("**Moderate convergence**: Models share some key reasoning but differ in emphasis.")
        else:
            analyses.append("**Low convergence**: Models approach the problem differently.")

        # Note specific areas of agreement/disagreement
        if common_keywords:
            analyses.append(f"Common elements: {', '.join(common_keywords)}")

        divergent_elements = {}
        for model_key, keywords in keywords_per_model.items():
            unique = keywords - common_keywords
            if unique:
                divergent_elements[model_key] = unique

        if divergent_elements:
            analyses.append("Divergent elements by model:")
            for model_key, elements in divergent_elements.items():
                analyses.append(f"  - {model_key}: {', '.join(elements)}")

        return "\n".join(analyses)

    def _synthesize_mock(self, responses: Dict[str, Dict[str, Any]],
                         prompt: Dict[str, Any],
                         extracted_insights: Dict[str, List[str]],
                         convergence_analysis: str) -> tuple:
        """
        Mock synthesis (simulates orchestrator model combining insights).
        In reality, this would call Haiku as orchestrator.
        """

        prompt_id = prompt['id']

        # Create mock synthesized answer
        synthesis_reasoning = f"""Synthesis process for {prompt_id}:

1. Extracted key insights from all three models
2. Analyzed convergence: {convergence_analysis.split('.')[0]}
3. Identified strongest reasoning chains:
   - Opus: Rigorous step-by-step probability calculation
   - Nova: Clear Bayesian framework application
   - Sonnet: Comprehensive probability tree approach

4. Combined insights:
   - All models correctly identify the core probability principle
   - Opus provides the most detailed mathematical steps
   - Nova offers the clearest structural framework
   - Sonnet validates with alternative calculation method

5. Synthesized answer draws on:
   - Mathematical rigor from Opus
   - Structural clarity from Nova
   - Validation methodology from Sonnet
"""

        # Mock synthesized answer (would be actual LLM generation)
        synthesized_answer = f"""[Synthesized from 3 reasoning models]

Based on ensemble analysis combining Opus's mathematical rigor, Nova's structural framework, and Sonnet's validation approach:

{responses['opus']['answer'][:200]}...

This conclusion is strengthened by convergence across all three models, each arriving at the same result through different reasoning paths, which increases confidence in the answer's correctness.
"""

        # Mock cost and latency
        cost_usd = 0.005  # Approximate cost for Haiku synthesis call
        latency_ms = 3000

        return synthesized_answer, synthesis_reasoning, cost_usd, latency_ms

    def _synthesize_live(self, responses: Dict[str, Dict[str, Any]],
                         prompt: Dict[str, Any],
                         extracted_insights: Dict[str, List[str]],
                         convergence_analysis: str) -> tuple:
        """
        Use actual orchestrator model (Haiku - cheap and fast) to synthesize answer.
        """

        # Format insights for orchestrator
        insights_text = ""
        for model_key, insights in extracted_insights.items():
            insights_text += f"\n\n**{model_key.upper()} Key Insights:**\n"
            for i, insight in enumerate(insights, 1):
                insights_text += f"{i}. {insight}\n"

        # Format full responses
        responses_text = ""
        for model_key, response in responses.items():
            if response.get('error'):
                continue
            responses_text += f"\n\n{'='*60}\n**{model_key.upper()} Full Response:**\n{'='*60}\n"
            responses_text += response['answer']

        orchestrator_prompt = f"""You are an expert orchestrator synthesizing insights from multiple AI reasoning models.

Original Question:
{prompt['text']}

Convergence Analysis:
{convergence_analysis}

Extracted Key Insights:
{insights_text}

Full Responses:
{responses_text}

Your task:
1. Identify the strongest reasoning elements from each model
2. Synthesize a combined answer that draws on multiple perspectives
3. Note where models converge (high confidence) and diverge (areas of uncertainty)
4. Produce a final answer that is better than any individual response

Provide both your synthesis reasoning and the final synthesized answer."""

        try:
            synthesis_output, input_tokens, output_tokens, latency_ms = self.client.call_model(
                model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
                prompt=orchestrator_prompt,
                max_tokens=3000,
                temperature=0.7
            )

            cost_usd = calculate_cost(
                "us.anthropic.claude-haiku-4-5-20251001-v1:0",
                input_tokens,
                output_tokens
            )

            # Use the full synthesis output
            synthesis_reasoning = synthesis_output
            synthesized_answer = synthesis_output

            return synthesized_answer, synthesis_reasoning, cost_usd, latency_ms

        except Exception as e:
            print(f"  ⚠️  Error calling orchestrator model: {e}")
            # Fall back to mock if live call fails
            return self._synthesize_mock(responses, prompt, extracted_insights, convergence_analysis)

    def synthesize(self, responses: Dict[str, Dict[str, Any]],
                   prompt: Dict[str, Any]) -> StitchResult:
        """
        Main synthesis method.
        Extracts insights, analyzes convergence, and synthesizes combined answer.
        """

        # Extract key insights from each model
        extracted_insights = {}
        for model_key, response in responses.items():
            if response.get('error'):
                continue
            extracted_insights[model_key] = self._extract_key_insights(response)

        # Analyze convergence
        convergence_analysis = self._analyze_convergence(responses)

        # Synthesize answer
        if self.mock_mode:
            synthesized_answer, synthesis_reasoning, cost_usd, latency_ms = self._synthesize_mock(
                responses, prompt, extracted_insights, convergence_analysis
            )
        else:
            synthesized_answer, synthesis_reasoning, cost_usd, latency_ms = self._synthesize_live(
                responses, prompt, extracted_insights, convergence_analysis
            )

        return StitchResult(
            prompt_id=prompt['id'],
            synthesized_answer=synthesized_answer,
            synthesis_reasoning=synthesis_reasoning,
            extracted_insights=extracted_insights,
            convergence_analysis=convergence_analysis,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            models_used=list(extracted_insights.keys())
        )


def main():
    """Demo of stitch synthesizer"""
    import argparse

    parser = argparse.ArgumentParser(description="Stitch Synthesizer")
    parser.add_argument("responses_file", help="Path to responses JSON file")
    parser.add_argument("--live", action="store_true", help="Use live orchestrator model")
    args = parser.parse_args()

    with open(args.responses_file, 'r') as f:
        data = json.load(f)

    mock_mode = not args.live
    synthesizer = StitchSynthesizer(mock_mode=mock_mode)

    print(f"Running stitch synthesis in {'MOCK' if mock_mode else 'LIVE'} mode...")

    results = []
    total_cost = 0.0

    for item in data:
        prompt = item['prompt']
        responses = item['responses']

        stitch_result = synthesizer.synthesize(responses, prompt)
        results.append(asdict(stitch_result))

        total_cost += stitch_result.cost_usd

        print(f"\n{'='*80}")
        print(f"Prompt: {prompt['id']}")
        print(f"Models used: {stitch_result.models_used}")
        print(f"Synthesis cost: ${stitch_result.cost_usd:.6f}")
        print(f"Synthesis latency: {stitch_result.latency_ms}ms")
        print(f"\nConvergence Analysis:")
        print(stitch_result.convergence_analysis)
        print(f"\nSynthesized Answer:")
        print(stitch_result.synthesized_answer[:300] + "...")

    # Save results
    output_file = args.responses_file.replace('responses.json', 'stitch_results.json')
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*80}")
    print(f"✓ Stitch results saved to {output_file}")
    print(f"Total synthesis cost: ${total_cost:.6f}")


if __name__ == "__main__":
    main()
