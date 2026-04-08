#!/usr/bin/env python3
"""
Analyze diversity benefit by comparing diverse vs same-model ensembles.
"""

import json
import sys
from pathlib import Path
import numpy as np
from scipy import stats


def analyze_diversity(results_file: str):
    """Compare diverse ensemble vs same-model ensemble."""

    with open(results_file) as f:
        results = json.load(f)

    # Check if judge scores are available
    if not results.get('metadata', {}).get('judge_enabled', False):
        print("❌ Judge scoring is not enabled in this benchmark run.")
        print("   Run benchmark with judge enabled to use this analysis.")
        print("   Command: python benchmark/run.py --output results/benchmark.json")
        return False

    # Get diverse ensemble (ultra-cheap)
    if 'ultra-cheap' not in results.get('ensembles', {}):
        print("❌ 'ultra-cheap' ensemble not found in results.")
        return False

    # Get same-model ensemble
    if 'same-model-baseline' not in results.get('ensembles', {}):
        print("❌ 'same-model-baseline' ensemble not found in results.")
        print("   Make sure to run benchmark with same-model ablation.")
        return False

    diverse = results['ensembles']['ultra-cheap']
    same_model = results['ensembles']['same-model-baseline']

    # Extract quality scores
    diverse_scores = [
        r['judge_score']['total']
        for r in diverse
        if 'judge_score' in r
    ]

    same_scores = [
        r['judge_score']['total']
        for r in same_model
        if 'judge_score' in r
    ]

    if not diverse_scores or not same_scores:
        print("❌ Missing judge scores in results.")
        print("   Ensure both ensembles were scored by judge model.")
        return False

    print("="*60)
    print("DIVERSITY ANALYSIS")
    print("="*60)

    diverse_mean = np.mean(diverse_scores)
    same_mean = np.mean(same_scores)

    diverse_std = np.std(diverse_scores)
    same_std = np.std(same_scores)

    print(f"\nDiverse Ensemble (Nova Lite + Mistral + Llama):")
    print(f"  Quality: {diverse_mean:.1f} ± {diverse_std:.1f}")
    print(f"  Cost: ${results['summary']['ensembles']['ultra-cheap']['avg_cost']:.6f}")
    print(f"  Latency: {results['summary']['ensembles']['ultra-cheap']['avg_latency_ms']:.0f}ms")

    print(f"\nSame-Model Ensemble (3x Nova Lite):")
    print(f"  Quality: {same_mean:.1f} ± {same_std:.1f}")
    print(f"  Cost: ${results['summary']['ensembles']['same-model-baseline']['avg_cost']:.6f}")
    print(f"  Latency: {results['summary']['ensembles']['same-model-baseline']['avg_latency_ms']:.0f}ms")

    # Calculate quality difference
    quality_diff = diverse_mean - same_mean
    print(f"\nQuality Difference: {quality_diff:+.1f} points")

    # Statistical test
    t_stat, p_value = stats.ttest_ind(diverse_scores, same_scores)

    print(f"\nStatistical Test (Independent t-test):")
    print(f"  t-statistic: {t_stat:.3f}")
    print(f"  p-value: {p_value:.4f}")

    if p_value < 0.05:
        if diverse_mean > same_mean:
            print("  ✅ Diverse ensemble is SIGNIFICANTLY better (p<0.05)")
            print("     → Diversity DOES matter!")
        else:
            print("  ⚠️  Same-model is SIGNIFICANTLY better (p<0.05)")
            print("     → Diversity may hurt quality!")
    else:
        print("  ⚠️  No significant difference (p≥0.05)")
        print("     → Diversity may not matter, just aggregation!")

    # Effect size (Cohen's d)
    pooled_std = np.sqrt((diverse_std**2 + same_std**2) / 2)
    cohens_d = (diverse_mean - same_mean) / pooled_std if pooled_std > 0 else 0

    print(f"\nEffect Size (Cohen's d): {cohens_d:.3f}")
    if abs(cohens_d) < 0.2:
        print("  → Small effect size (trivial difference)")
    elif abs(cohens_d) < 0.5:
        print("  → Medium effect size (moderate difference)")
    else:
        print("  → Large effect size (substantial difference)")

    print("\n" + "="*60)

    # Per-category breakdown
    print("\nQuality by Category:")
    print(f"{'Category':15s} {'Diverse':>8s} {'Same-Model':>11s} {'Delta':>8s} {'p-value':>8s}")
    print("-"*60)

    categories = set(r['category'] for r in diverse if 'category' in r)
    category_results = []

    for category in sorted(categories):
        diverse_cat = [
            r['judge_score']['total']
            for r in diverse
            if r.get('category') == category and 'judge_score' in r
        ]
        same_cat = [
            r['judge_score']['total']
            for r in same_model
            if r.get('category') == category and 'judge_score' in r
        ]

        if diverse_cat and same_cat:
            diverse_cat_mean = np.mean(diverse_cat)
            same_cat_mean = np.mean(same_cat)
            delta = diverse_cat_mean - same_cat_mean

            # Statistical test for this category
            if len(diverse_cat) >= 2 and len(same_cat) >= 2:
                _, cat_p_value = stats.ttest_ind(diverse_cat, same_cat)
                p_str = f"{cat_p_value:.3f}"
            else:
                p_str = "N/A"

            print(f"{category:15s} {diverse_cat_mean:8.1f} {same_cat_mean:11.1f} {delta:+8.1f} {p_str:>8s}")
            category_results.append({
                'category': category,
                'diverse_mean': diverse_cat_mean,
                'same_mean': same_cat_mean,
                'delta': delta
            })

    print("="*60)

    # Identify categories where diversity helps most
    if category_results:
        print("\nCategories Where Diversity Helps Most:")
        sorted_by_delta = sorted(category_results, key=lambda x: x['delta'], reverse=True)
        for i, cat_result in enumerate(sorted_by_delta[:3], 1):
            print(f"  {i}. {cat_result['category']:15s} (+{cat_result['delta']:.1f} points)")

        print("\nCategories Where Diversity Helps Least:")
        for i, cat_result in enumerate(sorted_by_delta[-3:], 1):
            delta = cat_result['delta']
            sign = "+" if delta >= 0 else ""
            print(f"  {i}. {cat_result['category']:15s} ({sign}{delta:.1f} points)")

    print("\n" + "="*60)

    # Conclusion
    print("\nCONCLUSION:")
    print("-"*60)

    if p_value < 0.05 and diverse_mean > same_mean:
        print("✅ Statistical evidence that diversity improves quality")
        print(f"   Diverse ensemble scores {quality_diff:.1f} points higher (p={p_value:.4f})")
        print("   Recommendation: Use diverse model families in ensembles")
    elif p_value < 0.05 and diverse_mean < same_mean:
        print("⚠️  Statistical evidence that diversity REDUCES quality")
        print(f"   Same-model scores {-quality_diff:.1f} points higher (p={p_value:.4f})")
        print("   Recommendation: Consider same-model ensembles for consistency")
    else:
        print("⚠️  No statistical evidence that diversity matters")
        print(f"   Quality difference is {quality_diff:.1f} points (p={p_value:.4f})")
        print("   Recommendation: Diversity benefit unclear, use aggregation alone")

    print("="*60 + "\n")

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python benchmark/analyze_diversity.py <results_file>")
        print("\nExample:")
        print("  python benchmark/analyze_diversity.py results/benchmark_results.json")
        sys.exit(1)

    results_file = sys.argv[1]

    if not Path(results_file).exists():
        print(f"❌ Error: File not found: {results_file}")
        sys.exit(1)

    success = analyze_diversity(results_file)
    sys.exit(0 if success else 1)
