#!/usr/bin/env bash
# Run Expanded Ensemble Experiment with Multiple Models
# Tests with and without Opus to compare value added
#
# Usage:
#   ./run_expanded_experiment.sh           # Interactive (asks for confirmation)
#   ./run_expanded_experiment.sh -y        # Skip confirmation

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -z "${AWS_BEARER_TOKEN_BEDROCK:-}" ]; then
    echo "ERROR: AWS_BEARER_TOKEN_BEDROCK environment variable not set"
    exit 1
fi

# Parse arguments
SKIP_CONFIRMATION=false
if [[ "${1:-}" == "-y" ]] || [[ "${1:-}" == "--yes" ]]; then
    SKIP_CONFIRMATION=true
fi

cd "$PROJECT_DIR"

# Verify prompts file exists
if [ ! -f "prompts/prompts.json" ]; then
    echo "ERROR: prompts/prompts.json not found"
    exit 1
fi

# Count prompts
PROMPT_COUNT=$(python3 -c "import json; print(len(json.load(open('prompts/prompts.json'))['prompts']))")

echo "========================================"
echo "Expanded Ensemble Experiment"
echo "========================================"
echo ""
echo "Models: 10 total"
echo "  Tier 1: opus"
echo "  Tier 2: nova-pro, mistral-large, llama-3-1-70b, gpt-oss"
echo "  Tier 3: haiku, llama-3-1-8b"
echo "  Tier 4: nova-lite, nova-micro, nemotron-nano"
echo ""
echo "Prompts: ${PROMPT_COUNT}"
echo ""
echo "Running TWO experiments:"
echo "  1. WITH Opus (all 10 models)"
echo "  2. WITHOUT Opus (9 models, excluding expensive thinking model)"
echo ""
echo "Estimated cost: ~\$0.97 total (\$0.70 + \$0.27)"
echo "Estimated time: ~4-5 minutes (with parallelization)"
echo ""

# Confirmation prompt (unless -y flag)
if [ "$SKIP_CONFIRMATION" = false ]; then
    read -p "Continue? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
    echo ""
fi

# Start timer
START_TIME=$(date +%s)

# Experiment 1: WITH OPUS (all models)
echo "========================================"
echo "Experiment 1: WITH OPUS"
echo "========================================"
PYTHONUNBUFFERED=1 python3 -u harness.py \
  --output results/responses_with_opus.json

# Copy for aggregation
cp results/responses_with_opus.json results/responses.json

# Vote aggregation (confidence-weighted)
echo ""
echo "Running confidence-weighted semantic majority vote (WITH OPUS)..."
PYTHONUNBUFFERED=1 python3 -u aggregators/vote.py \
  results/responses.json --live

# Save vote results
mv results/vote_results.json results/vote_results_with_opus.json

# Stitch synthesis
echo ""
echo "Running stitch synthesis (WITH OPUS)..."
PYTHONUNBUFFERED=1 python3 -u aggregators/stitch.py \
  results/responses.json --live

# Save stitch results
mv results/stitch_results.json results/stitch_results_with_opus.json

# Evaluation
echo ""
echo "Running evaluation (WITH OPUS)..."
cp results/vote_results_with_opus.json results/vote_results.json
cp results/stitch_results_with_opus.json results/stitch_results.json
PYTHONUNBUFFERED=1 python3 -u evaluate.py \
  --output results/evaluation_with_opus.json

# Experiment 2: WITHOUT OPUS
echo ""
echo "========================================"
echo "Experiment 2: WITHOUT OPUS"
echo "========================================"
PYTHONUNBUFFERED=1 python3 -u harness.py \
  --output results/responses_without_opus.json \
  --exclude-opus

# Copy for aggregation
cp results/responses_without_opus.json results/responses.json

# Vote aggregation (confidence-weighted)
echo ""
echo "Running confidence-weighted semantic majority vote (WITHOUT OPUS)..."
PYTHONUNBUFFERED=1 python3 -u aggregators/vote.py \
  results/responses.json --live

