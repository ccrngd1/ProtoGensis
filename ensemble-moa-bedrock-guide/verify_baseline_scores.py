#!/usr/bin/env python3
"""
Verification Script: M-V1 - Reconcile Opus Baseline Discrepancy

This script checks the Opus baseline scores across all result files and documents
where the 94.4 vs 82.7 discrepancy comes from.
"""

import json
import statistics

def load_json(filepath):
    """Load JSON file."""
    with open(filepath) as f:
        return json.load(f)

def calculate_avg_scores(results):
    """Calculate average judge scores from list of results."""
    scores = [r['judge_score']['total'] for r in results if 'judge_score' in r]
    if not scores:
        return None, None, 0
    return statistics.mean(scores), statistics.stdev(scores) if len(scores) > 1 else 0, len(scores)

print("="*80)
print("VERIFICATION: M-V1 - Opus Baseline Score Reconciliation")
print("="*80)
print()

# Check Phase 1 (premium_tier.json)
print("PHASE 1: premium_tier.json (Custom-54 prompts)")
print("-"*80)
phase1 = load_json('results/premium_tier.json')

if 'baselines' in phase1 and 'opus' in phase1['baselines']:
    opus_results = phase1['baselines']['opus']
    mean, std, count = calculate_avg_scores(opus_results)
    print(f"Opus baseline: {mean:.2f} ± {std:.2f} (n={count})")
    print(f"Source: .baselines.opus[]")
else:
    print("❌ No opus baseline found")

print()
print("Phase 1 Ensembles:")
if 'ensembles' in phase1:
    for ensemble_name, results in phase1['ensembles'].items():
        mean, std, count = calculate_avg_scores(results)
        if mean:
            delta = mean - (94.48 if 'baselines' in phase1 and 'opus' in phase1['baselines'] else 0)
            print(f"  {ensemble_name:30s}: {mean:.2f} ± {std:.2f} (delta: {delta:+.2f})")

print()
print("="*80)

# Check Phase 2 (mtbench_results.json)
print("PHASE 2: mtbench_results.json (MT-Bench 80 questions)")
print("-"*80)
phase2 = load_json('results/mtbench_results.json')

if 'summary' in phase2 and 'opus' in phase2['summary']:
    opus_mean = phase2['summary']['opus']['avg_quality']
    opus_std = phase2['summary']['opus']['std_quality']
    print(f"Opus baseline: {opus_mean:.2f} ± {opus_std:.2f}")
    print(f"Source: .summary.opus.avg_quality")
elif 'results' in phase2 and 'opus' in phase2['results']:
    opus_results = phase2['results']['opus']
    mean, std, count = calculate_avg_scores(opus_results)
    print(f"Opus baseline: {mean:.2f} ± {std:.2f} (n={count})")
    print(f"Source: .results.opus[]")

print()
print("="*80)

# Check Phase 3 (persona_experiment.json)
print("PHASE 3: persona_experiment.json (Custom-54 prompts, persona diversity)")
print("-"*80)
phase3 = load_json('results/persona_experiment.json')

if 'baseline' in phase3 and 'opus' in phase3['baseline']:
    opus_results = phase3['baseline']['opus']
    mean, std, count = calculate_avg_scores(opus_results)
    print(f"Opus baseline: {mean:.2f} ± {std:.2f} (n={count})")
    print(f"Source: .baseline.opus[]")
else:
    print("❌ No opus baseline found")

print()
print("Phase 3 Ensembles:")
if 'ensembles' in phase3:
    for ensemble_name, results in phase3['ensembles'].items():
        mean, std, count = calculate_avg_scores(results)
        if mean:
            delta = mean - (91.43 if 'baseline' in phase3 and 'opus' in phase3['baseline'] else 0)
            print(f"  {ensemble_name:30s}: {mean:.2f} ± {std:.2f} (delta: {delta:+.2f})")

print()
print("="*80)
print("SUMMARY: Where the discrepancy comes from")
print("="*80)
print()
print("1. PREMIUM_TIER_RESULTS.md reports: Opus = 94.4 ± 7.6")
print("   Source: premium_tier.json Phase 1 actual score = 94.48")
print("   ✅ CORRECT")
print()
print("2. BLOG.md reports: Opus baseline = 82.7")
print("   Possible source: mtbench_results.json actual score = 82.62")
print("   ❌ WRONG for Phase 1 comparisons")
print()
print("3. BLOG.md Phase 1 ensemble scores (81.3, 78.2, 77.9)")
print("   Premium_tier.json actual scores: (93.98, 93.07, 93.06)")
print("   ❌ MAJOR DISCREPANCY - scores don't match!")
print()
print("4. BLOG.md Phase 3 ensemble scores (80.6, 79.8, 80.1)")
print("   Persona_experiment.json actual scores: (89.28, 90.35, 90.83)")
print("   ❌ MAJOR DISCREPANCY - scores don't match!")
print()
print("="*80)
print("CONCLUSION:")
print("="*80)
print()
print("The BLOG.md appears to be using scores from a DIFFERENT scoring run")
print("than what's in the actual result files. All BLOG scores are ~10-15 points")
print("lower than the result files.")
print()
print("This is a PUBLICATION BLOCKER - all deltas and p-values in BLOG.md are wrong.")
print()
print("ACTION REQUIRED:")
print("1. Determine which scores are correct (result files vs BLOG)")
print("2. If result files are correct: Recalculate ALL deltas in BLOG.md")
print("3. If BLOG is correct: Trace where those scores came from")
print("4. Check if there were multiple judge scoring runs with different results")
print()
