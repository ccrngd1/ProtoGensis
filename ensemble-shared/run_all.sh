#!/usr/bin/env bash
# Run all three ensemble experiments sequentially
# Usage: ./run_all.sh [--output-dir DIR]
#
# Requires: AWS_BEARER_TOKEN_BEDROCK environment variable

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${1:-}"

if [ -z "${AWS_BEARER_TOKEN_BEDROCK:-}" ]; then
    echo "ERROR: AWS_BEARER_TOKEN_BEDROCK environment variable not set"
    exit 1
fi

echo "============================================================"
echo "ENSEMBLE EXPERIMENTS - FULL SUITE"
echo "============================================================"
echo "Started: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""

TOTAL_START=$(date +%s)

echo ">>> Experiment 1/3: Thinking Models"
echo "------------------------------------------------------------"
"$SCRIPT_DIR/run_thinking_models.sh"
echo ""

echo ">>> Experiment 2/3: Mixture-of-Agents"
echo "------------------------------------------------------------"
"$SCRIPT_DIR/run_moa.sh"
echo ""

echo ">>> Experiment 3/3: Persona Orchestrator"
echo "------------------------------------------------------------"
"$SCRIPT_DIR/run_persona.sh"
echo ""

TOTAL_END=$(date +%s)
TOTAL_ELAPSED=$((TOTAL_END - TOTAL_START))

echo "============================================================"
echo "ALL EXPERIMENTS COMPLETE"
echo "============================================================"
echo "Total time: ${TOTAL_ELAPSED}s"
echo "Finished: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""
echo "Results:"
echo "  Thinking Models: ensemble-thinking-models/results/live_responses.json"
echo "  MoA Benchmark:   ensemble-moa-bedrock-guide/results/live_benchmark.json"
echo "  Persona:         ensemble-persona-orchestrator/results/benchmark_*.json"