# Save vote results
mv results/vote_results.json results/vote_results_without_opus.json

# Stitch synthesis
echo ""
echo "Running stitch synthesis (WITHOUT OPUS)..."
PYTHONUNBUFFERED=1 python3 -u aggregators/stitch.py \
  results/responses.json --live

# Save stitch results
mv results/stitch_results.json results/stitch_results_without_opus.json

# Evaluation
echo ""
echo "Running evaluation (WITHOUT OPUS)..."
cp results/vote_results_without_opus.json results/vote_results.json
cp results/stitch_results_without_opus.json results/stitch_results.json
PYTHONUNBUFFERED=1 python3 -u evaluate.py \
  --output results/evaluation_without_opus.json

# Comparison
echo ""
echo "========================================"
echo "Comparison Summary"
echo "========================================"
echo ""

python3 -c "
import json

print('COST COMPARISON:')
print('='*60)

with open('results/evaluation_with_opus.json') as f:
    with_opus = json.load(f)

with open('results/evaluation_without_opus.json') as f:
    without_opus = json.load(f)

# Vote costs
vote_with = next(m['total_cost_usd'] for m in with_opus['summary_metrics'] if 'Vote' in m['approach'])
vote_without = next(m['total_cost_usd'] for m in without_opus['summary_metrics'] if 'Vote' in m['approach'])

print(f\"Vote aggregation WITH Opus:    \${vote_with:.4f}\")
print(f\"Vote aggregation WITHOUT Opus: \${vote_without:.4f}\")
print(f\"Cost reduction: \${vote_with - vote_without:.4f} ({(1 - vote_without/vote_with)*100:.1f}% cheaper)\")

print()
print('ACCURACY COMPARISON:')
print('='*60)

if 'ground_truth_analysis' in with_opus and 'ground_truth_analysis' in without_opus:
    acc_with = with_opus['ground_truth_analysis']['ensemble_accuracy']['vote']['accuracy']
    acc_without = without_opus['ground_truth_analysis']['ensemble_accuracy']['vote']['accuracy']

    print(f\"Vote accuracy WITH Opus:    {acc_with:.1%}\")
    print(f\"Vote accuracy WITHOUT Opus: {acc_without:.1%}\")
    print(f\"Accuracy difference: {(acc_with - acc_without)*100:+.1f} percentage points\")
else:
    print('Ground truth analysis not available')

print()
print('VALUE PROPOSITION:')
print('='*60)
if 'ground_truth_analysis' in with_opus and 'ground_truth_analysis' in without_opus:
    cost_premium = vote_with - vote_without
    acc_gain = (acc_with - acc_without) * 100

    if acc_gain > 0:
        print(f\"Opus adds {acc_gain:.1f} percentage points of accuracy for \${cost_premium:.4f}\")
        print(f\"Cost per accuracy point: \${cost_premium/acc_gain:.4f}\")
    elif acc_gain == 0:
        print(f\"⚠️  Opus adds NO accuracy improvement despite \${cost_premium:.4f} cost\")
        print(f\"   Recommendation: Use ensemble WITHOUT Opus\")
    else:
        print(f\"⚠️  Opus REDUCES accuracy by {abs(acc_gain):.1f} points and costs \${cost_premium:.4f} more\")
        print(f\"   Recommendation: Definitely exclude Opus\")
"

echo ""
echo "✓ Experiment complete!"
echo ""

# Calculate elapsed time
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
MINUTES=$((ELAPSED / 60))
SECONDS=$((ELAPSED % 60))

echo "Total time: ${MINUTES}m ${SECONDS}s"
echo ""
echo "Results saved:"
echo "  - results/responses_with_opus.json"
echo "  - results/responses_without_opus.json"
echo "  - results/evaluation_with_opus.json"
echo "  - results/evaluation_without_opus.json"
