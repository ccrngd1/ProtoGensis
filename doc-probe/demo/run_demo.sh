#!/usr/bin/env bash
# DocProbe demo: score a sanitized good/bad instruction-file corpus.
#
# Default is fully offline (--no-llm): only the deterministic dimensions
# (discovery_accessibility, hierarchy, directive_density) are graded and the
# LLM dimensions are listed as skipped. Pass --llm to also run the semantic
# dimensions (requires Bedrock credentials).
set -euo pipefail
cd "$(dirname "$0")"

MODE="--no-llm"
if [[ "${1:-}" == "--llm" ]]; then
  MODE=""
fi

echo "=== DocProbe demo: good corpus ==="
docprobe scan corpus/good/AGENTS.md $MODE

echo
echo "=== DocProbe demo: bad corpus ==="
docprobe scan corpus/bad/CLAUDE.md corpus/bad/BURIED.md $MODE

echo
echo "=== JSON output (bad corpus) ==="
docprobe scan corpus/bad/CLAUDE.md $MODE --format json | head -50

echo
echo "=== Fix suggestions (bad corpus) ==="
docprobe fix corpus/bad/CLAUDE.md $MODE
