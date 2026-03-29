"""
NLI Claims Evaluator - DeBERTa-based claim verification.
Decomposes response into claims and checks each via NLI cross-encoder on SageMaker.
"""

import json
import time
import re
import random
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from config import settings


@dataclass
class ClaimVerification:
    """Verification result for a single claim."""
    claim: str
    entailment_score: float  # Probability of entailment
    neutral_score: float
    contradiction_score: float
    verdict: str  # "entailed", "neutral", or "contradiction"


@dataclass
class NLIClaimsResult:
    """Result from NLI claims evaluation."""
    claims: List[ClaimVerification]
    faithfulness_score: float  # Minimum claim entailment score
    avg_entailment_score: float
    latency_ms: float
    num_claims: int
    estimated_cost_usd: float


class NLIClaimsEvaluator:
    """
    NLI-based claims evaluator using DeBERTa cross-encoder on SageMaker.

    This approach:
    1. Decomposes the response into individual claims (sentences)
    2. Checks each claim against the context via NLI
    3. Reports the minimum entailment score (weakest link)
    """

    def __init__(self, mock_mode: bool = None):
        """
        Initialize NLI claims evaluator.

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

    def evaluate(self, context: str, query: str, response: str) -> NLIClaimsResult:
        """
        Evaluate RAG response faithfulness using NLI claim verification.

        Args:
            context: Retrieved context chunks
            query: User query
            response: Generated response to evaluate

        Returns:
            NLIClaimsResult with claim-level scores and overall faithfulness
        """
        start_time = time.time()

        # Step 1: Decompose response into claims
        claims = self._decompose_into_claims(response)

        # Step 2: Verify each claim against context
        verifications = []
        for claim in claims:
            verification = self._verify_claim(context, claim)
            verifications.append(verification)

        latency_ms = (time.time() - start_time) * 1000

        # Step 3: Calculate overall faithfulness
        if verifications:
            entailment_scores = [v.entailment_score for v in verifications]
            faithfulness_score = min(entailment_scores)  # Weakest link
            avg_entailment_score = sum(entailment_scores) / len(entailment_scores)
        else:
            faithfulness_score = 1.0  # Empty response is trivially faithful
            avg_entailment_score = 1.0

        # Estimate cost (SageMaker compute time)
        cost = self._calculate_cost(latency_ms)

        return NLIClaimsResult(
            claims=verifications,
            faithfulness_score=faithfulness_score,
            avg_entailment_score=avg_entailment_score,
            latency_ms=latency_ms,
            num_claims=len(claims),
            estimated_cost_usd=cost
        )

    def _decompose_into_claims(self, response: str) -> List[str]:
        """
        Decompose response into individual claims.

        For simplicity, we use sentence splitting. In production,
        this could use an LLM to extract atomic claims.
        """
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+', response)
        claims = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        return claims

    def _verify_claim(self, context: str, claim: str) -> ClaimVerification:
        """
        Verify a single claim against context using NLI.

        Args:
            context: The premise (retrieved context)
            claim: The hypothesis (claim to verify)

        Returns:
            ClaimVerification with NLI scores
        """
        if self.mock_mode:
            return self._mock_verify_claim(context, claim)

        # Prepare input for DeBERTa NLI model
        # Format: premise [SEP] hypothesis
        nli_input = {
            "inputs": f"{context} [SEP] {claim}"
        }

        try:
            response = self.sagemaker_runtime.invoke_endpoint(
                EndpointName=settings.sagemaker_nli_endpoint,
                ContentType='application/json',
                Body=json.dumps(nli_input)
            )

            result = json.loads(response['Body'].read().decode())

            # Parse NLI scores
            # Expected format: [{"label": "entailment", "score": 0.9}, ...]
            scores = {"entailment": 0.0, "neutral": 0.0, "contradiction": 0.0}
            for item in result:
                label = item['label'].lower()
                if label in scores:
                    scores[label] = item['score']

            entailment_score = scores['entailment']
            verdict = max(scores, key=scores.get)

            return ClaimVerification(
                claim=claim,
                entailment_score=entailment_score,
                neutral_score=scores['neutral'],
                contradiction_score=scores['contradiction'],
                verdict=verdict
            )

        except ClientError as e:
            raise Exception(f"SageMaker NLI inference failed: {e}")

    def _mock_verify_claim(self, context: str, claim: str) -> ClaimVerification:
        """Mock NLI verification for testing without AWS."""
        # Simulate NLI inference latency (2-5ms per claim)
        time.sleep(random.uniform(0.002, 0.005))

        # Simple heuristic: word overlap
        claim_words = set(claim.lower().split())
        context_words = set(context.lower().split())
        overlap = len(claim_words & context_words)
        total = len(claim_words)

        if total > 0:
            overlap_ratio = overlap / total
            # Map overlap to entailment probability
            entailment_score = min(1.0, overlap_ratio + random.uniform(-0.1, 0.1))
            entailment_score = max(0.0, entailment_score)
        else:
            entailment_score = 0.5

        # Distribute remaining probability
        remaining = 1.0 - entailment_score
        neutral_score = remaining * random.uniform(0.4, 0.7)
        contradiction_score = remaining - neutral_score

        scores = {
            "entailment": entailment_score,
            "neutral": neutral_score,
            "contradiction": contradiction_score
        }
        verdict = max(scores, key=scores.get)

        return ClaimVerification(
            claim=claim,
            entailment_score=entailment_score,
            neutral_score=neutral_score,
            contradiction_score=contradiction_score,
            verdict=verdict
        )

    def _calculate_cost(self, latency_ms: float) -> float:
        """Calculate estimated cost based on compute time."""
        # SageMaker ml.g5.xlarge at ~$1.41/hr = $0.000392/sec
        compute_seconds = latency_ms / 1000
        return compute_seconds * settings.sagemaker_compute_cost_per_sec


def main():
    """Demo the NLI claims evaluator."""
    evaluator = NLIClaimsEvaluator(mock_mode=True)

    # Test cases
    test_cases = [
        {
            "name": "Faithful Response",
            "context": "Amazon S3 is an object storage service offering industry-leading scalability, data availability, security, and performance. It can be used for data lakes, cloud-native applications, and mobile apps.",
            "query": "What is Amazon S3?",
            "response": "Amazon S3 is an object storage service that provides scalability, data availability, security, and performance. It is commonly used for data lakes and cloud-native applications."
        },
        {
            "name": "Partially Hallucinated Response",
            "context": "Amazon S3 is an object storage service offering industry-leading scalability, data availability, security, and performance.",
            "query": "What is Amazon S3?",
            "response": "Amazon S3 is an object storage service that provides scalability and security. It also includes built-in machine learning capabilities for automatic data classification."
        },
        {
            "name": "Fully Hallucinated Response",
            "context": "Amazon S3 is an object storage service offering industry-leading scalability, data availability, security, and performance.",
            "query": "What is Amazon S3?",
            "response": "Amazon S3 uses quantum encryption and provides 99.99999% durability with automatic replication across 12 availability zones worldwide."
        }
    ]

    print("=" * 80)
    print("NLI Claims Evaluator Demo (Mock Mode)")
    print("=" * 80)

    for test in test_cases:
        print(f"\n{test['name']}")
        print("-" * 80)
        print(f"Query: {test['query']}")
        print(f"Response: {test['response']}")

        result = evaluator.evaluate(test['context'], test['query'], test['response'])

        print(f"\nClaim-by-Claim Verification:")
        for i, claim_result in enumerate(result.claims, 1):
            print(f"  Claim {i}: {claim_result.claim}")
            print(f"    Entailment: {claim_result.entailment_score:.3f} | "
                  f"Neutral: {claim_result.neutral_score:.3f} | "
                  f"Contradiction: {claim_result.contradiction_score:.3f}")
            print(f"    Verdict: {claim_result.verdict}")

        print(f"\nOverall Results:")
        print(f"  Faithfulness Score (min): {result.faithfulness_score:.3f}")
        print(f"  Average Entailment: {result.avg_entailment_score:.3f}")
        print(f"  Number of Claims: {result.num_claims}")
        print(f"  Latency: {result.latency_ms:.2f}ms")
        print(f"  Cost: ${result.estimated_cost_usd:.6f}")


if __name__ == "__main__":
    main()
