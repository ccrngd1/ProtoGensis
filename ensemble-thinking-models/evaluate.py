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
    # Ground truth evaluation
    has_ground_truth: bool = False
    individual_correctness: Dict[str, bool] = None  # Which models got it right
    vote_correct: bool = False
    stitch_correct: bool = False
    best_individual_correct: bool = False
    ensemble_adds_value: bool = False  # Did ensemble beat best individual?


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

    def _evaluate_against_ground_truth(self, answer: str, ground_truth: str, prompt_id: str) -> bool:
        """
        Evaluate if an answer matches the ground truth.
        Uses keyword matching and pattern detection for different prompt types.
        Returns True if answer appears correct, False otherwise.
        """
        if not ground_truth or not answer:
            return False

        # Normalize for comparison
        answer_lower = answer.lower()
        truth_lower = ground_truth.lower()

        # Check for explicit "no ground truth" statements
        if any(phrase in truth_lower for phrase in [
            "no objective ground truth",
            "no settled law",
            "evaluation should assess"
        ]):
            # Can't evaluate these automatically
            return None

        # Prompt-specific evaluation logic
        if "monty_hall" in prompt_id:
            # Looking for: 3/8 probability for doors 2 and 4
            has_3_8 = "3/8" in answer or "three eighths" in answer_lower
            has_switch = "switch" in answer_lower
            return has_3_8 and has_switch

        elif "mutex" in prompt_id or "deadlock" in prompt_id:
            # Looking for: CAN deadlock (not guaranteed)
            has_can = "can deadlock" in answer_lower or "possible" in answer_lower
            has_not_guaranteed = "not guaranteed" in answer_lower or "not always" in answer_lower or "race condition" in answer_lower
            avoids_will = "will deadlock" not in answer_lower or ("can" in answer_lower and "will" in answer_lower)
            return (has_can or has_not_guaranteed) and avoids_will

        elif "regex" in prompt_id:
            # Looking for: catastrophic backtracking DOES occur
            has_catastrophic = "catastrophic" in answer_lower or "exponential" in answer_lower
            has_backtracking = "backtracking" in answer_lower or "exponential time" in answer_lower
            avoids_instant = not ("instant" in answer_lower and "fail" in answer_lower) or ("catastrophic" in answer_lower)
            return has_catastrophic or (has_backtracking and avoids_instant)

        elif "bayes" in prompt_id or "medical" in prompt_id:
            # Looking for: ~9% probability, friend is correct
            has_low_prob = any(p in answer for p in ["9%", "0.09", "9.09%", "9.0%", "9.016%"])
            has_friend = "friend" in answer_lower and ("correct" in answer_lower or "right" in answer_lower)
            return has_low_prob or has_friend

        elif "time_complexity" in prompt_id:
            # Looking for: Both O(2^n) and O(φ^n) are valid
            has_phi = "φ" in answer or "phi" in answer_lower or "golden ratio" in answer_lower
            has_2n = "o(2^n)" in answer_lower or "o(2**n)" in answer_lower
            has_both = ("both" in answer_lower or "either" in answer_lower) and (has_phi or has_2n)
            return has_both or (has_phi and has_2n)

        elif "sql_injection" in prompt_id:
            # Looking for: security reviewer is correct (but with nuance)
            has_reviewer = "reviewer" in answer_lower and ("correct" in answer_lower or "right" in answer_lower)
            has_vulnerable = "vulnerable" in answer_lower or "unsafe" in answer_lower
            has_param = "parameter" in answer_lower or "prepared statement" in answer_lower
            return has_reviewer or (has_vulnerable and has_param)

        # Default: check if answer contains key phrases from ground truth
        # Extract key phrases (numbers, percentages, specific recommendations)
        import re
        truth_numbers = set(re.findall(r'\d+(?:\.\d+)?%?', truth_lower))
        answer_numbers = set(re.findall(r'\d+(?:\.\d+)?%?', answer_lower))

        # If ground truth has specific numbers, check if answer has them
        if truth_numbers:
            overlap = truth_numbers & answer_numbers
            return len(overlap) >= len(truth_numbers) * 0.5  # At least 50% of numbers match

        # Otherwise, check for key concept words
        truth_words = set(truth_lower.split())
        answer_words = set(answer_lower.split())
        important_words = truth_words - {'the', 'a', 'an', 'is', 'are', 'to', 'of', 'and', 'or', 'but', 'should'}

        if important_words:
            overlap = important_words & answer_words
            return len(overlap) >= len(important_words) * 0.3  # At least 30% of key words

        # If can't determine, return None
        return None

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

            # Check convergence (simple: do all models with valid answers agree?)
            # Only include responses with non-empty answers
            answers = [
                r['answer'][:100].lower()
                for r in responses.values()
                if not r.get('error') and r.get('answer', '').strip()
            ]
            # Rough convergence check (need at least 2 valid answers to compare)
            convergence = len(answers) >= 2 and len(set(answers)) == 1

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

            # Truncate vote and stitch answers properly
            vote_ans = vote_result.get('selected_answer', 'N/A')
            vote_answer_truncated = vote_ans[:150] + ("..." if len(vote_ans) > 150 else "")

            stitch_ans = stitch_result.get('synthesized_answer', 'N/A')
            stitch_answer_truncated = stitch_ans[:150] + ("..." if len(stitch_ans) > 150 else "")

            # Evaluate against ground truth if available
            ground_truth = prompt.get('ground_truth', 'No ground truth')
            has_ground_truth = ground_truth and ground_truth != 'No ground truth'

            individual_correctness = {}
            best_individual_correct = False
            vote_correct = False
            stitch_correct = False
            ensemble_adds_value = False

            if has_ground_truth:
                # Evaluate each individual model
                for model_key in self.model_keys:
                    if model_key in responses and not responses[model_key].get('error'):
                        full_answer = responses[model_key]['answer']
                        is_correct = self._evaluate_against_ground_truth(
                            full_answer, ground_truth, prompt['id']
                        )
                        individual_correctness[model_key] = is_correct
                        if is_correct:
                            best_individual_correct = True

                # Evaluate vote
                vote_correct = self._evaluate_against_ground_truth(
                    vote_ans, ground_truth, prompt['id']
                )

                # Evaluate stitch
                stitch_correct = self._evaluate_against_ground_truth(
                    stitch_ans, ground_truth, prompt['id']
                )

                # Determine if ensemble adds value
                # Ensemble adds value if it's correct when all individuals are wrong,
                # or if it avoids being wrong when individuals are mixed
                ensemble_adds_value = (vote_correct and not best_individual_correct) or \
                                     (stitch_correct and not best_individual_correct)

                # Add to analysis
                if any(v for v in individual_correctness.values() if v is not None):
                    correct_models = [k for k, v in individual_correctness.items() if v]
                    if correct_models:
                        analysis.append(f"Correct: {', '.join(correct_models)}")
                    else:
                        analysis.append("All models incorrect")

                    if vote_correct:
                        analysis.append("Vote: ✓ Correct")
                    elif vote_correct is False:
                        analysis.append("Vote: ✗ Incorrect")

                    if ensemble_adds_value:
                        analysis.append("⭐ Ensemble adds value!")

            comparison = PromptComparison(
                prompt_id=prompt['id'],
                convergence=convergence,
                model_answers=model_answers,
                vote_strategy=vote_result.get('strategy', 'N/A'),
                vote_answer=vote_answer_truncated,
                stitch_answer=stitch_answer_truncated,
                ground_truth=ground_truth,
                analysis=" | ".join(analysis),
                has_ground_truth=has_ground_truth,
                individual_correctness=individual_correctness,
                vote_correct=vote_correct,
                stitch_correct=stitch_correct,
                best_individual_correct=best_individual_correct,
                ensemble_adds_value=ensemble_adds_value
            )

            comparisons.append(comparison)

        return comparisons

    def print_summary(self, metrics: List[EvaluationMetrics], comparisons: List[PromptComparison] = None):
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

        # Add ground truth accuracy analysis
        if comparisons:
            with_ground_truth = [c for c in comparisons if c.has_ground_truth]
            if with_ground_truth:
                print("\n" + "="*100)
                print("GROUND TRUTH ACCURACY ANALYSIS")
                print("="*100)

                # Calculate accuracy for each approach
                evaluable = [c for c in with_ground_truth if c.individual_correctness]

                if evaluable:
                    print(f"\nPrompts with evaluable ground truth: {len(evaluable)}/10")

                    # Individual model accuracy
                    print("\n📊 Individual Model Accuracy:")
                    for model_key in self.model_keys:
                        correct = sum(1 for c in evaluable if c.individual_correctness.get(model_key) is True)
                        total = sum(1 for c in evaluable if c.individual_correctness.get(model_key) is not None)
                        if total > 0:
                            acc = correct / total
                            print(f"   {model_key.capitalize():<10} {correct}/{total} = {acc:.1%}")

                    # Ensemble accuracy
                    print("\n🎯 Ensemble Accuracy:")
                    vote_correct = sum(1 for c in evaluable if c.vote_correct is True)
                    vote_total = sum(1 for c in evaluable if c.vote_correct is not None)
                    if vote_total > 0:
                        vote_acc = vote_correct / vote_total
                        print(f"   Vote:      {vote_correct}/{vote_total} = {vote_acc:.1%}")

                    stitch_correct = sum(1 for c in evaluable if c.stitch_correct is True)
                    stitch_total = sum(1 for c in evaluable if c.stitch_correct is not None)
                    if stitch_total > 0:
                        stitch_acc = stitch_correct / stitch_total
                        print(f"   Stitch:    {stitch_correct}/{stitch_total} = {stitch_acc:.1%}")

                    # Key finding: Does ensemble beat best individual?
                    print("\n⭐ Ensemble Value Analysis:")
                    ensemble_wins = sum(1 for c in evaluable if c.ensemble_adds_value)
                    print(f"   Ensemble beat best individual: {ensemble_wins}/{len(evaluable)} times ({ensemble_wins/len(evaluable)*100:.0f}%)")

                    if ensemble_wins == 0:
                        print("   ⚠️  FINDING: Ensemble never outperformed the best individual model!")
                        print("      On these prompts, using the best individual model alone would be cheaper and equally accurate.")

                    # Show which prompts ensemble added value
                    if ensemble_wins > 0:
                        print("\n   Prompts where ensemble added value:")
                        for c in evaluable:
                            if c.ensemble_adds_value:
                                print(f"      - {c.prompt_id}")

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

        # Calculate ground truth accuracy statistics
        with_ground_truth = [c for c in comparisons if c.has_ground_truth]
        evaluable = [c for c in with_ground_truth if c.individual_correctness]

        ground_truth_analysis = {
            'prompts_with_ground_truth': len(with_ground_truth),
            'prompts_evaluable': len(evaluable)
        }

        if evaluable:
            # Individual accuracy
            individual_accuracy = {}
            for model_key in self.model_keys:
                correct = sum(1 for c in evaluable if c.individual_correctness.get(model_key) is True)
                total = sum(1 for c in evaluable if c.individual_correctness.get(model_key) is not None)
                if total > 0:
                    individual_accuracy[model_key] = {
                        'correct': correct,
                        'total': total,
                        'accuracy': correct / total
                    }

            # Ensemble accuracy
            vote_correct = sum(1 for c in evaluable if c.vote_correct is True)
            vote_total = sum(1 for c in evaluable if c.vote_correct is not None)
            ensemble_accuracy = {
                'vote': {
                    'correct': vote_correct,
                    'total': vote_total,
                    'accuracy': vote_correct / vote_total if vote_total > 0 else 0
                }
            }

            stitch_correct = sum(1 for c in evaluable if c.stitch_correct is True)
            stitch_total = sum(1 for c in evaluable if c.stitch_correct is not None)
            ensemble_accuracy['stitch'] = {
                'correct': stitch_correct,
                'total': stitch_total,
                'accuracy': stitch_correct / stitch_total if stitch_total > 0 else 0
            }

            # Key finding
            ensemble_wins = sum(1 for c in evaluable if c.ensemble_adds_value)
            ground_truth_analysis.update({
                'individual_accuracy': individual_accuracy,
                'ensemble_accuracy': ensemble_accuracy,
                'ensemble_beat_best_individual': ensemble_wins,
                'ensemble_win_rate': ensemble_wins / len(evaluable) if evaluable else 0,
                'conclusion': 'Ensemble adds value' if ensemble_wins > 0 else 'Ensemble does not outperform best individual'
            })

        output = {
            'summary_metrics': [asdict(m) for m in metrics],
            'prompt_comparisons': [asdict(c) for c in comparisons],
            'insights': {
                'convergence_rate': next(m.convergence_rate for m in metrics if 'vote' in m.approach.lower()),
                'cost_ratio_ensemble_vs_best': next(m.total_cost_usd for m in metrics if 'stitch' in m.approach.lower()) /
                                               next(m.total_cost_usd for m in metrics if baseline_model in m.approach.lower()),
                'when_ensembling_helps': 'When models diverge (low convergence), ensemble synthesis can combine best reasoning. When models converge (high agreement), ensemble adds cost without value.',
                'judge_irony': 'If you need a high-quality model as judge to select best response, you could have just used that model directly. Judge quality matters more than ensemble size.'
            },
            'ground_truth_analysis': ground_truth_analysis
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

    evaluator.print_summary(metrics, comparisons)

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
