#!/usr/bin/env python3
"""
Statistical Re-analysis Script
Generates corrected statistics with proper baselines for BLOG.md update
"""

import json
import statistics
from scipy import stats
import math

def load_json(filepath):
    """Load JSON file."""
    with open(filepath) as f:
        return json.load(f)

def extract_scores(results):
    """Extract judge scores from results list."""
    return [r['judge_score']['total'] for r in results if 'judge_score' in r]

def cohens_d(group1, group2):
    """Calculate Cohen's d effect size."""
    n1, n2 = len(group1), len(group2)
    var1, var2 = statistics.variance(group1), statistics.variance(group2)
    pooled_std = math.sqrt(((n1-1)*var1 + (n2-1)*var2) / (n1+n2-2))
    return (statistics.mean(group1) - statistics.mean(group2)) / pooled_std

def analyze_phase(phase_name, baseline_scores, ensemble_configs):
    """Analyze one phase: baseline vs ensembles."""
    print(f"\n{'='*80}")
    print(f"{phase_name}")
    print(f"{'='*80}\n")

    baseline_mean = statistics.mean(baseline_scores)
    baseline_std = statistics.stdev(baseline_scores)
    n = len(baseline_scores)

    print(f"Baseline (Opus):")
    print(f"  Score: {baseline_mean:.2f} ± {baseline_std:.2f} (n={n})")
    print()

    print(f"{'Configuration':<30} {'Score':<15} {'Delta':<10} {'t-stat':<10} {'p-value':<12} {'Cohen\'s d':<12} {'Significant?'}")
    print("-"*110)

    for config_name, ensemble_scores in ensemble_configs.items():
        ens_mean = statistics.mean(ensemble_scores)
        ens_std = statistics.stdev(ensemble_scores)
        delta = ens_mean - baseline_mean

        # Paired t-test (same prompts for baseline and ensemble)
        t_stat, p_value = stats.ttest_rel(baseline_scores, ensemble_scores)

        # Cohen's d effect size
        d = cohens_d(baseline_scores, ensemble_scores)

        # Significance
        significant = "YES ✓" if p_value < 0.05 else "NO ✗"

        score_str = f"{ens_mean:.2f} ± {ens_std:.2f}"
        print(f"{config_name:<30} {score_str:<15} {delta:+.2f}     {t_stat:+.3f}     {p_value:.4f}      {d:+.3f}         {significant}")

print("="*80)
print("CORRECTED STATISTICAL ANALYSIS")
print("="*80)
print()
print("Using correct baselines from result JSON files:")
print("  Phase 1: 94.48 (from premium_tier.json)")
print("  Phase 3: 91.43 (from persona_experiment.json)")
print()

# Phase 1: Premium Tier Testing
print("\nLoading Phase 1 results...")
phase1 = load_json('results/premium_tier.json')

baseline_opus = extract_scores(phase1['baselines']['opus'])

ensembles_phase1 = {
    'High-End Reasoning': extract_scores(phase1['ensembles']['high-end-reasoning']),
    'Mixed-Capability': extract_scores(phase1['ensembles']['mixed-capability']),
    'Same-Model-Premium': extract_scores(phase1['ensembles']['same-model-premium']),
}

analyze_phase("PHASE 1: Premium Tier Testing (Custom-54 prompts)", baseline_opus, ensembles_phase1)

# Phase 3: Persona Diversity
print("\n\nLoading Phase 3 results...")
phase3 = load_json('results/persona_experiment.json')

baseline_opus_p3 = extract_scores(phase3['baseline']['opus'])

ensembles_phase3 = {
    'Persona-Diverse': extract_scores(phase3['ensembles']['persona-diverse']),
    'Reasoning Cross-Vendor': extract_scores(phase3['ensembles']['reasoning-cross-vendor']),
    'Reasoning + Personas': extract_scores(phase3['ensembles']['reasoning-with-personas']),
}

analyze_phase("PHASE 3: Persona Diversity Testing (Custom-54 prompts)", baseline_opus_p3, ensembles_phase3)

# Summary
print(f"\n{'='*80}")
print("SUMMARY: Statistical Significance")
print(f"{'='*80}\n")

print("Phase 1 (3 comparisons):")
phase1_results = []
for config_name, scores in ensembles_phase1.items():
    t_stat, p_value = stats.ttest_rel(baseline_opus, scores)
    phase1_results.append((config_name, p_value))
    sig = "✓ significant" if p_value < 0.05 else "✗ not significant"
    print(f"  {config_name}: p={p_value:.4f} {sig}")

phase1_sig_count = sum(1 for _, p in phase1_results if p < 0.05)
print(f"\nPhase 1 significant: {phase1_sig_count} of 3")

print("\nPhase 3 (3 comparisons):")
phase3_results = []
for config_name, scores in ensembles_phase3.items():
    t_stat, p_value = stats.ttest_rel(baseline_opus_p3, scores)
    phase3_results.append((config_name, p_value))
    sig = "✓ significant" if p_value < 0.05 else "✗ not significant"
    print(f"  {config_name}: p={p_value:.4f} {sig}")

phase3_sig_count = sum(1 for _, p in phase3_results if p < 0.05)
print(f"\nPhase 3 significant: {phase3_sig_count} of 3")

total_sig = phase1_sig_count + phase3_sig_count
print(f"\n{'='*80}")
print(f"TOTAL: {total_sig} of 6 comparisons statistically significant (p < 0.05)")
print(f"{'='*80}")

print("\n\nCOMPARISON TO BLOG.md CLAIMS:")
print("-"*80)
print("BLOG.md claimed: '5 of 6 comparisons statistically significant'")
print(f"Corrected analysis: '{total_sig} of 6 comparisons statistically significant'")
print()
print("BLOG.md claimed: 'Same-model-premium scored 4.8 points lower'")
delta_smp = statistics.mean(ensembles_phase1['Same-Model-Premium']) - statistics.mean(baseline_opus)
print(f"Corrected analysis: 'Same-model-premium scored {delta_smp:.2f} points lower'")
print()
print("BLOG.md claimed: 'All ensembles underperform by 2-5 points'")
all_deltas = []
for scores in ensembles_phase1.values():
    all_deltas.append(statistics.mean(scores) - statistics.mean(baseline_opus))
for scores in ensembles_phase3.values():
    all_deltas.append(statistics.mean(scores) - statistics.mean(baseline_opus_p3))
min_delta, max_delta = min(all_deltas), max(all_deltas)
print(f"Corrected analysis: 'All ensembles underperform by {abs(max_delta):.2f}-{abs(min_delta):.2f} points'")

print("\n" + "="*80)
print("Analysis complete. Use these corrected numbers to update BLOG.md.")
print("="*80)
