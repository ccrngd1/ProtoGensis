#!/usr/bin/env bash
# Run Ensemble Thinking Models experiment
# Tests: Opus (extended thinking) + Nova Pro + Mistral Large on 10 hard prompts
#
# Requires: AWS_BEARER_TOKEN_BEDROCK environment variable

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$REPO_DIR/ensemble-thinking-models"
OUTPUT_FILE="results/live_responses.json"

if [ -z "${AWS_BEARER_TOKEN_BEDROCK:-}" ]; then
    echo "ERROR: AWS_BEARER_TOKEN_BEDROCK environment variable not set"
    exit 1
fi

echo "Ensemble Thinking Models"
echo "Models: Opus (extended thinking), Nova Pro, Mistral Large"
echo "Prompts: 10"
echo ""

cd "$PROJECT_DIR"
PYTHONUNBUFFERED=1 python3 -u harness.py --live --output "$OUTPUT_FILE"

echo ""
echo "Results saved to: $PROJECT_DIR/$OUTPUT_FILE"

# Copy live results to standard location for aggregators
cp "$OUTPUT_FILE" results/responses.json
echo "✓ Copied $OUTPUT_FILE to results/responses.json"

PYTHONUNBUFFERED=1 python3 -u aggregators/vote.py results/responses.json --live

PYTHONUNBUFFERED=1 python3 -u aggregators/stitch.py results/responses.json --live

PYTHONUNBUFFERED=1 python3 -u evaluate.py