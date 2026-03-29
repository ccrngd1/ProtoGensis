"""
LLM-as-Judge Evaluator - CC's original 2023 TDS pattern.
Uses Claude on Bedrock to evaluate RAG output faithfulness.
"""

import json
import time
import re
import random
from typing import Dict, Optional
from dataclasses import dataclass, asdict

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from config import settings


@dataclass
class LLMJudgeResult:
    """Result from LLM-as-judge evaluation."""
    faithfulness_score: float  # 0.0 to 1.0
    explanation: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


class LLMJudgeEvaluator:
    """
    LLM-as-Judge evaluator using Claude on Bedrock.

    This implements the pattern from CC's 2023 TDS article:
    "How to Measure the Success of Your RAG-based LLM System"

    The evaluator prompts Claude to score faithfulness on a 0-1 scale
    and provide an explanation for its judgment.
    """

    def __init__(self, mock_mode: bool = None):
        """
        Initialize LLM-as-judge evaluator.

        Args:
            mock_mode: If True, use mock evaluation. If None, use settings.mock_mode
        """
        self.mock_mode = mock_mode if mock_mode is not None else settings.mock_mode

        if not self.mock_mode:
            if not BOTO3_AVAILABLE:
                raise ImportError("boto3 is required for non-mock mode")
            self.bedrock_client = boto3.client(
                'bedrock-runtime',
                region_name=settings.aws_region
            )

    def evaluate(self, context: str, query: str, response: str) -> LLMJudgeResult:
        """
        Evaluate RAG response faithfulness using LLM-as-judge.

        Args:
            context: Retrieved context chunks
            query: User query
            response: Generated response to evaluate

        Returns:
            LLMJudgeResult with score, explanation, and metrics
        """
        if self.mock_mode:
            return self._mock_evaluate(context, query, response)

        prompt = self._build_prompt(context, query, response)

        start_time = time.time()

        try:
            bedrock_response = self.bedrock_client.converse(
                modelId=settings.bedrock_model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": prompt}]
                    }
                ],
                inferenceConfig={
                    "maxTokens": 500,
                    "temperature": 0.1
                }
            )

            output_text = bedrock_response['output']['message']['content'][0]['text']
            input_tokens = bedrock_response['usage']['inputTokens']
            output_tokens = bedrock_response['usage']['outputTokens']

            latency_ms = (time.time() - start_time) * 1000

            # Parse the response
            score, explanation = self._parse_response(output_text)

            # Calculate cost
            cost = self._calculate_cost(input_tokens, output_tokens)

            return LLMJudgeResult(
                faithfulness_score=score,
                explanation=explanation,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=cost
            )

        except ClientError as e:
            raise Exception(f"LLM-as-judge evaluation failed: {e}")

    def _build_prompt(self, context: str, query: str, response: str) -> str:
        """Build the evaluation prompt."""
        return f"""You are evaluating the faithfulness of a RAG system's response.

**Context (retrieved from knowledge base):**
{context}

**User Query:**
{query}

**Generated Response:**
{response}

**Task:**
Evaluate whether the response is faithful to the context. A faithful response:
1. Only makes claims that are directly supported by the context
2. Does not add information not present in the context
3. Does not contradict the context
4. Accurately represents the information from the context

**Output Format:**
Provide your evaluation in the following format:

FAITHFULNESS_SCORE: [a number between 0.0 and 1.0]
- 0.0 = Completely unfaithful (hallucinated, contradicts context)
- 0.5 = Partially faithful (some claims supported, some not)
- 1.0 = Completely faithful (all claims supported by context)

EXPLANATION: [2-3 sentences explaining your score]

Be strict in your evaluation. If the response includes any claims not supported by the context, reduce the score accordingly."""

    def _parse_response(self, output: str) -> tuple[float, str]:
        """Parse the LLM's evaluation response."""
        # Extract score
        score_match = re.search(r'FAITHFULNESS_SCORE:\s*([0-9]*\.?[0-9]+)', output)
        if score_match:
            score = float(score_match.group(1))
            score = max(0.0, min(1.0, score))  # Clamp to [0, 1]
        else:
            # Fallback: look for any number
            numbers = re.findall(r'([0-9]*\.?[0-9]+)', output)
            score = float(numbers[0]) if numbers else 0.5

        # Extract explanation
        explanation_match = re.search(r'EXPLANATION:\s*(.+)', output, re.DOTALL)
        if explanation_match:
            explanation = explanation_match.group(1).strip()
        else:
            explanation = output.strip()

        return score, explanation

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost in USD."""
        input_cost = (input_tokens / 1000) * settings.claude_input_cost_per_1k
        output_cost = (output_tokens / 1000) * settings.claude_output_cost_per_1k
        return input_cost + output_cost

    def _mock_evaluate(self, context: str, query: str, response: str) -> LLMJudgeResult:
        """Mock evaluation for testing without AWS."""
        # Simulate LLM latency (2-5 seconds typical)
        latency_ms = random.uniform(2000, 5000)
        time.sleep(latency_ms / 1000)

        # Simple heuristic: check if response words are in context
        response_words = set(response.lower().split())
        context_words = set(context.lower().split())
        overlap = len(response_words & context_words)
        total = len(response_words)

        # Basic faithfulness estimation
        if total > 0:
            word_overlap_ratio = overlap / total
            # Add some randomness for realism
            score = min(1.0, word_overlap_ratio + random.uniform(-0.1, 0.1))
            score = max(0.0, score)
        else:
            score = 0.5

        # Categorize and generate explanation
        if score >= 0.8:
            explanation = "The response is highly faithful to the context. All major claims are well-supported by the retrieved information."
        elif score >= 0.5:
            explanation = "The response is partially faithful. Some claims are supported by the context, but there may be additions or minor inaccuracies."
        else:
            explanation = "The response shows low faithfulness. Multiple claims are not supported by the context or appear to be hallucinated."

        # Estimate tokens
        input_tokens = len(context.split()) + len(query.split()) + len(response.split()) + 200
        output_tokens = 80

        cost = self._calculate_cost(input_tokens, output_tokens)

        return LLMJudgeResult(
            faithfulness_score=score,
            explanation=explanation,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost
        )


def main():
    """Demo the LLM-as-judge evaluator."""
    evaluator = LLMJudgeEvaluator(mock_mode=True)

    # Test cases
    test_cases = [
        {
            "name": "Faithful Response",
            "context": "Amazon S3 is an object storage service offering industry-leading scalability, data availability, security, and performance.",
            "query": "What is Amazon S3?",
            "response": "Amazon S3 is an object storage service that provides scalability, data availability, security, and performance."
        },
        {
            "name": "Hallucinated Response",
            "context": "Amazon S3 is an object storage service offering industry-leading scalability, data availability, security, and performance.",
            "query": "What is Amazon S3?",
            "response": "Amazon S3 is an object storage service that uses quantum encryption and provides 99.99999% durability with automatic replication across 12 availability zones."
        }
    ]

    print("=" * 80)
    print("LLM-as-Judge Evaluator Demo (Mock Mode)")
    print("=" * 80)

    for test in test_cases:
        print(f"\n{test['name']}")
        print("-" * 80)
        print(f"Query: {test['query']}")
        print(f"Response: {test['response']}")

        result = evaluator.evaluate(test['context'], test['query'], test['response'])

        print(f"\nEvaluation Results:")
        print(f"  Faithfulness Score: {result.faithfulness_score:.3f}")
        print(f"  Explanation: {result.explanation}")
        print(f"  Latency: {result.latency_ms:.2f}ms")
        print(f"  Cost: ${result.estimated_cost_usd:.6f}")
        print(f"  Tokens: {result.input_tokens} in, {result.output_tokens} out")


if __name__ == "__main__":
    main()
