#!/usr/bin/env bash
# Re-run aggregations and evaluation with bug fixes applied

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -z "${AWS_BEARER_TOKEN_BEDROCK:-}" ]; then
    echo "ERROR: AWS_BEARER_TOKEN_BEDROCK environment variable not set"
    exit 1
fi

cd "$PROJECT_DIR"

echo "========================================"
echo "Re-running with Bug Fixes Applied"
echo "========================================"
echo ""
echo "Fixes:"
echo "  1. vote.py: Pattern matching now looks at END of judge response"
echo "  2. evaluate.py: Convergence ignores empty Opus answers"
echo "  3. evaluate.py: Truncation doesn't add '...' unnecessarily"
echo ""
echo "Using existing: results/live_responses.json"
echo ""

# Copy live responses to standard location
if [ -f "results/live_responses.json" ]; then
    cp results/live_responses.json results/responses.json
    echo "✓ Using live_responses.json"
else
    echo "ERROR: results/live_responses.json not found!"
    exit 1
fi

echo ""
echo "Step 1: Vote aggregation (with pattern matching fix)..."
echo "========================================"
PYTHONUNBUFFERED=1 python3 -u aggregators/vote.py results/responses.json --live

echo ""
echo "Step 2: Stitch synthesis..."
echo "========================================"
PYTHONUNBUFFERED=1 python3 -u aggregators/stitch.py results/responses.json --live

echo ""
echo "Step 3: Evaluation (with convergence fix)..."
echo "========================================"
PYTHONUNBUFFERED=1 python3 -u evaluate.py

echo ""
echo "========================================"
echo "✓ Complete! Verifying fixes..."
echo "========================================"
echo ""

# Verify vote answers are no longer empty
python3 -c "
import json
with open('results/vote_results.json', 'r') as f:
    data = json.load(f)
    empty_count = sum(1 for item in data if not item.get('selected_answer', '').strip())
    print(f'Vote results: {len(data) - empty_count}/{len(data)} have non-empty answers')
    if empty_count > 0:
        print(f'⚠ Warning: {empty_count} vote answers still empty')
    else:
        print('✓ All vote answers populated!')
"

# Verify convergence detection
python3 -c "
import json
with open('results/evaluation.json', 'r') as f:
    data = json.load(f)
    convergent = sum(1 for c in data['prompt_comparisons'] if c['convergence'])
    total = len(data['prompt_comparisons'])
    print(f'Convergence: {convergent}/{total} prompts show model agreement')
    print(f'Overall convergence rate: {data[\"insights\"][\"convergence_rate\"]:.1%}')
"

echo ""
echo "Results saved to:"
echo "  - results/vote_results.json"
echo "  - results/stitch_results.json"
echo "  - results/evaluation.json"
