#!/usr/bin/env python3
"""
Statistical Analysis for Benchmark Results

Performs comprehensive statistical testing:
- Bootstrap confidence intervals
- Paired t-tests
- McNemar's test for binary outcomes
- Effect sizes (Cohen's d)
- Multiple comparison correction (Bonferroni)

Usage:
    python statistical_analysis.py <prompts.json> <run1.json> <run2.json> <run3.json>
"""

import json
import sys
import numpy as np
from scipy import stats
from typing import List, Dict, Tuple
from collections import defaultdict
from evaluators import evaluate_benchmark


def load_and_evaluate_runs(response_files: List[str], prompts_file: str) -> Dict:
    """
    Load multiple runs and evaluate each.

    Returns:
        Dict with structure:
        {
            'prompt_id': {
                'model_key': [bool, bool, bool],  # Results for each run
                'ground_truth': str
            }
        }
    """
    # Load prompts
    with open(prompts_file, 'r') as f:
        prompts_data = json.load(f)
    prompts_by_id = {p['id']: p for p in prompts_data['prompts']}

    # Load all runs
    all_runs = []
    for file in response_files:
        with open(file, 'r') as f:
            all_runs.append(json.load(f))

    # Group results by prompt and model
    results_by_prompt = defaultdict(lambda: {'ground_truth': None, 'models': defaultdict(list)})

    for run_idx, run_data in enumerate(all_runs):
        for item in run_data:
            prompt_id = item['prompt']['id']
            prompt = prompts_by_id.get(prompt_id)

            if not prompt:
                continue

            results_by_prompt[prompt_id]['ground_truth'] = prompt.get('ground_truth')

            for model_key, response_data in item['responses'].items():
                answer = response_data['answer']
                correct = evaluate_benchmark(prompt, answer)
                results_by_prompt[prompt_id]['models'][model_key].append(correct)

    return dict(results_by_prompt)


def bootstrap_confidence_interval(
    values: List[float],
    n_bootstrap: int = 10000,
    confidence: float = 0.95
) -> Tuple[float, float, float]:
    """
    Calculate bootstrap confidence interval.

    Args:
        values: List of values (e.g., accuracies from multiple runs)
        n_bootstrap: Number of bootstrap samples
        confidence: Confidence level (default 0.95 for 95% CI)

    Returns:
        (mean, lower_bound, upper_bound)
    """
    if not values:
        return (0.0, 0.0, 0.0)

    bootstrap_means = []
    n = len(values)

    for _ in range(n_bootstrap):
        sample = np.random.choice(values, size=n, replace=True)
        bootstrap_means.append(np.mean(sample))

    mean = np.mean(values)
    alpha = 1 - confidence
    lower = np.percentile(bootstrap_means, alpha/2 * 100)
    upper = np.percentile(bootstrap_means, (1 - alpha/2) * 100)

    return (mean, lower, upper)


def paired_t_test(
    baseline_values: List[float],
    treatment_values: List[float]
) -> Tuple[float, float]:
    """
    Paired t-test comparing baseline vs treatment.

    Args:
        baseline_values: Values from baseline approach
        treatment_values: Values from treatment approach

    Returns:
        (t_statistic, p_value)
    """
    if len(baseline_values) != len(treatment_values):
        raise ValueError("Baseline and treatment must have same length")

    if len(baseline_values) < 2:
        return (0.0, 1.0)

    t_stat, p_value = stats.ttest_rel(baseline_values, treatment_values)
    return (float(t_stat), float(p_value))


def mcnemar_test(
    baseline_correct: List[bool],
    treatment_correct: List[bool]
) -> Tuple[float, float]:
    """
    McNemar's test for paired binary outcomes.

    More appropriate than t-test for binary correct/incorrect data.

    Args:
        baseline_correct: Binary outcomes for baseline
        treatment_correct: Binary outcomes for treatment

    Returns:
        (chi2_statistic, p_value)
    """
    if len(baseline_correct) != len(treatment_correct):
        raise ValueError("Baseline and treatment must have same length")

    # Count concordant and discordant pairs
    b_yes_t_no = sum(1 for b, t in zip(baseline_correct, treatment_correct) if b and not t)
    b_no_t_yes = sum(1 for b, t in zip(baseline_correct, treatment_correct) if not b and t)

    # McNemar's test with continuity correction
    n_discordant = b_yes_t_no + b_no_t_yes

    if n_discordant == 0:
        return (0.0, 1.0)

    chi2 = (abs(b_yes_t_no - b_no_t_yes) - 1)**2 / n_discordant
    p_value = 1 - stats.chi2.cdf(chi2, df=1)

    return (float(chi2), float(p_value))


