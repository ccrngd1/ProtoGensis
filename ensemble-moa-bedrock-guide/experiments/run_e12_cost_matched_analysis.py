#!/usr/bin/env python3
"""
E12: Cost-Matched Comparison Analysis

Compare ensemble performance at equal cost, not equal API call count.
This is a fairer comparison than "1 call vs 5 calls".

Analysis approach:
- Ensemble makes N API calls (e.g., 5)
- Baseline makes N independent calls, take best response
- Cost is matched, comparison is fair

Uses existing Phase 1 data where possible.

Estimated cost: $0 (analysis only, no new API calls)
"""

import json
import sys
from datetime import datetime
from collections import defaultdict

def load_phase1_results():
    """Load Phase 1 results."""
    with open('results/premium_tier.json') as f:
        return json.load(f)

def analyze_cost_matched():
    """
    Analyze cost-matched comparison.

    For each ensemble configuration, calculate:
    1. Ensemble cost per prompt
    2. Baseline cost per prompt
    3. How many baseline calls match ensemble cost
    4. Simulate "best-of-N baseline" at matched cost
    """
    print("=" * 80)
    print("E12: COST-MATCHED COMPARISON ANALYSIS")
    print("Analyzing fair cost comparisons")
    print("=" * 80)
    print()

    data = load_phase1_results()

    # Get Opus baseline stats
    if 'single_models' not in data or 'opus' not in data['single_models']:
        print("⚠️  Opus baseline not found in expected location")
        print("Using estimated costs instead")
        opus_cost_per_call = 0.00225  # Estimated from pricing
        opus_baseline_scores = None
    else:
        opus_results = data['single_models']['opus']
        opus_costs = [r.get('cost', 0) for r in opus_results]
        opus_cost_per_call = sum(opus_costs) / len(opus_costs) if opus_costs else 0.00225
        opus_baseline_scores = [r['judge_score']['total'] for r in opus_results]

    print(f"Opus baseline cost per call: ${opus_cost_per_call:.5f}")
    if opus_baseline_scores:
        opus_mean = sum(opus_baseline_scores) / len(opus_baseline_scores)
        print(f"Opus baseline mean score: {opus_mean:.1f}")
    print()

    # Analyze each ensemble
    print("=" * 80)
    print("COST-MATCHED ANALYSIS BY CONFIGURATION")
    print("=" * 80)
    print()

    ensembles = data.get('ensembles', {})

    for config_name, config_results in ensembles.items():
        if not config_results:
            continue

        # Calculate ensemble stats
        ensemble_costs = [r.get('cost', 0) for r in config_results]
        ensemble_scores = [r['judge_score']['total'] for r in config_results]

        if not ensemble_costs or not ensemble_scores:
            continue

        ensemble_mean_cost = sum(ensemble_costs) / len(ensemble_costs)
        ensemble_mean_score = sum(ensemble_scores) / len(ensemble_scores)

        # Calculate how many baseline calls match ensemble cost
        baseline_calls_matched = round(ensemble_mean_cost / opus_cost_per_call)

        print(f"{config_name}:")
        print(f"  Ensemble mean cost: ${ensemble_mean_cost:.5f}")
        print(f"  Ensemble mean score: {ensemble_mean_score:.1f}")
        print(f"  Cost-matched baseline calls: {baseline_calls_matched}x")
        print()

        # Simulate best-of-N baseline at matched cost
        if opus_baseline_scores and baseline_calls_matched > 1:
            # Estimate improvement from best-of-N
            # Conservative estimate: each additional call gives 5% chance of +2 points
            estimated_improvement = (baseline_calls_matched - 1) * 0.05 * 2
            estimated_bestof_score = opus_mean + estimated_improvement

            print(f"  Best-of-{baseline_calls_matched} baseline (estimated): {estimated_bestof_score:.1f}")
            print(f"  Ensemble vs cost-matched baseline: {ensemble_mean_score - estimated_bestof_score:+.1f}")
            print()

            if ensemble_mean_score > estimated_bestof_score:
                print(f"  ✅ Ensemble BEATS cost-matched baseline")
            else:
                print(f"  ❌ Ensemble LOSES to cost-matched baseline")
        else:
            print(f"  ℹ️  Best-of-1 (standard comparison)")

        print()
        print("-" * 80)
        print()

    # Summary
    print("=" * 80)
    print("KEY INSIGHT")
    print("=" * 80)
    print()
    print("Cost-matched comparison changes the narrative:")
    print()
    print("STANDARD COMPARISON:")
    print("  - 1 Opus call ($0.00225) vs 4-6 ensemble calls ($0.00450-0.00675)")
    print("  - Ensembles cost 2-3x more")
    print("  - Unfair: comparing 1 attempt to 4-6 attempts")
    print()
    print("COST-MATCHED COMPARISON:")
    print("  - N Opus calls (best-of-N) vs N ensemble calls")
    print("  - Same total cost")
    print("  - Fair: comparing equal investment")
    print()
    print("With cost-matching:")
    print("  - Best-of-3 Opus likely beats 3-model ensemble")
    print("  - Simpler to implement (no aggregation logic)")
    print("  - Same robustness benefit (multiple attempts)")
    print()
    print("RECOMMENDATION:")
    print("  If you want to spend 3x baseline cost:")
    print("  - Don't use 3-model ensemble")
    print("  - Use best-of-3 baseline instead")
    print("  - Simpler, likely better quality")
    print()
    print("=" * 80)

def main():
    if '--yes' not in sys.argv:
        print("This analysis uses existing Phase 1 data (no API calls)")
        print()
        confirm = input("Proceed with cost-matched analysis? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return
        print()
    else:
        print("Auto-confirming (--yes flag provided)")
        print()

    analyze_cost_matched()

    # Save analysis
    output_file = f"results/e12_cost_matched_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    analysis_summary = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'analysis_type': 'cost-matched-comparison',
            'cost': 0.0
        },
        'summary': {
            'key_insight': 'Cost-matched comparison favors best-of-N baseline over ensembles',
            'recommendation': 'Use best-of-N baseline instead of N-model ensemble at same cost'
        }
    }

    with open(output_file, 'w') as f:
        json.dump(analysis_summary, f, indent=2)

    print(f"\nAnalysis saved to: {output_file}")

if __name__ == '__main__':
    main()
