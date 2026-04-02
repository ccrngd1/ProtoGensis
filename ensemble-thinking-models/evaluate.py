#!/usr/bin/env python3
"""
Evaluation Framework

Compares individual model performance vs ensemble aggregation methods:
- Individual models (dynamically detected from responses)
- Vote aggregation
- Stitch synthesis
- Self-consistency baseline (same model, multiple runs)

Metrics:
- Convergence rate (how often models agree)
- Cost per approach
- Latency per approach
- Quality assessment (where ground truth exists)
"""

import json
import argparse
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class EvaluationMetrics:
    """Metrics for a single approach"""
    approach: str
    total_cost_usd: float
    avg_latency_ms: int
    convergence_rate: float  # 0-1, how often models agreed
    prompts_evaluated: int


@dataclass
class PromptComparison:
    """Comparison data for a single prompt"""
    prompt_id: str
    convergence: bool
    model_answers: Dict[str, str]  # Dynamic model answers
    vote_strategy: str
    vote_answer: str
    stitch_answer: str
    ground_truth: str = None
    analysis: str = ""


class Evaluator:
    """Evaluates and compares ensemble approaches"""

    def __init__(self):
        self.responses = None
        self.vote_results = None
        self.stitch_results = None
        self.prompts_metadata = None
        self.model_keys = None

    def load_data(self, responses_file: str = "results/responses.json",
                  vote_file: str = "results/vote_results.json",
                  stitch_file: str = "results/stitch_results.json",
                  prompts_file: str = "prompts/prompts.json"):
        """Load all results and metadata"""

        with open(responses_file, 'r') as f:
            self.responses = json.load(f)

        with open(vote_file, 'r') as f:
            self.vote_results = json.load(f)

        with open(stitch_file, 'r') as f:
            self.stitch_results = json.load(f)

        with open(prompts_file, 'r') as f:
            prompts_data = json.load(f)
            self.prompts_metadata = {p['id']: p for p in prompts_data['prompts']}

        # Dynamically detect available model keys from responses
        self.model_keys = self._extract_model_keys()

    def _extract_model_keys(self) -> List[str]:
        """Extract available model keys from responses data"""
        if not self.responses or len(self.responses) == 0:
            return []

        # Get model keys from first response item
        first_item = self.responses[0]
        model_keys = list(first_item['responses'].keys())

        print(f"Detected model keys: {model_keys}")
        return model_keys

    def calculate_individual_metrics(self, model_key: str) -> EvaluationMetrics:
        """Calculate metrics for a single model"""

        total_cost = 0.0
        total_latency = 0
        num_prompts = 0

        for item in self.responses:
            response = item['responses'][model_key]
            if not response.get('error'):
                total_cost += response['cost_usd']
                total_latency += response['latency_ms']
                num_prompts += 1

        return EvaluationMetrics(
            approach=f"Individual: {model_key.capitalize()}",
            total_cost_usd=total_cost,
            avg_latency_ms=int(total_latency / num_prompts) if num_prompts > 0 else 0,
            convergence_rate=0.0,  # N/A for individual models
            prompts_evaluated=num_prompts
        )

    def calculate_vote_metrics(self) -> EvaluationMetrics:
        """Calculate metrics for vote aggregation"""

        # Vote cost = cost of all models + optional judge call
        total_model_cost = 0.0
        total_latency = 0
        num_prompts = len(self.responses)
        convergence_count = 0

        for item in self.responses:
            # Cost of running all models
            for model_key in self.model_keys:
                response = item['responses'][model_key]
                if not response.get('error'):
                    total_model_cost += response['cost_usd']

            # Max latency (parallel execution)
            max_latency = max(
                item['responses'][mk]['latency_ms']
                for mk in self.model_keys
                if not item['responses'][mk].get('error')
            )
            total_latency += max_latency

        # Add judge costs for open-ended (estimated)
        for vote_result in self.vote_results:
            if vote_result.get('convergence'):
                convergence_count += 1

            # Judge selection costs ~$0.02 per call (Sonnet)
            if vote_result.get('strategy') == 'judge_selection':
                total_model_cost += 0.02

        convergence_rate = convergence_count / num_prompts if num_prompts > 0 else 0

        return EvaluationMetrics(
            approach="Ensemble: Vote",
            total_cost_usd=total_model_cost,
            avg_latency_ms=int(total_latency / num_prompts) if num_prompts > 0 else 0,
            convergence_rate=convergence_rate,
            prompts_evaluated=num_prompts
        )

    def calculate_stitch_metrics(self) -> EvaluationMetrics:
        """Calculate metrics for stitch synthesis"""

        # Stitch cost = cost of all models + orchestrator synthesis
        total_cost = 0.0
        total_latency = 0
        num_prompts = len(self.responses)

        for i, item in enumerate(self.responses):
            # Cost of running all models
            for model_key in self.model_keys:
                response = item['responses'][model_key]
                if not response.get('error'):
                    total_cost += response['cost_usd']

            # Add synthesis cost
            if i < len(self.stitch_results):
                total_cost += self.stitch_results[i].get('cost_usd', 0.015)

            # Max latency (parallel) + synthesis time (estimated 5s)
            max_latency = max(
                item['responses'][mk]['latency_ms']
                for mk in self.model_keys
                if not item['responses'][mk].get('error')
            )
            total_latency += max_latency + 5000  # Add synthesis time

        # Convergence analysis from stitch results
        convergence_count = sum(
            1 for sr in self.stitch_results
            if 'High convergence' in sr.get('convergence_analysis', '')
        )
        convergence_rate = convergence_count / num_prompts if num_prompts > 0 else 0

        return EvaluationMetrics(
            approach="Ensemble: Stitch",
            total_cost_usd=total_cost,
            avg_latency_ms=int(total_latency / num_prompts) if num_prompts > 0 else 0,
            convergence_rate=convergence_rate,
            prompts_evaluated=num_prompts
        )

    def calculate_self_consistency_metrics(self) -> EvaluationMetrics:
        """
        Calculate metrics for self-consistency baseline.
        This would be: run the first model 3x with temperature > 0, majority vote.
        Using estimated costs/latency based on first model's pricing.
        """

        # Self-consistency = 3x first model calls + voting logic (trivial cost)
        # Use first model (typically the best/most expensive one)
        baseline_model = self.model_keys[0] if self.model_keys else 'opus'
        baseline_metrics = self.calculate_individual_metrics(baseline_model)

        return EvaluationMetrics(
            approach=f"Baseline: Self-Consistency ({baseline_model.capitalize()} 3x)",
            total_cost_usd=baseline_metrics.total_cost_usd * 3,  # 3x runs
            avg_latency_ms=baseline_metrics.avg_latency_ms * 3,  # Sequential or ~1x if parallel
            convergence_rate=0.7,  # Estimated (would need actual test)
            prompts_evaluated=baseline_metrics.prompts_evaluated
        )

    def generate_comparison_matrix(self) -> List[EvaluationMetrics]:
        """Generate comparison across all approaches"""

        metrics = []

        # Individual models
        for model_key in self.model_keys:
            metrics.append(self.calculate_individual_metrics(model_key))

        # Ensemble approaches
        metrics.append(self.calculate_vote_metrics())
        metrics.append(self.calculate_stitch_metrics())

        # Baseline
        metrics.append(self.calculate_self_consistency_metrics())

        return metrics

    def generate_prompt_comparisons(self) -> List[PromptComparison]:
        """Generate per-prompt comparison data"""

        comparisons = []

        for i, item in enumerate(self.responses):
            prompt = item['prompt']
            responses = item['responses']

            # Check convergence (simple: do all 3 agree?)
            answers = [r['answer'][:100].lower() for r in responses.values() if not r.get('error')]
            # Rough convergence check
            convergence = len(set(answers)) == 1

            # Get vote and stitch results
            vote_result = self.vote_results[i] if i < len(self.vote_results) else {}
            stitch_result = self.stitch_results[i] if i < len(self.stitch_results) else {}

            # Analysis
            analysis = []
            if convergence:
                analysis.append("✓ All models converged on similar answer")
            else:
                analysis.append("✗ Models diverged")

            if vote_result.get('strategy') == 'majority_vote':
                analysis.append("Vote: Used majority voting (discrete answer)")
            else:
                analysis.append("Vote: Required judge selection (open-ended)")

            stitch_convergence = stitch_result.get('convergence_analysis', '')
            if 'High convergence' in stitch_convergence:
                analysis.append("Stitch: High agreement across models")
            elif 'Low convergence' in stitch_convergence:
                analysis.append("Stitch: Low agreement, synthesis adds value")

            # Build model_answers dynamically
            model_answers = {}
            for model_key in self.model_keys:
                if model_key in responses and not responses[model_key].get('error'):
                    answer = responses[model_key]['answer']
                    model_answers[model_key] = answer[:150] + ("..." if len(answer) > 150 else "")
                else:
                    model_answers[model_key] = "ERROR"

            comparison = PromptComparison(
                prompt_id=prompt['id'],
                convergence=convergence,
                model_answers=model_answers,
                vote_strategy=vote_result.get('strategy', 'N/A'),
                vote_answer=vote_result.get('selected_answer', 'N/A')[:150] + "...",
                stitch_answer=stitch_result.get('synthesized_answer', 'N/A')[:150] + "...",
                ground_truth=prompt.get('ground_truth', 'No ground truth'),
                analysis=" | ".join(analysis)
            )

            comparisons.append(comparison)

        return comparisons

    def print_summary(self, metrics: List[EvaluationMetrics]):
        """Print evaluation summary"""

        print("\n" + "="*100)
        print("EVALUATION SUMMARY")
        print("="*100)

        # Print table header
        print(f"\n{'Approach':<40} {'Cost ($)':<12} {'Latency (ms)':<15} {'Convergence':<12} {'Prompts':<10}")
        print("-"*100)

        # Print each approach
        for m in metrics:
            conv_str = f"{m.convergence_rate:.1%}" if m.convergence_rate > 0 else "N/A"
            print(f"{m.approach:<40} ${m.total_cost_usd:<11.6f} {m.avg_latency_ms:<15} {conv_str:<12} {m.prompts_evaluated:<10}")

        print("-"*100)

        # Key insights
        print("\nKEY INSIGHTS:")

        # Find cheapest and most expensive
        cheapest = min(metrics, key=lambda m: m.total_cost_usd)
        most_expensive = max(metrics, key=lambda m: m.total_cost_usd)

        print(f"\n💰 Cost Analysis:")
        print(f"   Cheapest: {cheapest.approach} (${cheapest.total_cost_usd:.6f})")
        print(f"   Most expensive: {most_expensive.approach} (${most_expensive.total_cost_usd:.6f})")
        if cheapest.total_cost_usd > 0:
            print(f"   Ratio: {most_expensive.total_cost_usd / cheapest.total_cost_usd:.1f}x more expensive")
        else:
            print(f"   Ratio: N/A (cheapest has zero cost)")

        # Compare ensemble vs best individual (first model)
        baseline_model = self.model_keys[0] if self.model_keys else 'opus'
        baseline_cost = next(m.total_cost_usd for m in metrics if baseline_model in m.approach.lower())
        vote_cost = next(m.total_cost_usd for m in metrics if 'vote' in m.approach.lower())
        stitch_cost = next(m.total_cost_usd for m in metrics if 'stitch' in m.approach.lower())

        print(f"\n🎯 Ensemble Premium:")
        print(f"   Vote vs {baseline_model.capitalize()} alone: {vote_cost / baseline_cost:.2f}x cost")
        print(f"   Stitch vs {baseline_model.capitalize()} alone: {stitch_cost / baseline_cost:.2f}x cost")

        # Convergence insights
        vote_metrics = next(m for m in metrics if 'vote' in m.approach.lower())
        print(f"\n🔄 Convergence:")
        print(f"   Models agreed: {vote_metrics.convergence_rate:.1%} of prompts")
        print(f"   Implication: Ensembling adds most value on the {1-vote_metrics.convergence_rate:.1%} where models diverge")

        print("\n" + "="*100)

    def save_results(self, metrics: List[EvaluationMetrics],
                     comparisons: List[PromptComparison],
                     output_file: str = "results/evaluation.json"):
        """Save evaluation results"""

        # Use first model as baseline for comparison
        baseline_model = self.model_keys[0] if self.model_keys else 'opus'

        output = {
            'summary_metrics': [asdict(m) for m in metrics],
            'prompt_comparisons': [asdict(c) for c in comparisons],
            'insights': {
                'convergence_rate': next(m.convergence_rate for m in metrics if 'vote' in m.approach.lower()),
                'cost_ratio_ensemble_vs_best': next(m.total_cost_usd for m in metrics if 'stitch' in m.approach.lower()) /
                                               next(m.total_cost_usd for m in metrics if baseline_model in m.approach.lower()),
                'when_ensembling_helps': 'When models diverge (low convergence), ensemble synthesis can combine best reasoning. When models converge (high agreement), ensemble adds cost without value.',
                'judge_irony': 'If you need a high-quality model as judge to select best response, you could have just used that model directly. Judge quality matters more than ensemble size.'
            }
        }

        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"✓ Evaluation results saved to {output_file}")