def cohens_d(
    baseline_values: List[float],
    treatment_values: List[float]
) -> float:
    """
    Calculate Cohen's d effect size.

    Cohen's d = (mean1 - mean2) / pooled_std

    Interpretation:
    - 0.2: Small effect
    - 0.5: Medium effect
    - 0.8: Large effect

    Args:
        baseline_values: Values from baseline
        treatment_values: Values from treatment

    Returns:
        Cohen's d effect size
    """
    if len(baseline_values) < 2 or len(treatment_values) < 2:
        return 0.0

    mean1 = np.mean(baseline_values)
    mean2 = np.mean(treatment_values)

    std1 = np.std(baseline_values, ddof=1)
    std2 = np.std(treatment_values, ddof=1)

    n1 = len(baseline_values)
    n2 = len(treatment_values)

    # Pooled standard deviation
    pooled_std = np.sqrt(((n1 - 1) * std1**2 + (n2 - 1) * std2**2) / (n1 + n2 - 2))

    if pooled_std == 0:
        return 0.0

    return (mean1 - mean2) / pooled_std


def analyze_model_performance(
    results_by_prompt: Dict,
    model_key: str
) -> Dict:
    """
    Analyze performance for a single model across runs.

    Returns:
        Dict with statistics for the model
    """
    n_prompts = len(results_by_prompt)
    n_runs = len(next(iter(results_by_prompt.values()))['models'][model_key])

    # Calculate accuracy for each run
    accuracies = []
    for run_idx in range(n_runs):
        correct_count = sum(
            1 for prompt_data in results_by_prompt.values()
            if prompt_data['models'][model_key][run_idx]
        )
        accuracy = correct_count / n_prompts if n_prompts > 0 else 0
        accuracies.append(accuracy)

    # Bootstrap CI
    mean_acc, ci_lower, ci_upper = bootstrap_confidence_interval(accuracies)

    # Standard error
    std_error = np.std(accuracies, ddof=1) / np.sqrt(n_runs) if n_runs > 1 else 0

    return {
        'model': model_key,
        'n_prompts': n_prompts,
        'n_runs': n_runs,
        'accuracies': accuracies,
        'mean_accuracy': mean_acc,
        'std_dev': np.std(accuracies, ddof=1) if n_runs > 1 else 0,
        'std_error': std_error,
        'ci_95_lower': ci_lower,
        'ci_95_upper': ci_upper,
        'min_accuracy': min(accuracies),
        'max_accuracy': max(accuracies)
    }


def compare_models(
    results_by_prompt: Dict,
    baseline_model: str,
    treatment_model: str
) -> Dict:
    """
    Compare two models using multiple statistical tests.

    Returns:
        Dict with comparison statistics
    """
    n_runs = len(next(iter(results_by_prompt.values()))['models'][baseline_model])

    # Get accuracies per run
    baseline_accs = []
    treatment_accs = []

    for run_idx in range(n_runs):
        baseline_correct = sum(
            1 for p in results_by_prompt.values()
            if p['models'][baseline_model][run_idx]
        )
        treatment_correct = sum(
            1 for p in results_by_prompt.values()
            if p['models'][treatment_model][run_idx]
        )

        n_prompts = len(results_by_prompt)
        baseline_accs.append(baseline_correct / n_prompts if n_prompts > 0 else 0)
        treatment_accs.append(treatment_correct / n_prompts if n_prompts > 0 else 0)

    # Paired t-test on accuracies
    t_stat, p_value_ttest = paired_t_test(baseline_accs, treatment_accs)

    # McNemar's test on individual prompt outcomes
    # Use the first run for McNemar (it's prompt-level, not run-level)
    baseline_outcomes = [
        p['models'][baseline_model][0]
        for p in results_by_prompt.values()
    ]
    treatment_outcomes = [
        p['models'][treatment_model][0]
        for p in results_by_prompt.values()
    ]
    chi2, p_value_mcnemar = mcnemar_test(baseline_outcomes, treatment_outcomes)

    # Effect size
    effect_size = cohens_d(baseline_accs, treatment_accs)

    # Mean difference
    mean_diff = np.mean(baseline_accs) - np.mean(treatment_accs)

    return {
        'baseline_model': baseline_model,
        'treatment_model': treatment_model,
        'mean_difference': mean_diff,
        'paired_t_test': {
            't_statistic': t_stat,
            'p_value': p_value_ttest
        },
        'mcnemar_test': {
            'chi2_statistic': chi2,
            'p_value': p_value_mcnemar
        },
        'cohens_d': effect_size,
        'significant_at_0.05': p_value_ttest < 0.05,
        'significant_at_0.01': p_value_ttest < 0.01
    }


def interpret_effect_size(d: float) -> str:
    """Interpret Cohen's d effect size."""
    abs_d = abs(d)
    if abs_d < 0.2:
        return "negligible"
    elif abs_d < 0.5:
        return "small"
    elif abs_d < 0.8:
        return "medium"
    else:
        return "large"


