#!/usr/bin/env bash
# Regenerate the golden master from a real GnuCOBOL compile + run.
# Requires: cobc (GnuCOBOL 3.x) on PATH.
set -euo pipefail
cd "$(dirname "$0")/.."   # assets/samples
tmpbin="$(mktemp -d)/claimcalc"
cobc -x -Wall -I copy -o "$tmpbin" claimcalc.cbl
"$tmpbin" > golden/expected_output.txt
echo "Golden master regenerated: golden/expected_output.txt"