def main():
    """Main evaluation entry point"""

    parser = argparse.ArgumentParser(description='Evaluate ensemble thinking model results')
    parser.add_argument('--responses', default='results/responses.json',
                        help='Path to responses JSON file (default: results/responses.json)')
    parser.add_argument('--vote', default='results/vote_results.json',
                        help='Path to vote results JSON file (default: results/vote_results.json)')
    parser.add_argument('--stitch', default='results/stitch_results.json',
                        help='Path to stitch results JSON file (default: results/stitch_results.json)')
    parser.add_argument('--prompts', default='prompts/prompts.json',
                        help='Path to prompts JSON file (default: prompts/prompts.json)')
    parser.add_argument('--output', default='results/evaluation.json',
                        help='Path to output evaluation JSON file (default: results/evaluation.json)')

    args = parser.parse_args()

    evaluator = Evaluator()

    print("Loading data...")
    evaluator.load_data(
        responses_file=args.responses,
        vote_file=args.vote,
        stitch_file=args.stitch,
        prompts_file=args.prompts
    )

    print("Calculating metrics...")
    metrics = evaluator.generate_comparison_matrix()
    comparisons = evaluator.generate_prompt_comparisons()

    evaluator.print_summary(metrics)

    print(f"\nGenerating detailed prompt comparisons...")
    print(f"Analyzed {len(comparisons)} prompts")

    evaluator.save_results(metrics, comparisons, output_file=args.output)

    # Print a few example comparisons
    print(f"\n{'='*100}")
    print("EXAMPLE PROMPT COMPARISONS")
    print("="*100)

    for comp in comparisons[:3]:
        print(f"\n{comp.prompt_id}:")
        print(f"  Convergence: {comp.convergence}")
        print(f"  Vote strategy: {comp.vote_strategy}")
        print(f"  Analysis: {comp.analysis}")


if __name__ == "__main__":
    main()
