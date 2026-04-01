#!/usr/bin/env bash
# Run Persona Orchestrator experiment
# Tests: 7 personas on Sonnet with pick-best/synthesize/debate across 12 prompts
#
# Requires: AWS_BEARER_TOKEN_BEDROCK environment variable

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$REPO_DIR/ensemble-persona-orchestrator"
OUTPUT_FILE="results/live_persona.json"

if [ -z "${AWS_BEARER_TOKEN_BEDROCK:-}" ]; then
    echo "ERROR: AWS_BEARER_TOKEN_BEDROCK environment variable not set"
    exit 1
fi

echo "Persona Orchestrator Experiment"
echo "Model: Sonnet (all personas)"
echo "Personas: 7 (Systems Thinker, First Principles, Empiricist, Skeptical Analyst, Devil's Advocate, Domain Expert, Creative Problem Solver)"
echo "Strategies: pick-best, synthesize, debate"
echo "Prompts: 12"
echo ""

cd "$PROJECT_DIR"
PYTHONUNBUFFERED=1 python3 -u experiment.py --benchmark --output "$OUTPUT_FILE"

echo ""
echo "Results saved to: $PROJECT_DIR/results/benchmark_*.json"
