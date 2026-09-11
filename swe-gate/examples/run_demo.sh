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
SWE_GATE_SRC="$(cd "$EXAMPLES_DIR/.." && pwd)"
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
# Prefer the installed console script; fall back to the module form so the
# demo runs from a source checkout without an editable install (PEP 668 hosts).
if command -v swe-gate >/dev/null 2>&1; then
    GATE=(swe-gate)
else
    GATE=(python3 -m swe_gate)
fi
set +e
( cd "$SWE_GATE_SRC" && "${GATE[@]}" run --baseline HEAD "$WORKDIR" )
GATE_EXIT=$?
set -e

echo
echo "==> swe-gate exit code: $GATE_EXIT (1 = gate failed, as intended)"
if [ "$GATE_EXIT" -ne 1 ]; then
    echo "DEMO BROKEN: expected exit 1" >&2
    exit 1
fi
echo "==> Demo complete: the suite was GREEN, but SWE-Gate blocked the patch."
echo "    Layers L0 (test tampering) and L1 (hallucinated import) fire with no"
echo "    extra tooling. For the full four-layer catch (L2 signatures, L3 security),"
echo "    install the scanners:  pip install -e '.[pyright]'  (bandit + semgrep are"
echo "    core deps; pyright is the optional extra). Absent them, those layers"
echo "    report a labeled, non-blocking SKIP — see the table above."
