"""
Comparison runner - evaluates all three approaches on the same test dataset.
Tracks accuracy, latency, and cost for head-to-head comparison.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from tqdm import tqdm

from config import settings, DATA_DIR
from evaluators import LLMJudgeEvaluator, NLIClaimsEvaluator, RealtimeEncoderEvaluator


@dataclass
class ComparisonResult:
    """Result from comparing all three evaluators on one test case."""
    test_id: int
    query: str
    response: str
    ground_truth_label: str

    # LLM-as-judge results
    llm_judge_score: float
    llm_judge_latency_ms: float
    llm_judge_cost_usd: float

    # NLI claims results
    nli_claims_score: float
    nli_claims_latency_ms: float
    nli_claims_cost_usd: float
    nli_num_claims: int

    # Real-time encoder results
    encoder_score: float
    encoder_latency_ms: float
    encoder_cost_usd: float
    encoder_num_spans: int


@dataclass
class AggregateMetrics:
    """Aggregate metrics across all test cases."""
    evaluator_name: str
    total_test_cases: int

    # Latency stats
    avg_latency_ms: float
    median_latency_ms: float
    p95_latency_ms: float

    # Cost stats
    total_cost_usd: float
    avg_cost_per_eval_usd: float

    # Accuracy stats (correlation with ground truth)
    accuracy_faithful: float  # % correctly identified faithful responses
    accuracy_hallucinated: float  # % correctly identified hallucinated responses
    overall_accuracy: float

    # Score distribution
    avg_score: float
    score_std_dev: float


class ComparisonRunner:
    """Runs all three evaluators on the same dataset for comparison."""

    def __init__(self, mock_mode: bool = None):
        """
        Initialize comparison runner.

        Args:
            mock_mode: If True, use mock mode for all evaluators
        """
        self.mock_mode = mock_mode if mock_mode is not None else settings.mock_mode

        self.llm_judge = LLMJudgeEvaluator(mock_mode=self.mock_mode)
        self.nli_claims = NLIClaimsEvaluator(mock_mode=self.mock_mode)
        self.encoder = RealtimeEncoderEvaluator(mock_mode=self.mock_mode)

    def load_test_cases(self, test_file: str = "test_cases.json") -> List[Dict]:
        """Load test cases from data directory."""
        test_path = DATA_DIR / test_file
        with open(test_path, 'r') as f:
            return json.load(f)

    def evaluate_single_case(self, test_case: Dict) -> ComparisonResult:
        """
        Evaluate a single test case with all three evaluators.

        Args:
            test_case: Test case dict with query, context, response, label

        Returns:
            ComparisonResult with all three evaluations
        """
        context = test_case['context']
        query = test_case['query']
        response = test_case['response']

        # Run all three evaluators
        llm_result = self.llm_judge.evaluate(context, query, response)
        nli_result = self.nli_claims.evaluate(context, query, response)
        encoder_result = self.encoder.evaluate(context, query, response)

        return ComparisonResult(
            test_id=test_case['id'],
            query=query,
            response=response,
            ground_truth_label=test_case['label'],
            llm_judge_score=llm_result.faithfulness_score,
            llm_judge_latency_ms=llm_result.latency_ms,
            llm_judge_cost_usd=llm_result.estimated_cost_usd,
            nli_claims_score=nli_result.faithfulness_score,
            nli_claims_latency_ms=nli_result.latency_ms,
            nli_claims_cost_usd=nli_result.estimated_cost_usd,
            nli_num_claims=nli_result.num_claims,
            encoder_score=encoder_result.faithfulness_score,
            encoder_latency_ms=encoder_result.latency_ms,
            encoder_cost_usd=encoder_result.estimated_cost_usd,
            encoder_num_spans=len(encoder_result.hallucinated_spans)
        )

    def run_comparison(self, limit: int = None) -> List[ComparisonResult]:
        """
        Run comparison on all test cases.

        Args:
            limit: Optional limit on number of test cases to run

        Returns:
            List of ComparisonResult for each test case
        """
        test_cases = self.load_test_cases()

        if limit:
            test_cases = test_cases[:limit]

        results = []
        print(f"\nRunning comparison on {len(test_cases)} test cases...")
        print(f"Mock mode: {self.mock_mode}")

        for test_case in tqdm(test_cases, desc="Evaluating"):
            result = self.evaluate_single_case(test_case)
            results.append(result)

        return results

    def calculate_aggregate_metrics(
        self,
        results: List[ComparisonResult],
        evaluator: str
    ) -> AggregateMetrics:
        """
        Calculate aggregate metrics for a specific evaluator.

        Args:
            results: List of comparison results
            evaluator: "llm_judge", "nli_claims", or "encoder"

        Returns:
            AggregateMetrics with summary statistics
        """
        import numpy as np

        # Extract scores and metrics for this evaluator
        if evaluator == "llm_judge":
            scores = [r.llm_judge_score for r in results]
            latencies = [r.llm_judge_latency_ms for r in results]
            costs = [r.llm_judge_cost_usd for r in results]
        elif evaluator == "nli_claims":
            scores = [r.nli_claims_score for r in results]
            latencies = [r.nli_claims_latency_ms for r in results]
            costs = [r.nli_claims_cost_usd for r in results]
        else:  # encoder
            scores = [r.encoder_score for r in results]
            latencies = [r.encoder_latency_ms for r in results]
            costs = [r.encoder_cost_usd for r in results]

        # Latency stats
        avg_latency = np.mean(latencies)
        median_latency = np.median(latencies)
        p95_latency = np.percentile(latencies, 95)

        # Cost stats
        total_cost = sum(costs)
        avg_cost = np.mean(costs)

        # Accuracy calculation (using 0.5 threshold)
        faithful_results = [r for r in results if r.ground_truth_label == "faithful"]
        hallucinated_results = [r for r in results if r.ground_truth_label in ["partially_hallucinated", "fully_hallucinated"]]

        if evaluator == "llm_judge":
            faithful_correct = sum(1 for r in faithful_results if r.llm_judge_score >= 0.5)
            hallucinated_correct = sum(1 for r in hallucinated_results if r.llm_judge_score < 0.5)
        elif evaluator == "nli_claims":
            faithful_correct = sum(1 for r in faithful_results if r.nli_claims_score >= 0.5)
            hallucinated_correct = sum(1 for r in hallucinated_results if r.nli_claims_score < 0.5)
        else:  # encoder
            faithful_correct = sum(1 for r in faithful_results if r.encoder_score >= 0.5)
            hallucinated_correct = sum(1 for r in hallucinated_results if r.encoder_score < 0.5)

        accuracy_faithful = faithful_correct / len(faithful_results) if faithful_results else 0
        accuracy_hallucinated = hallucinated_correct / len(hallucinated_results) if hallucinated_results else 0
        overall_accuracy = (faithful_correct + hallucinated_correct) / len(results)

        # Score distribution
        avg_score = np.mean(scores)
        score_std_dev = np.std(scores)

        return AggregateMetrics(
            evaluator_name=evaluator,
            total_test_cases=len(results),
            avg_latency_ms=avg_latency,
            median_latency_ms=median_latency,
            p95_latency_ms=p95_latency,
            total_cost_usd=total_cost,
            avg_cost_per_eval_usd=avg_cost,
            accuracy_faithful=accuracy_faithful,
            accuracy_hallucinated=accuracy_hallucinated,
            overall_accuracy=overall_accuracy,
            avg_score=avg_score,
            score_std_dev=score_std_dev
        )

    def save_results(self, results: List[ComparisonResult], output_file: str = "comparison_results.json"):
        """Save comparison results to JSON."""
        output_path = DATA_DIR / output_file
        with open(output_path, 'w') as f:
            json.dump([asdict(r) for r in results], f, indent=2)
        print(f"\nResults saved to: {output_path}")

    def save_aggregate_metrics(self, metrics: Dict[str, AggregateMetrics], output_file: str = "aggregate_metrics.json"):
        """Save aggregate metrics to JSON."""
        output_path = DATA_DIR / output_file
        with open(output_path, 'w') as f:
            json.dump({k: asdict(v) for k, v in metrics.items()}, f, indent=2)
        print(f"Aggregate metrics saved to: {output_path}")


def main():
    """Run the comparison and save results."""
    runner = ComparisonRunner(mock_mode=True)

    print("=" * 80)
    print("RAG Verification Approach Comparison")
    print("=" * 80)
    print(f"\nComparing three approaches:")
    print("  1. LLM-as-Judge (Claude on Bedrock)")
    print("  2. NLI Claims (DeBERTa on SageMaker)")
    print("  3. Real-Time Encoder (Fast & Faithful on SageMaker)")

    # Run comparison
    results = runner.run_comparison()

    # Calculate aggregate metrics for each evaluator
    metrics = {}
    for evaluator in ["llm_judge", "nli_claims", "encoder"]:
        metrics[evaluator] = runner.calculate_aggregate_metrics(results, evaluator)

    # Print summary
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)

    for evaluator, metric in metrics.items():
        print(f"\n{evaluator.upper().replace('_', ' ')}:")
        print(f"  Accuracy: {metric.overall_accuracy:.1%} (Faithful: {metric.accuracy_faithful:.1%}, Hallucinated: {metric.accuracy_hallucinated:.1%})")
        print(f"  Avg Latency: {metric.avg_latency_ms:.2f}ms (p95: {metric.p95_latency_ms:.2f}ms)")
        print(f"  Avg Cost: ${metric.avg_cost_per_eval_usd:.6f} per evaluation")
        print(f"  Total Cost: ${metric.total_cost_usd:.4f} for {metric.total_test_cases} evaluations")

    # Save results
    runner.save_results(results)
    runner.save_aggregate_metrics(metrics)

    print("\n" + "=" * 80)
    print("Comparison complete! Use report.py to generate markdown tables.")
    print("=" * 80)


if __name__ == "__main__":
    main()
