#!/usr/bin/env bash
# Run MoA (Mixture-of-Agents) benchmark
# Tests: 3 ensemble configs (ultra-cheap, code-gen, reasoning) + baselines across 20 prompts
#
# Requires: AWS_BEARER_TOKEN_BEDROCK environment variable

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$REPO_DIR/ensemble-moa-bedrock-guide"
OUTPUT_FILE="results/live_benchmark.json"

if [ -z "${AWS_BEARER_TOKEN_BEDROCK:-}" ]; then
    echo "ERROR: AWS_BEARER_TOKEN_BEDROCK environment variable not set"
    exit 1
fi

echo "Mixture-of-Agents Benchmark"
echo "Configs: ultra-cheap, code-generation, reasoning"
echo "Baselines: Nova Lite, Haiku, Sonnet"
echo "Prompts: 20"
echo ""

cd "$PROJECT_DIR"
PYTHONUNBUFFERED=1 python3 -u benchmark/run.py --output "$OUTPUT_FILE"

echo ""
echo "Results saved to: $PROJECT_DIR/$OUTPUT_FILE"
