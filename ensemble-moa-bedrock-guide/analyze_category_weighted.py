#!/usr/bin/env python3
"""
M-V5: Calculate category-weighted averages
Check if category imbalance skews overall scores
"""

import json
import statistics
from collections import defaultdict

def load_json(filepath):
    with open(filepath) as f:
        return json.load(f)

def analyze_by_category(results, name):
    """Group scores by category and calculate weighted average."""

    category_scores = defaultdict(list)

    for r in results:
        if 'judge_score' in r and 'category' in r:
            category_scores[r['category']].append(r['judge_score']['total'])

    # Calculate per-category means
    category_means = {}
    for category, scores in category_scores.items():
        category_means[category] = statistics.mean(scores)

    # Overall mean (current method - all prompts equally weighted)
    all_scores = [r['judge_score']['total'] for r in results if 'judge_score' in r]
    overall_mean = statistics.mean(all_scores)

    # Category-weighted mean (each category weighted equally)
    weighted_mean = statistics.mean(category_means.values())

    return {
        'name': name,
        'category_means': category_means,
        'overall_mean': overall_mean,
        'weighted_mean': weighted_mean,
        'difference': weighted_mean - overall_mean,
        'n_categories': len(category_means),
        'total_prompts': len(all_scores)
    }

print("="*80)
print("M-V5: CATEGORY-WEIGHTED AVERAGES")
print("="*80)
print()
print("Checking if unbalanced category representation skews overall scores")
print()

# Phase 1
phase1 = load_json('results/premium_tier.json')

print("="*80)
print("PHASE 1: Premium Tier Testing")
print("="*80)

configs_p1 = {
    'Opus Baseline': phase1['baselines']['opus'],
    'High-End Reasoning': phase1['ensembles']['high-end-reasoning'],
    'Mixed-Capability': phase1['ensembles']['mixed-capability'],
    'Same-Model-Premium': phase1['ensembles']['same-model-premium']
}

results_p1 = []
for name, data in configs_p1.items():
    result = analyze_by_category(data, name)
    results_p1.append(result)

    print(f"\n{name}:")
    print(f"  Current method (all prompts): {result['overall_mean']:.2f}")
    print(f"  Category-weighted:            {result['weighted_mean']:.2f}")
    print(f"  Difference:                   {result['difference']:+.2f}")
    print(f"\n  Category breakdown ({result['n_categories']} categories):")

    for category in sorted(result['category_means'].keys()):
        score = result['category_means'][category]
        print(f"    {category:15s}: {score:.2f}")

# Phase 3
print("\n\n" + "="*80)
print("PHASE 3: Persona Diversity Testing")
print("="*80)

phase3 = load_json('results/persona_experiment.json')

configs_p3 = {
    'Opus Baseline': phase3['baseline']['opus'],
    'Persona-Diverse': phase3['ensembles']['persona-diverse'],
    'Reasoning Cross-Vendor': phase3['ensembles']['reasoning-cross-vendor'],
    'Reasoning + Personas': phase3['ensembles']['reasoning-with-personas']
}

results_p3 = []
for name, data in configs_p3.items():
    result = analyze_by_category(data, name)
    results_p3.append(result)

    print(f"\n{name}:")
    print(f"  Current method (all prompts): {result['overall_mean']:.2f}")
    print(f"  Category-weighted:            {result['weighted_mean']:.2f}")
    print(f"  Difference:                   {result['difference']:+.2f}")
    print(f"\n  Category breakdown ({result['n_categories']} categories):")

    for category in sorted(result['category_means'].keys()):
        score = result['category_means'][category]
        print(f"    {category:15s}: {score:.2f}")

# Summary
print("\n\n" + "="*80)
print("SUMMARY: Impact of Category Weighting")
print("="*80)

all_results = results_p1 + results_p3

print(f"\n{'Configuration':<30} {'Current':<10} {'Weighted':<10} {'Diff':<10} {'Impact'}")
print("-"*80)

for r in all_results:
    diff = r['difference']
    impact = "Minimal" if abs(diff) < 0.5 else ("Moderate" if abs(diff) < 1.0 else "Large")
    print(f"{r['name']:<30} {r['overall_mean']:>9.2f} {r['weighted_mean']:>9.2f} {diff:+9.2f}  {impact}")

max_diff = max(abs(r['difference']) for r in all_results)
avg_diff = statistics.mean(abs(r['difference']) for r in all_results)

print(f"\nMaximum difference: {max_diff:.2f} points")
print(f"Average difference: {avg_diff:.2f} points")

# Check if deltas change
print("\n" + "="*80)
print("Do Deltas Change with Category Weighting?")
print("="*80)

def get_delta(baseline, ensemble, method):
    """Calculate delta for a given averaging method."""
    if method == 'current':
        return ensemble['overall_mean'] - baseline['overall_mean']
    else:
        return ensemble['weighted_mean'] - baseline['weighted_mean']

print("\nPhase 1:")
baseline_p1 = results_p1[0]  # Opus baseline
for ensemble in results_p1[1:]:
    delta_current = get_delta(baseline_p1, ensemble, 'current')
    delta_weighted = get_delta(baseline_p1, ensemble, 'weighted')
    delta_change = delta_weighted - delta_current
    print(f"  {ensemble['name']:30s}: {delta_current:+.2f} → {delta_weighted:+.2f} (change: {delta_change:+.2f})")

print("\nPhase 3:")
baseline_p3 = results_p3[0]  # Opus baseline
for ensemble in results_p3[1:]:
    delta_current = get_delta(baseline_p3, ensemble, 'current')
    delta_weighted = get_delta(baseline_p3, ensemble, 'weighted')
    delta_change = delta_weighted - delta_current
    print(f"  {ensemble['name']:30s}: {delta_current:+.2f} → {delta_weighted:+.2f} (change: {delta_change:+.2f})")

# Conclusion
print("\n" + "="*80)
print("CONCLUSION:")
print("="*80)

if max_diff < 0.5:
    print("\n✅ Category weighting has MINIMAL impact")
    print("   Current averaging method (all prompts equally weighted) is appropriate")
elif max_diff < 1.0:
    print("\n⚠️  Category weighting has MODERATE impact")
    print("   Consider reporting both methods or justifying equal prompt weighting")
else:
    print("\n🔴 Category weighting has LARGE impact")
    print("   MUST use category-weighted averages to avoid bias from unbalanced categories")

print("\n" + "="*80)
