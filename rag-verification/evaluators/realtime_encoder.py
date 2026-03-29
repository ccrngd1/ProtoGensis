"""
Real-Time Encoder Evaluator - Fast & Faithful / LettuceDetect pattern.
Token-level hallucination detection using encoder-based verification on SageMaker.
"""

import json
import time
import random
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from config import settings


@dataclass
class HallucinatedSpan:
    """A span of text identified as hallucinated."""
    text: str
    start_idx: int
    end_idx: int
    confidence: float


@dataclass
class RealtimeEncoderResult:
    """Result from real-time encoder evaluation."""
    is_faithful: bool
    hallucinated_spans: List[HallucinatedSpan]
    token_predictions: List[Tuple[str, bool, float]]  # (token, is_hallucinated, confidence)
    faithfulness_score: float  # 1.0 - (hallucinated_tokens / total_tokens)
    latency_ms: float
    num_tokens: int
    estimated_cost_usd: float


class RealtimeEncoderEvaluator:
    """
    Real-time encoder-based evaluator using Fast & Faithful approach on SageMaker.

    This approach:
    1. Concatenates context + query + response with special separators
    2. Uses an extended encoder (ModernBERT-based) for token-level classification
    3. Identifies hallucinated spans in real-time (sub-50ms for typical responses)
    4. Supports up to 32K tokens (Fast & Faithful) vs 8K (LettuceDetect)
    """

    def __init__(self, mock_mode: bool = None):
        """
        Initialize real-time encoder evaluator.

        Args:
            mock_mode: If True, use mock evaluation. If None, use settings.mock_mode
        """
        self.mock_mode = mock_mode if mock_mode is not None else settings.mock_mode

        if not self.mock_mode:
            if not BOTO3_AVAILABLE:
                raise ImportError("boto3 is required for non-mock mode")
            self.sagemaker_runtime = boto3.client(
                'sagemaker-runtime',
                region_name=settings.aws_region
            )

    def evaluate(self, context: str, query: str, response: str) -> RealtimeEncoderResult:
        """
        Evaluate RAG response faithfulness using token-level encoder.

        Args:
            context: Retrieved context chunks
            query: User query
            response: Generated response to evaluate

        Returns:
            RealtimeEncoderResult with token-level predictions and spans
        """
        if self.mock_mode:
            return self._mock_evaluate(context, query, response)

        start_time = time.time()

        # Construct input: [Context] [SEP] [Query] [SEP] [Response]
        input_text = f"{context} [SEP] {query} [SEP] {response}"

        # Prepare payload for SageMaker endpoint
        payload = {
            "inputs": input_text,
            "parameters": {
                "return_token_predictions": True,
                "response_start_marker": "[SEP]"  # Mark where response begins
            }
        }

        try:
            sagemaker_response = self.sagemaker_runtime.invoke_endpoint(
                EndpointName=settings.sagemaker_encoder_endpoint,
                ContentType='application/json',
                Body=json.dumps(payload)
            )

            result = json.loads(sagemaker_response['Body'].read().decode())

            latency_ms = (time.time() - start_time) * 1000

            # Parse token-level predictions
            token_predictions = self._parse_token_predictions(result, response)

            # Extract hallucinated spans
            hallucinated_spans = self._extract_spans(token_predictions)

            # Calculate faithfulness score
            total_tokens = len(token_predictions)
            hallucinated_tokens = sum(1 for _, is_hall, _ in token_predictions if is_hall)
            faithfulness_score = 1.0 - (hallucinated_tokens / total_tokens if total_tokens > 0 else 0)

            is_faithful = len(hallucinated_spans) == 0

            # Calculate cost
            cost = self._calculate_cost(latency_ms)

            return RealtimeEncoderResult(
                is_faithful=is_faithful,
                hallucinated_spans=hallucinated_spans,
                token_predictions=token_predictions,
                faithfulness_score=faithfulness_score,
                latency_ms=latency_ms,
                num_tokens=total_tokens,
                estimated_cost_usd=cost
            )

        except ClientError as e:
            raise Exception(f"SageMaker encoder inference failed: {e}")

    def _parse_token_predictions(self, result: Dict, response: str) -> List[Tuple[str, bool, float]]:
        """
        Parse token-level predictions from model output.

        Expected format:
        {
            "predictions": [
                {"token": "Amazon", "hallucinated": false, "confidence": 0.95},
                ...
            ]
        }
        """
        predictions = []
        for pred in result.get('predictions', []):
            token = pred.get('token', '')
            is_hallucinated = pred.get('hallucinated', False)
            confidence = pred.get('confidence', 0.5)
            predictions.append((token, is_hallucinated, confidence))

        return predictions

    def _extract_spans(self, token_predictions: List[Tuple[str, bool, float]]) -> List[HallucinatedSpan]:
        """Extract contiguous spans of hallucinated tokens."""
        spans = []
        current_span_tokens = []
        current_start_idx = 0

        for i, (token, is_hallucinated, confidence) in enumerate(token_predictions):
            if is_hallucinated:
                if not current_span_tokens:
                    current_start_idx = i
                current_span_tokens.append((token, confidence))
            else:
                if current_span_tokens:
                    # End current span
                    span_text = ' '.join([t for t, _ in current_span_tokens])
                    avg_confidence = sum([c for _, c in current_span_tokens]) / len(current_span_tokens)
                    spans.append(HallucinatedSpan(
                        text=span_text,
                        start_idx=current_start_idx,
                        end_idx=i - 1,
                        confidence=avg_confidence
                    ))
                    current_span_tokens = []

        # Handle final span if exists
        if current_span_tokens:
            span_text = ' '.join([t for t, _ in current_span_tokens])
            avg_confidence = sum([c for _, c in current_span_tokens]) / len(current_span_tokens)
            spans.append(HallucinatedSpan(
                text=span_text,
                start_idx=current_start_idx,
                end_idx=len(token_predictions) - 1,
                confidence=avg_confidence
            ))

        return spans

    def _calculate_cost(self, latency_ms: float) -> float:
        """Calculate estimated cost based on compute time."""
        compute_seconds = latency_ms / 1000
        return compute_seconds * settings.sagemaker_compute_cost_per_sec

    def _mock_evaluate(self, context: str, query: str, response: str) -> RealtimeEncoderResult:
        """Mock evaluation for testing without AWS."""
        # Simulate encoder latency (10-50ms typical)
        latency_ms = random.uniform(10, 50)
        time.sleep(latency_ms / 1000)

        # Tokenize response (simple word splitting)
        tokens = response.split()
        context_words = set(context.lower().split())

        # Token-level predictions based on context overlap
        token_predictions = []
        for token in tokens:
            # Check if token (or similar) appears in context
            token_lower = token.lower().strip('.,!?;:')
            in_context = token_lower in context_words

            # Add some randomness
            if in_context:
                is_hallucinated = random.random() < 0.1  # 10% false positive
                confidence = random.uniform(0.8, 0.95)
            else:
                is_hallucinated = random.random() < 0.7  # 70% true positive
                confidence = random.uniform(0.6, 0.85)

            token_predictions.append((token, is_hallucinated, confidence))

        # Extract spans
        hallucinated_spans = self._extract_spans(token_predictions)

        # Calculate faithfulness
        total_tokens = len(token_predictions)
        hallucinated_tokens = sum(1 for _, is_hall, _ in token_predictions if is_hall)
        faithfulness_score = 1.0 - (hallucinated_tokens / total_tokens if total_tokens > 0 else 0)

        is_faithful = len(hallucinated_spans) == 0

        cost = self._calculate_cost(latency_ms)

        return RealtimeEncoderResult(
            is_faithful=is_faithful,
            hallucinated_spans=hallucinated_spans,
            token_predictions=token_predictions,
            faithfulness_score=faithfulness_score,
            latency_ms=latency_ms,
            num_tokens=total_tokens,
            estimated_cost_usd=cost
        )


