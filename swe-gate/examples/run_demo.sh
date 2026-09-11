#!/usr/bin/env bash
# SWE-Gate demo: an "all tests pass" patch that is broken four ways.
#
#   1. builds a scratch git repo from examples/baseline/ and commits it
#   2. applies examples/patch/ — a plausible-looking change seeded with:
#        - a hallucinated package import   (Layer 1)
#        - a wrong-arity internal call     (Layer 2)
#        - a weakened test                 (Layer 0)
#        - shell=True command interpolation (Layer 3)
#   3. runs pytest      -> green (the defects are invisible to the suite)
#   4. runs swe-gate    -> FAILED with all four layers attributing findings
#
# Usage: bash examples/run_demo.sh [workdir]

set -euo pipefail

EXAMPLES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="${1:-$(mktemp -d /tmp/swe-gate-demo.XXXXXX)}"

echo "==> Building demo repo in $WORKDIR"
mkdir -p "$WORKDIR"
cp -r "$EXAMPLES_DIR/baseline/." "$WORKDIR/"
cd "$WORKDIR"
git init -q -b main
git config user.email demo@swe-gate && git config user.name swe-gate-demo
git add -A && git commit -qm "baseline: note store with real tests"

echo
echo "==> Applying the 'helpful' patch (hallucinated import, wrong signature,"
echo "    weakened test, shell=True interpolation)"
cp -r "$EXAMPLES_DIR/patch/." "$WORKDIR/"

echo
echo "==> Step 1: the test suite is GREEN"
python3 -m pytest -q

echo
echo "==> Step 2: SWE-Gate on the same working tree"
set +e
swe-gate run --baseline HEAD "$WORKDIR"
GATE_EXIT=$?
set -e

echo
echo "==> swe-gate exit code: $GATE_EXIT (1 = gate failed, as intended)"
if [ "$GATE_EXIT" -ne 1 ]; then
    echo "DEMO BROKEN: expected exit 1" >&2
    exit 1
fi
echo "==> Demo complete. Tests passed; the gate caught all four defects."
