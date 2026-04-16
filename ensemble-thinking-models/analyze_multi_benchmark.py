#!/usr/bin/env python3
"""
Multi-Benchmark Analysis for E18-E20

Tests whether judge failures generalize beyond math:
- GSM8K: Math problems (objective, verifiable)
- MMLU: Multiple choice knowledge (objective, categorical)
- HumanEval: Code generation (objective, executable)
- GPQA: Graduate science (objective, hard)

Hypothesis:
- If judges fail only on GSM8K: Problem is math-specific
- If judges fail on all benchmarks: Problem is architectural (evaluation harder than generation)
- If judges work on some benchmarks: Problem is task-specific

Key comparisons:
1. E18-E20 vs baselines across each benchmark
2. Judge performance variation by benchmark type
3. Whether correctness-based prompts help (compared to E1/E2 on GSM8K)
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple
import statistics


def load_results(experiment: str, benchmark: str, num_runs: int = 3) -> List[Dict]:
    """Load results for a specific experiment + benchmark combination"""
    results = []
    for run in range(1, num_runs + 1):
        filepath = f'results/phase3_multi/{experiment}_{benchmark}_run{run}.json'
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                results.append(json.load(f))
    return results


def calculate_accuracy(results: List[Dict]) -> Tuple[float, float, List[float]]:
    """Calculate mean, std, and individual accuracies from multiple runs"""
    accuracies = [r['accuracy'] for r in results if 'accuracy' in r]

    if not accuracies:
        return 0.0, 0.0, []

    mean = statistics.mean(accuracies)
    std = statistics.stdev(accuracies) if len(accuracies) > 1 else 0.0

    return mean, std, accuracies


def print_benchmark_section(benchmark: str, experiments: Dict[str, List[Dict]], baselines: Dict[str, float]):
    """Print analysis for a single benchmark"""

    print(f"\n{'='*80}")
    print(f"{benchmark.upper()} Results")
    print(f"{'='*80}\n")

    # Print baseline for context
    baseline = baselines.get(benchmark, 0.0)
    print(f"Baseline (Opus solo): {baseline:.1%}\n")

    # Print experiment results
    results_summary = []

    for exp_name, exp_results in experiments.items():
        if not exp_results:
            continue

        mean_acc, std_acc, individual = calculate_accuracy(exp_results)

        # Calculate delta from baseline
        delta = mean_acc - baseline
        delta_str = f"{delta:+.1%}"

        # Status indicator
        if mean_acc > baseline:
            status = "✓ BETTER"
        elif abs(delta) < 0.02:
            status = "≈ SAME"
        else:
            status = "✗ WORSE"

        results_summary.append({
            'name': exp_name,
            'mean': mean_acc,
            'std': std_acc,
            'individual': individual,
            'delta': delta,
            'status': status
        })

        print(f"{exp_name:30} {mean_acc:6.1%} ± {std_acc:4.1%}  ({delta_str})  {status}")
        print(f"  Individual runs: {', '.join([f'{a:.1%}' for a in individual])}")

    print()

    # Interpretation
    any_better = any(r['delta'] > 0.02 for r in results_summary)
    all_worse = all(r['delta'] < -0.01 for r in results_summary)

    if all_worse:
        print(f"📊 Interpretation: Judges FAIL on {benchmark} (all methods worse than baseline)")
    elif any_better:
        print(f"📊 Interpretation: Some judge methods WORK on {benchmark}")
    else:
        print(f"📊 Interpretation: Judges show MARGINAL effect on {benchmark}")

    return results_summary


def print_cross_benchmark_analysis(all_results: Dict[str, Dict[str, List[Dict]]]):
    """Analyze patterns across benchmarks"""

    print(f"\n{'='*80}")
    print("Cross-Benchmark Analysis")
    print(f"{'='*80}\n")

    # For each experiment, compare performance across benchmarks
    experiments = ['e18', 'e19', 'e20']
    benchmarks = ['gsm8k', 'mmlu', 'humaneval', 'gpqa']

    print("Performance by Experiment:")
    print()

    for exp in experiments:
        print(f"  {exp.upper()}:")
        for bench in benchmarks:
            if bench in all_results and exp in all_results[bench]:
                results = all_results[bench][exp]
                if results:
                    mean_acc, std_acc, _ = calculate_accuracy(results)
                    print(f"    {bench:12} {mean_acc:6.1%} ± {std_acc:4.1%}")
        print()

    # Check if failures are universal or task-specific
    print("\n🔍 Key Questions:")
    print()

    # Question 1: Do judges fail on all benchmarks?
    print("1. Do judges fail on ALL benchmarks?")

    baselines = {
        'gsm8k': 0.847,    # From prior experiments
        'mmlu': 0.75,       # Estimated (need to measure)
        'humaneval': 0.65,  # Estimated (need to measure)
        'gpqa': 0.55        # Estimated (need to measure)
    }

    all_fail = True
    some_succeed = False

    for bench in benchmarks:
        if bench not in all_results:
            continue

        baseline = baselines.get(bench, 0.0)

        for exp in experiments:
            if exp in all_results[bench]:
                results = all_results[bench][exp]
                if results:
                    mean_acc, _, _ = calculate_accuracy(results)
                    if mean_acc > baseline + 0.02:
                        some_succeed = True
                        all_fail = False

    if all_fail:
        print("   → YES: Judge-based ensembles fail across all domains")
        print("   → Conclusion: Problem is ARCHITECTURAL, not task-specific")
    elif some_succeed:
        print("   → NO: Judges succeed on some benchmarks")
        print("   → Conclusion: Task-specific factors matter")
    else:
        print("   → MIXED: Marginal or inconsistent results")

    print()

    # Question 2: Are failures worse on math vs other domains?
    print("2. Is math (GSM8K) uniquely hard for judges?")

    gsm8k_deltas = []
    other_deltas = []

    for bench in benchmarks:
        if bench not in all_results:
            continue

        baseline = baselines.get(bench, 0.0)

        for exp in experiments:
            if exp in all_results[bench]:
                results = all_results[bench][exp]
                if results:
                    mean_acc, _, _ = calculate_accuracy(results)
                    delta = mean_acc - baseline

                    if bench == 'gsm8k':
                        gsm8k_deltas.append(delta)
                    else:
                        other_deltas.append(delta)

    if gsm8k_deltas and other_deltas:
        avg_gsm8k = statistics.mean(gsm8k_deltas)
        avg_other = statistics.mean(other_deltas)

        print(f"   GSM8K average delta: {avg_gsm8k:+.1%}")
        print(f"   Other benchmarks avg delta: {avg_other:+.1%}")

        if avg_gsm8k < avg_other - 0.05:
            print("   → YES: Math is uniquely hard for judges")
        elif abs(avg_gsm8k - avg_other) < 0.03:
            print("   → NO: Similar performance across domains")
        else:
            print("   → UNCLEAR: Need more data")

    print()

    # Question 3: Does correctness-based prompting help?
    print("3. Does correctness-based prompting help (vs agreement-based E1)?")

    # Compare E18 (correctness vote) vs E1 (agreement vote) on GSM8K
    if 'gsm8k' in all_results and 'e18' in all_results['gsm8k']:
        e18_results = all_results['gsm8k']['e18']
        if e18_results:
            e18_mean, _, _ = calculate_accuracy(e18_results)
            e1_accuracy = 0.797  # From prior experiments

            print(f"   E1 (agreement vote):   {e1_accuracy:.1%}")
            print(f"   E18 (correctness vote): {e18_mean:.1%}")
            print(f"   Delta: {e18_mean - e1_accuracy:+.1%}")

            if e18_mean < e1_accuracy:
                print("   → NO: Correctness prompting made it WORSE")
                print("   → Conclusion: Problem is architectural, not prompt-related")
            elif e18_mean > e1_accuracy + 0.02:
                print("   → YES: Correctness prompting helps")
            else:
                print("   → MARGINAL: Small or no improvement")

    print()


def main():
    """Main analysis"""

    print("\n" + "="*80)
    print("Multi-Benchmark Analysis: E18-E20")
    print("Testing: Do judge failures generalize beyond math?")
    print("="*80)

    # Define experiments and benchmarks
    experiments = {
        'e18': 'E18: Correctness Vote',
        'e19': 'E19: Correctness Best-of-N',
        'e20': 'E20: Two-Stage'
    }

    benchmarks = {
        'gsm8k': 'GSM8K-100 (Math)',
        'mmlu': 'MMLU-100 (Knowledge)',
        'humaneval': 'HumanEval-50 (Code)',
        'gpqa': 'GPQA-50 (Science)'
    }

    # Baselines from prior work (Opus solo)
    baselines = {
        'gsm8k': 0.847,
        'mmlu': 0.75,   # TODO: Measure actual baseline
        'humaneval': 0.65,  # TODO: Measure actual baseline
        'gpqa': 0.55   # TODO: Measure actual baseline
    }

    # Load all results
    all_results = {}

    for bench_key, bench_name in benchmarks.items():
        all_results[bench_key] = {}

        for exp_key, exp_name in experiments.items():
            results = load_results(exp_key, bench_key)
            all_results[bench_key][exp_key] = results

    # Print per-benchmark analysis
    for bench_key, bench_name in benchmarks.items():
        exp_results = {
            experiments[exp_key]: all_results[bench_key][exp_key]
            for exp_key in experiments
        }
        print_benchmark_section(bench_name, exp_results, baselines)

    # Cross-benchmark analysis
    print_cross_benchmark_analysis(all_results)

    # Summary
    print("\n" + "="*80)
    print("Summary")
    print("="*80)
    print()
    print("📋 Data collected:")
    total_experiments = 0
    for bench in benchmarks:
        for exp in experiments:
            count = len(all_results.get(bench, {}).get(exp, []))
            total_experiments += count
    print(f"   Total experiment runs: {total_experiments}")
    print()

    print("🎯 Next steps:")
    print("   1. Review results above to determine if failures generalize")
    print("   2. Update BLOG.md and README.md with multi-benchmark findings")
    print("   3. Revise recommendations based on domain-specific insights")
    print()

    # Save summary
    summary = {
        'benchmarks': list(benchmarks.keys()),
        'experiments': list(experiments.keys()),
        'results': all_results,
        'baselines': baselines
    }

    with open('results/phase3_multi/analysis_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print("💾 Detailed summary saved to: results/phase3_multi/analysis_summary.json")
    print()


if __name__ == '__main__':
    main()