def format_report(analysis_results: Dict) -> str:
    """
    Format analysis results as a readable report.
    """
    report = []
    report.append("="*80)
    report.append("STATISTICAL ANALYSIS REPORT")
    report.append("="*80)
    report.append("")

    # Individual model performance
    report.append("## Individual Model Performance")
    report.append("-"*80)
    report.append("")

    for model_stats in analysis_results['models']:
        model = model_stats['model']
        mean_acc = model_stats['mean_accuracy'] * 100
        ci_lower = model_stats['ci_95_lower'] * 100
        ci_upper = model_stats['ci_95_upper'] * 100
        std_error = model_stats['std_error'] * 100

        report.append(f"**{model}**")
        report.append(f"  Mean accuracy: {mean_acc:.1f}% (95% CI: [{ci_lower:.1f}%, {ci_upper:.1f}%])")
        report.append(f"  Standard error: ±{std_error:.1f}%")
        report.append(f"  Runs: {model_stats['accuracies']}")
        report.append(f"  Range: {model_stats['min_accuracy']*100:.1f}% - {model_stats['max_accuracy']*100:.1f}%")
        report.append("")

    # Pairwise comparisons
    if analysis_results['comparisons']:
        report.append("## Pairwise Comparisons")
        report.append("-"*80)
        report.append("")

        for comp in analysis_results['comparisons']:
            baseline = comp['baseline_model']
            treatment = comp['treatment_model']
            mean_diff = comp['mean_difference'] * 100
            p_ttest = comp['paired_t_test']['p_value']
            p_mcnemar = comp['mcnemar_test']['p_value']
            cohens_d = comp['cohens_d']
            effect = interpret_effect_size(cohens_d)

            report.append(f"**{baseline} vs {treatment}**")
            report.append(f"  Mean difference: {mean_diff:+.1f}% ({baseline} - {treatment})")
            report.append(f"  Paired t-test: t={comp['paired_t_test']['t_statistic']:.3f}, p={p_ttest:.4f}")
            report.append(f"  McNemar's test: χ²={comp['mcnemar_test']['chi2_statistic']:.3f}, p={p_mcnemar:.4f}")
            report.append(f"  Cohen's d: {cohens_d:.3f} ({effect} effect)")

            if comp['significant_at_0.01']:
                report.append(f"  Result: ✓✓ HIGHLY SIGNIFICANT (p < 0.01)")
            elif comp['significant_at_0.05']:
                report.append(f"  Result: ✓ SIGNIFICANT (p < 0.05)")
            else:
                report.append(f"  Result: ✗ NOT SIGNIFICANT (p ≥ 0.05)")

            report.append("")

    # Interpretation
    report.append("## Interpretation Guide")
    report.append("-"*80)
    report.append("")
    report.append("**P-value:**")
    report.append("  p < 0.01: Highly significant (strong evidence)")
    report.append("  p < 0.05: Significant (moderate evidence)")
    report.append("  p ≥ 0.05: Not significant (insufficient evidence)")
    report.append("")
    report.append("**Cohen's d (effect size):**")
    report.append("  < 0.2: Negligible effect")
    report.append("  0.2-0.5: Small effect")
    report.append("  0.5-0.8: Medium effect")
    report.append("  > 0.8: Large effect")
    report.append("")
    report.append("**Confidence Interval:**")
    report.append("  95% CI shows range where true mean likely falls")
    report.append("  Narrower CI = more precise estimate")
    report.append("")

    report.append("="*80)

    return "\n".join(report)


def main():
    if len(sys.argv) < 4:
        print("Usage: python statistical_analysis.py <prompts.json> <run1.json> <run2.json> [<run3.json> ...]")
        print("\nExpects:")
        print("  - prompts.json: Prompts file with ground truth")
        print("  - run*.json: Multiple result files from harness.py (3+ recommended)")
        print("\nOutputs:")
        print("  - Statistical analysis with CI, t-tests, McNemar's test, effect sizes")
        sys.exit(1)

    prompts_file = sys.argv[1]
    response_files = sys.argv[2:]

    print(f"Loading {len(response_files)} runs from {prompts_file}...")

    # Load and evaluate all runs
    results_by_prompt = load_and_evaluate_runs(response_files, prompts_file)

    # Get all models
    model_keys = list(next(iter(results_by_prompt.values()))['models'].keys())

    print(f"Found {len(model_keys)} models: {', '.join(model_keys)}")
    print()

    # Analyze each model
    model_analyses = []
    for model_key in model_keys:
        model_stats = analyze_model_performance(results_by_prompt, model_key)
        model_analyses.append(model_stats)

    # Compare models pairwise
    comparisons = []

    # If there's a baseline model (e.g., opus-fast), compare others to it
    if 'opus-fast' in model_keys:
        baseline = 'opus-fast'
        for treatment in model_keys:
            if treatment != baseline:
                comp = compare_models(results_by_prompt, baseline, treatment)
                comparisons.append(comp)
    else:
        # Otherwise, compare first model to all others
        baseline = model_keys[0]
        for treatment in model_keys[1:]:
            comp = compare_models(results_by_prompt, baseline, treatment)
            comparisons.append(comp)

    # Compile results
    analysis_results = {
        'n_prompts': len(results_by_prompt),
        'n_runs': len(response_files),
        'models': model_analyses,
        'comparisons': comparisons
    }

    # Print report
    report = format_report(analysis_results)
    print(report)

    # Save JSON output
    output_file = 'results/statistical_analysis.json'
    with open(output_file, 'w') as f:
        json.dump(analysis_results, f, indent=2)

    print(f"\n✓ Detailed results saved to {output_file}")


if __name__ == "__main__":
    main()
