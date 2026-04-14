#!/usr/bin/env python3
"""
M-V4: Analyze results with and without adversarial prompts
Check if adversarial prompts (5 of 54) skew the overall findings
"""

import json
import statistics
from scipy import stats

def load_json(filepath):
    with open(filepath) as f:
        return json.load(f)

def filter_by_category(results, exclude_category=None):
    """Filter results, optionally excluding a category."""
    if exclude_category:
        return [r for r in results if r.get('category') != exclude_category]
    return results

def extract_scores(results):
    """Extract judge scores."""
    return [r['judge_score']['total'] for r in results if 'judge_score' in r]

def analyze_with_without(baseline, ensemble, config_name, phase_name):
    """Analyze results with and without adversarial prompts."""

    # All prompts
    baseline_all = extract_scores(baseline)
    ensemble_all = extract_scores(ensemble)

    # Without adversarial
    baseline_no_adv = extract_scores(filter_by_category(baseline, 'adversarial'))
    ensemble_no_adv = extract_scores(filter_by_category(ensemble, 'adversarial'))

    mean_baseline_all = statistics.mean(baseline_all)
    mean_ensemble_all = statistics.mean(ensemble_all)
    delta_all = mean_ensemble_all - mean_baseline_all

    mean_baseline_no_adv = statistics.mean(baseline_no_adv)
    mean_ensemble_no_adv = statistics.mean(ensemble_no_adv)
    delta_no_adv = mean_ensemble_no_adv - mean_baseline_no_adv

    # Paired t-tests
    t_all, p_all = stats.ttest_rel(baseline_all, ensemble_all)
    t_no_adv, p_no_adv = stats.ttest_rel(baseline_no_adv, ensemble_no_adv)

    print(f"\n{config_name}:")
    print(f"  All prompts (n={len(baseline_all)}):")
    print(f"    Baseline: {mean_baseline_all:.2f}, Ensemble: {mean_ensemble_all:.2f}, Delta: {delta_all:+.2f}, p={p_all:.4f}")
    print(f"  Without adversarial (n={len(baseline_no_adv)}):")
    print(f"    Baseline: {mean_baseline_no_adv:.2f}, Ensemble: {mean_ensemble_no_adv:.2f}, Delta: {delta_no_adv:+.2f}, p={p_no_adv:.4f}")
    print(f"  Impact of excluding adversarial: Delta change = {delta_no_adv - delta_all:+.2f}")

    return {
        'config': config_name,
        'delta_all': delta_all,
        'delta_no_adv': delta_no_adv,
        'p_all': p_all,
        'p_no_adv': p_no_adv
    }

print("="*80)
print("M-V4: IMPACT OF ADVERSARIAL PROMPTS")
print("="*80)

# Phase 1
print("\n" + "="*80)
print("PHASE 1: Premium Tier Testing")
print("="*80)

phase1 = load_json('results/premium_tier.json')
baseline_p1 = phase1['baselines']['opus']

results_p1 = []

for config_name in ['high-end-reasoning', 'mixed-capability', 'same-model-premium']:
    ensemble = phase1['ensembles'][config_name]
    result = analyze_with_without(baseline_p1, ensemble, config_name, "Phase 1")
    results_p1.append(result)

# Phase 3
print("\n\n" + "="*80)
print("PHASE 3: Persona Diversity Testing")
print("="*80)

phase3 = load_json('results/persona_experiment.json')
baseline_p3 = phase3['baseline']['opus']

results_p3 = []

for config_name in ['persona-diverse', 'reasoning-cross-vendor', 'reasoning-with-personas']:
    ensemble = phase3['ensembles'][config_name]
    result = analyze_with_without(baseline_p3, ensemble, config_name, "Phase 3")
    results_p3.append(result)

# Summary
print("\n\n" + "="*80)
print("SUMMARY: Does Excluding Adversarial Prompts Change Findings?")
print("="*80)

print(f"\n{'Configuration':<30} {'Delta (All)':<12} {'Delta (No-Adv)':<15} {'Change':<10} {'Impact'}")
print("-"*90)

all_results = results_p1 + results_p3

for r in all_results:
    change = r['delta_no_adv'] - r['delta_all']
    impact = "Minimal" if abs(change) < 0.3 else ("Moderate" if abs(change) < 0.7 else "Large")
    print(f"{r['config']:<30} {r['delta_all']:+.2f}         {r['delta_no_adv']:+.2f}            {change:+.2f}       {impact}")

# Overall range
all_deltas = [r['delta_all'] for r in all_results]
no_adv_deltas = [r['delta_no_adv'] for r in all_results]

min_all, max_all = min(all_deltas), max(all_deltas)
min_no_adv, max_no_adv = min(no_adv_deltas), max(no_adv_deltas)

print(f"\nOverall delta range:")
print(f"  All prompts:         {abs(max_all):.2f} to {abs(min_all):.2f} points")
print(f"  Without adversarial: {abs(max_no_adv):.2f} to {abs(min_no_adv):.2f} points")

# Check if any become significant
print(f"\nStatistical significance (p < 0.05):")
sig_all = sum(1 for r in all_results if r['p_all'] < 0.05)
sig_no_adv = sum(1 for r in all_results if r['p_no_adv'] < 0.05)
print(f"  All prompts:         {sig_all} of {len(all_results)} significant")
print(f"  Without adversarial: {sig_no_adv} of {len(all_results)} significant")

print("\n" + "="*80)
print("CONCLUSION:")
print("="*80)

avg_change = statistics.mean([abs(r['delta_no_adv'] - r['delta_all']) for r in all_results])
print(f"\nAverage absolute change in delta: {avg_change:.2f} points")

if avg_change < 0.3:
    print("\n✅ Adversarial prompts have MINIMAL impact on findings")
    print("   Excluding them does not materially change the conclusions")
elif avg_change < 0.7:
    print("\n⚠️  Adversarial prompts have MODERATE impact on findings")
    print("   Consider reporting results with and without adversarial prompts")
else:
    print("\n🔴 Adversarial prompts have LARGE impact on findings")
    print("   MUST report results separately with breakdown by prompt type")

print("\n" + "="*80)
