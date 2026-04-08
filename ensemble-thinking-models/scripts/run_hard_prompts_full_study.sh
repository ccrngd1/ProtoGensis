#!/usr/bin/env bash
# Full Hard Prompts Experiment Study
# Runs all comparison dimensions to test thinking vs fast models on hard prompts
#
# Estimated cost: $12-15 total
# Estimated time: 20-30 minutes

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -z "${AWS_BEARER_TOKEN_BEDROCK:-}" ]; then
    echo "ERROR: AWS_BEARER_TOKEN_BEDROCK environment variable not set"
    exit 1
fi

cd "$PROJECT_DIR"

# Verify hard prompts file exists
if [ ! -f "prompts/hard_prompts.json" ]; then
    echo "ERROR: prompts/hard_prompts.json not found"
    exit 1
fi

# Count prompts
PROMPT_COUNT=$(python3 -c "import json; print(len(json.load(open('prompts/hard_prompts.json'))['prompts']))")

echo "========================================"
echo "HARD PROMPTS FULL STUDY"
echo "========================================"
echo ""
echo "Prompts: ${PROMPT_COUNT} hard prompts (requiring deep reasoning)"
echo ""
echo "Experiments:"
echo "  1. THINKING-ONLY: opus-thinking, sonnet-thinking, haiku-thinking"
echo "  2. FAST-ONLY: opus-fast, sonnet-fast, haiku-fast, llama-3-1-70b, nova-pro, nova-lite"
echo "  3. THINKING vs FAST (same models): Direct comparison"
echo "  4. HYBRID: 1 thinking + 5 fast models"
echo ""
echo "Estimated cost: \$12-15 total"
echo "Estimated time: 20-30 minutes"
echo ""

# Start timer
START_TIME=$(date +%s)

# Create results directory structure
mkdir -p results/hard_prompts/{thinking,fast,comparison,hybrid}

# ============================================================================
# EXPERIMENT 1: THINKING-ONLY ENSEMBLE
# ============================================================================

echo ""
echo "========================================"
echo "EXPERIMENT 1: THINKING-ONLY ENSEMBLE"
echo "========================================"
echo "Models: opus-thinking, sonnet-thinking, haiku-thinking"
echo "Expected: 80-90% accuracy, ~\$2.50 cost"
echo ""

PYTHONUNBUFFERED=1 python3 -u harness.py \
  --models opus-thinking sonnet-thinking haiku-thinking \
  --prompts prompts/hard_prompts.json \
  --output results/hard_prompts/thinking/responses.json

echo ""
echo "Running vote aggregation (thinking-only)..."
PYTHONUNBUFFERED=1 python3 -u aggregators/vote.py \
  results/hard_prompts/thinking/responses.json --live

echo ""
echo "Running stitch synthesis (thinking-only)..."
PYTHONUNBUFFERED=1 python3 -u aggregators/stitch.py \
  results/hard_prompts/thinking/responses.json --live

echo ""
echo "✓ Experiment 1 complete!"

# ============================================================================
# EXPERIMENT 2: FAST-ONLY ENSEMBLE
# ============================================================================

echo ""
echo "========================================"
echo "EXPERIMENT 2: FAST-ONLY ENSEMBLE"
echo "========================================"
echo "Models: opus-fast, sonnet-fast, haiku-fast, llama-3-1-70b, nova-pro, nova-lite"
echo "Expected: 50-70% accuracy, ~\$0.80 cost"
echo ""

PYTHONUNBUFFERED=1 python3 -u harness.py \
  --models opus-fast sonnet-fast haiku-fast llama-3-1-70b nova-pro nova-lite \
  --prompts prompts/hard_prompts.json \
  --output results/hard_prompts/fast/responses.json

echo ""
echo "Running vote aggregation (fast-only)..."
PYTHONUNBUFFERED=1 python3 -u aggregators/vote.py \
  results/hard_prompts/fast/responses.json --live

echo ""
echo "Running stitch synthesis (fast-only)..."
PYTHONUNBUFFERED=1 python3 -u aggregators/stitch.py \
  results/hard_prompts/fast/responses.json --live

echo ""
echo "✓ Experiment 2 complete!"

# ============================================================================
# EXPERIMENT 3: DIRECT COMPARISON (Thinking vs Fast, same models)
# ============================================================================

echo ""
echo "========================================"
echo "EXPERIMENT 3: THINKING vs FAST (DIRECT)"
echo "========================================"
echo "Models: All 6 Claude models (3 thinking, 3 fast)"
echo "Tests: Does thinking justify 5-10x cost increase?"
echo ""

PYTHONUNBUFFERED=1 python3 -u harness.py \
  --models opus-thinking opus-fast sonnet-thinking sonnet-fast haiku-thinking haiku-fast \
  --prompts prompts/hard_prompts.json \
  --output results/hard_prompts/comparison/responses.json

echo ""
echo "Running vote aggregation (comparison)..."
PYTHONUNBUFFERED=1 python3 -u aggregators/vote.py \
  results/hard_prompts/comparison/responses.json --live

echo ""
echo "Running stitch synthesis (comparison)..."
PYTHONUNBUFFERED=1 python3 -u aggregators/stitch.py \
  results/hard_prompts/comparison/responses.json --live

echo ""
echo "✓ Experiment 3 complete!"

# ============================================================================
# EXPERIMENT 4: HYBRID ENSEMBLE (1 thinking + 5 fast)
# ============================================================================

