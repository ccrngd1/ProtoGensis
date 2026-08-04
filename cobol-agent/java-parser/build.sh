#!/usr/bin/env bash
# Build the ProLeap-backed parser JAR and install it where the Python side
# looks for it (assets/cobalt-parser-v0.jar).
#
# Requires: JDK 17+, Maven 3.8+, network access to Maven Central.
# If this build cannot run in your environment, Cobalt still works: the
# pure-Python fallback parser (cobalt/parser/fallback.py) is used
# automatically whenever the JAR is absent.
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v mvn >/dev/null 2>&1; then
    echo "error: mvn not found. Install Maven (e.g. apt-get install maven)" >&2
    echo "Cobalt will use the pure-Python fallback parser without the JAR." >&2
    exit 1
fi

mvn -q -DskipTests package

cp target/cobalt-parser-v0.jar ../assets/cobalt-parser-v0.jar
echo "Installed ../assets/cobalt-parser-v0.jar"
echo "Verify with: cobalt inspect assets/samples/claimcalc.cbl --parser java"
