#!/usr/bin/env bash
# Test parallelization improvements
# Quick test with 3 models on 1 prompt to verify speedup

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -z "${AWS_BEARER_TOKEN_BEDROCK:-}" ]; then
    echo "ERROR: AWS_BEARER_TOKEN_BEDROCK environment variable not set"
    exit 1
fi

cd "$PROJECT_DIR"

echo "========================================"
echo "Parallelization Test"
echo "========================================"
echo "Testing: 3 models × 3 prompts"
echo "Models: haiku, nova-lite, mistral-large"
echo ""

# Test harness parallelization
echo "Testing harness parallel model calls..."
START=$(date +%s)
PYTHONUNBUFFERED=1 python3 -u harness.py \
  --models haiku nova-lite mistral-large \
  --prompts prompts/prompts_limited.json \
  --output results/test_parallel.json
END=$(date +%s)
HARNESS_TIME=$((END - START))

echo ""
echo "⏱️  Harness completed in ${HARNESS_TIME}s"
echo ""

# Test vote parallelization
echo "Testing vote parallel aggregation..."
cp results/test_parallel.json results/responses.json
START=$(date +%s)
PYTHONUNBUFFERED=1 python3 -u aggregators/vote.py results/responses.json --live
END=$(date +%s)
VOTE_TIME=$((END - START))

echo ""
echo "⏱️  Vote completed in ${VOTE_TIME}s"
echo ""

# Test stitch parallelization
echo "Testing stitch parallel synthesis..."
START=$(date +%s)
PYTHONUNBUFFERED=1 python3 -u aggregators/stitch.py results/responses.json --live
END=$(date +%s)
STITCH_TIME=$((END - START))

echo ""
echo "⏱️  Stitch completed in ${STITCH_TIME}s"
echo ""

echo "========================================"
echo "Performance Summary"
echo "========================================"
echo "Harness (3 models × 3 prompts): ${HARNESS_TIME}s"
echo "Vote (3 prompts): ${VOTE_TIME}s"
echo "Stitch (3 prompts): ${STITCH_TIME}s"
echo "Total: $((HARNESS_TIME + VOTE_TIME + STITCH_TIME))s"
echo ""

echo "Expected improvements vs sequential:"
echo "- Harness: 3-4x faster (models run in parallel)"
echo "- Vote: 3x faster (prompts processed in parallel)"
echo "- Stitch: 3x faster (prompts processed in parallel)"
echo ""
echo "✓ Parallelization test complete!"