echo ""
echo "========================================"
echo "EXPERIMENT 4: HYBRID ENSEMBLE"
echo "========================================"
echo "Models: opus-thinking + haiku-fast + llama-3-1-70b + nova-pro + nova-lite + nemotron-nano"
echo "Tests: Optimal cost/accuracy trade-off?"
echo ""

PYTHONUNBUFFERED=1 python3 -u harness.py \
  --models opus-thinking haiku-fast llama-3-1-70b nova-pro nova-lite nemotron-nano \
  --prompts prompts/hard_prompts.json \
  --output results/hard_prompts/hybrid/responses.json

echo ""
echo "Running vote aggregation (hybrid)..."
PYTHONUNBUFFERED=1 python3 -u aggregators/vote.py \
  results/hard_prompts/hybrid/responses.json --live

echo ""
echo "Running stitch synthesis (hybrid)..."
PYTHONUNBUFFERED=1 python3 -u aggregators/stitch.py \
  results/hard_prompts/hybrid/responses.json --live

echo ""
echo "✓ Experiment 4 complete!"

# ============================================================================
# SUMMARY ANALYSIS
# ============================================================================

echo ""
echo "========================================"
echo "GENERATING SUMMARY ANALYSIS"
echo "========================================"

python3 <<'PYTHON'
import json
import os

results_dir = "results/hard_prompts"
experiments = {
    "thinking": "Thinking-Only Ensemble (O+S+H thinking)",
    "fast": "Fast-Only Ensemble (6 models, no thinking)",
    "comparison": "Direct Comparison (3 thinking + 3 fast)",
    "hybrid": "Hybrid Ensemble (1 thinking + 5 fast)"
}

print("\n" + "="*80)
print("HARD PROMPTS STUDY: SUMMARY RESULTS")
print("="*80)

for exp_key, exp_name in experiments.items():
    exp_dir = os.path.join(results_dir, exp_key)

    print(f"\n{exp_name}")
    print("-" * len(exp_name))

    # Load responses
    with open(os.path.join(exp_dir, "responses.json")) as f:
        responses = json.load(f)

    # Calculate metrics
    total_cost = 0
    model_costs = {}

    for prompt_result in responses:
        for model_key, response in prompt_result["responses"].items():
            cost = response.get("cost_usd", 0)
            total_cost += cost
            model_costs[model_key] = model_costs.get(model_key, 0) + cost

    # Load vote results
    with open(os.path.join(exp_dir, "vote_results.json")) as f:
        vote_results = json.load(f)

    # Count convergence
    convergence_count = sum(1 for r in vote_results if r.get("convergence", False))

    print(f"  Total cost: ${total_cost:.4f}")
    print(f"  Models used: {len(model_costs)}")
    print(f"  Convergence rate: {convergence_count}/{len(vote_results)} ({convergence_count/len(vote_results)*100:.0f}%)")
    print(f"  Top 3 most expensive models:")

    sorted_costs = sorted(model_costs.items(), key=lambda x: x[1], reverse=True)[:3]
    for model, cost in sorted_costs:
        print(f"    - {model}: ${cost:.4f}")

print("\n" + "="*80)
print("KEY COMPARISONS")
print("="*80)

# Load thinking results
with open("results/hard_prompts/thinking/responses.json") as f:
    thinking_data = json.load(f)
thinking_cost = sum(r["cost_usd"] for p in thinking_data for r in p["responses"].values())

# Load fast results
with open("results/hard_prompts/fast/responses.json") as f:
    fast_data = json.load(f)
fast_cost = sum(r["cost_usd"] for p in fast_data for r in p["responses"].values())

# Load hybrid results
with open("results/hard_prompts/hybrid/responses.json") as f:
    hybrid_data = json.load(f)
hybrid_cost = sum(r["cost_usd"] for p in hybrid_data for r in p["responses"].values())

print(f"\nCost Comparison:")
print(f"  Thinking-only: ${thinking_cost:.4f}")
print(f"  Fast-only:     ${fast_cost:.4f} ({thinking_cost/fast_cost:.1f}x cheaper than thinking)")
print(f"  Hybrid:        ${hybrid_cost:.4f} ({thinking_cost/hybrid_cost:.1f}x cheaper than thinking)")

print(f"\nCost Premium Analysis:")
print(f"  Thinking premium over fast: ${thinking_cost - fast_cost:.4f} ({(thinking_cost/fast_cost - 1)*100:.0f}% more)")
print(f"  Hybrid vs Fast delta:       ${hybrid_cost - fast_cost:.4f}")

print("\n" + "="*80)
print("To evaluate accuracy, run:")
print("  python3 evaluate_hard_prompts.py")
print("="*80)

PYTHON

# Calculate elapsed time
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
MINUTES=$((ELAPSED / 60))
SECONDS=$((ELAPSED % 60))

echo ""
echo "========================================"
echo "STUDY COMPLETE!"
echo "========================================"
echo ""
echo "Total time: ${MINUTES}m ${SECONDS}s"
echo ""
echo "Results saved to:"
echo "  - results/hard_prompts/thinking/"
echo "  - results/hard_prompts/fast/"
echo "  - results/hard_prompts/comparison/"
echo "  - results/hard_prompts/hybrid/"
echo ""
echo "Next steps:"
echo "  1. Review summary analysis above"
echo "  2. Run: python3 evaluate_hard_prompts.py (for accuracy metrics)"
echo "  3. Compare to previous easy-prompt results"
echo ""