def main():
    """Demo the real-time encoder evaluator."""
    evaluator = RealtimeEncoderEvaluator(mock_mode=True)

    # Test cases
    test_cases = [
        {
            "name": "Faithful Response",
            "context": "Amazon S3 is an object storage service offering industry-leading scalability, data availability, security, and performance. It can be used for data lakes, cloud-native applications, and mobile apps.",
            "query": "What is Amazon S3?",
            "response": "Amazon S3 is an object storage service that provides scalability, data availability, security, and performance for data lakes and cloud-native applications."
        },
        {
            "name": "Partially Hallucinated Response",
            "context": "Amazon S3 is an object storage service offering industry-leading scalability, data availability, security, and performance.",
            "query": "What is Amazon S3?",
            "response": "Amazon S3 is an object storage service with built-in quantum encryption that provides scalability and automatic replication across 12 availability zones."
        },
        {
            "name": "Fully Hallucinated Response",
            "context": "Amazon S3 is an object storage service offering industry-leading scalability, data availability, security, and performance.",
            "query": "What is Amazon S3?",
            "response": "Amazon S3 uses blockchain technology for data verification and provides neural network-based compression achieving 100x reduction in storage costs."
        }
    ]

    print("=" * 80)
    print("Real-Time Encoder Evaluator Demo (Mock Mode)")
    print("=" * 80)

    for test in test_cases:
        print(f"\n{test['name']}")
        print("-" * 80)
        print(f"Query: {test['query']}")
        print(f"Response: {test['response']}")

        result = evaluator.evaluate(test['context'], test['query'], test['response'])

        print(f"\nToken-Level Analysis:")
        print(f"  Total Tokens: {result.num_tokens}")
        print(f"  Hallucinated Tokens: {sum(1 for _, is_h, _ in result.token_predictions if is_h)}")

        if result.hallucinated_spans:
            print(f"\nHallucinated Spans:")
            for i, span in enumerate(result.hallucinated_spans, 1):
                print(f"  Span {i}: \"{span.text}\"")
                print(f"    Position: {span.start_idx}-{span.end_idx}")
                print(f"    Confidence: {span.confidence:.3f}")
        else:
            print(f"\n✓ No hallucinated spans detected")

        print(f"\nOverall Results:")
        print(f"  Is Faithful: {result.is_faithful}")
        print(f"  Faithfulness Score: {result.faithfulness_score:.3f}")
        print(f"  Latency: {result.latency_ms:.2f}ms")
        print(f"  Cost: ${result.estimated_cost_usd:.6f}")


if __name__ == "__main__":
    main()
