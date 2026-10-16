#!/usr/bin/env bash
# PolicyGate host phase (run by MasterControl as root; read-only on /root/.openclaw).
# Uses only `policygate` subcommands (guard active), `jq`, and shell builtins.
# Writes ONLY to results/ and local/ inside this repo. Never calls openclaw,
# sqlite3, or any non-allowlisted git command. Prints a short summary per step.
#
# Usage: scripts/host_run.sh stage-a | stage-b
#
# Failure handling (phase 2a Bug 3): set -euo pipefail; each named step runs
# via step(), which prints "STEP FAILED: <name>" on a nonzero exit but lets
# the remaining independent steps finish; the script exits 1 at the end if any
# step failed.
set -euo pipefail
JQ=/usr/bin/jq
ROOT=/root/.openclaw
AGENTS=$ROOT/agents
BUNDLE=config/bundle.cabal.toml
DATE="$(date -u +%Y-%m-%d)"
FAILED=0
mkdir -p results local/runs local/host local/candidates local/labels

say() { echo ">> $*"; }

step() {  # step "<name>" <command...>  (shell snippet via step_sh below)
  local name="$1"; shift
  if "$@"; then
    return 0
  fi
  echo "STEP FAILED: $name"
  FAILED=1
  return 0
}

step_sh() {  # step_sh "<name>" '<shell snippet>'
  local name="$1"; shift
  if bash -euo pipefail -c "$1"; then
    return 0
  fi
  echo "STEP FAILED: $name"
  FAILED=1
  return 0
}

finish() {
  if [ "$FAILED" -ne 0 ]; then
    echo "host_run: one or more steps FAILED"
    exit 1
  fi
  echo "host_run: all steps OK"
}

stage_a() {
  say "stage-a: bundle probes (AC #3)"
  step_sh "bundle show 16:00Z" "policygate bundle show --root $ROOT --bundle $BUNDLE --at 2026-02-19T16:00:00Z --format json \
    | $JQ -r '.sources[\"global/BASE-AGENTS.md\"].commit[:8]' | sed 's/^/  16:00Z commit: /'"
  step_sh "bundle show 17:00Z" "policygate bundle show --root $ROOT --bundle $BUNDLE --at 2026-02-19T17:00:00Z --format json \
    | $JQ -r '.sources[\"global/BASE-AGENTS.md\"].commit[:8]' | sed 's/^/  17:00Z commit: /'"

  say "stage-a: parse at 17:00Z with the AC #4 qualifier check"
  step_sh "parse qualifier check" "policygate parse --root $ROOT --bundle $BUNDLE --at 2026-02-19T17:00:00Z --format json \
    | $JQ -e '[.clauses[] | select(.src.file==\"global/BASE-AGENTS.md\" and (.inherited_qualifiers | index(\"without explicit CC instruction\")))] | length >= 3' > /dev/null && echo '  qualifier inheritance: OK'"

  say "stage-a: parse dumps for authoring the real candidates (local/ only)"
  for t in 2026-02-19T16:00:00Z 2026-02-19T17:00:00Z 2026-04-03T03:00:00Z 2026-09-27T23:59:59Z; do
    step_sh "parse dump $t" "policygate parse --root $ROOT --bundle $BUNDLE --at '$t' --format json > 'local/host/parse-$t.json' && echo '  wrote local/host/parse-$t.json'"
  done

  say "stage-a: bundle history (per source: sha, committer time, A/M/D) via gitread log"
  step_sh "bundle history" "policygate bundle history --root $ROOT --bundle $BUNDLE \
    --since 2026-02-01T00:00:00Z --until 2026-09-28T00:00:00Z --format json \
    > local/host/bundle-history.json && echo '  wrote local/host/bundle-history.json'"

  say "stage-a: demo feb19 --verify-sources (read-only; PASS/FAIL only)"
  step_sh "verify-sources" "out=\$(policygate demo feb19 --verify-sources $ROOT); echo \"\$out\"; ! echo \"\$out\" | grep -q '^FAIL'"

  say "stage-a: spike-parity replay (AC #10/#18)"
  # keep the previous run's actions.jsonl: it holds the OLD action keys the
  # labels file may still be keyed on (stage-b rekey step, AC #19)
  step_sh "preserve previous parity run" "if [ -f local/runs/parity/actions.jsonl ] && [ ! -d local/runs/parity-prev ]; then \
    cp -r local/runs/parity local/runs/parity-prev && echo '  kept local/runs/parity-prev (old keys)'; \
  else echo '  no previous parity run to preserve (or parity-prev exists)'; fi"
  step_sh "spike-parity replay" "policygate replay --source legacy-archive --path $AGENTS --profile spike-parity \
    --format json --out local/runs/parity > 'results/replay-spike-parity-$DATE.json' \
    && cp 'results/replay-spike-parity-$DATE.json' 'results/replay-spike-parity-latest.json' \
    && $JQ -r '.parity_check | \"  parity: matches=\(.matches|length) deltas=\(.deltas|length)\"' 'results/replay-spike-parity-$DATE.json'"

  say "stage-a: ablation run (first-pass count)"
  step_sh "ablation replay" "policygate replay --source legacy-archive --path $AGENTS --profile spike-parity \
    --no-help-filter --no-heredoc-skip --format json --out local/runs/parity-ablation \
    | $JQ -r '\"  first-pass infra actions: \(.normalizer.ablation.no_help_no_heredoc)\"'"

  say "stage-a: results lint"
  step policygate_results_lint policygate results lint results/

  finish
}

stage_b() {
  say "stage-b: pinned replay (AC #14/#18)"
  if [ ! -f local/candidates/cabal.json ]; then
    echo "  NOTE: local/candidates/cabal.json not present; author it from the stage-a parse dumps."
  fi
  step_sh "pinned replay" "policygate replay --source legacy-archive --path $AGENTS --root $ROOT --bundle $BUNDLE \
    --candidates local/candidates/cabal.json --profile pinned --format json --out local/runs/pinned \
    > 'results/replay-pinned-$DATE.json' \
    && cp 'results/replay-pinned-$DATE.json' 'results/replay-pinned-latest.json' \
    && $JQ -r '.verdict_classes | to_entries[] | \"  \(.key): ALLOW=\(.value.ALLOW) BLOCK=\(.value.BLOCK) NO_RULE_IN_FORCE=\(.value.NO_RULE_IN_FORCE) VERSION_UNKNOWN=\(.value.VERSION_UNKNOWN)\"' 'results/replay-pinned-$DATE.json' \
    && $JQ -r '.retroactive_rules | \"  retroactive rules: \(keys | length) (flagged total \([.[].flagged] | add // 0); never counted as violations)\"' 'results/replay-pinned-$DATE.json'"

  say "stage-b: retroactive run (aggregates also to results/, for the COUNTERFACTUAL claim rows)"
  step_sh "retroactive replay" "policygate replay --source legacy-archive --path $AGENTS --root $ROOT --bundle $BUNDLE \
    --candidates local/candidates/cabal.json --profile pinned --retroactive \
    --format json --out local/runs/pinned-retroactive \
    > 'results/replay-pinned-retroactive-$DATE.json' \
    && cp 'results/replay-pinned-retroactive-$DATE.json' 'results/replay-pinned-retroactive-latest.json' \
    && $JQ -r '.counterfactual | \"  \(.label)\", (.readings | to_entries[] | \"    \(.key): \(.value.blocked)/\(.value.total)\")' 'results/replay-pinned-retroactive-$DATE.json'"

  say "stage-b: re-key labels if the old keys no longer join (AC #19 key change)"
  step_sh "rekey labels" "OLD_RUN=local/runs/parity-prev; [ -d \$OLD_RUN ] || OLD_RUN=local/runs/parity; \
  if [ -f local/labels/real-actions.jsonl ] && [ -f \$OLD_RUN/actions.jsonl ]; then \
    if python scripts/rekey_labels.py --old-run \$OLD_RUN --new-run local/runs/pinned \
         --labels local/labels/real-actions.jsonl --check-join; then \
      echo '  labels already join the pinned run; no rekey needed'; \
    else \
      python scripts/rekey_labels.py --old-run \$OLD_RUN --new-run local/runs/pinned \
        --labels local/labels/real-actions.jsonl --out local/labels/real-actions.rekeyed.jsonl \
      && mv local/labels/real-actions.jsonl local/labels/real-actions.oldkeys.jsonl \
      && mv local/labels/real-actions.rekeyed.jsonl local/labels/real-actions.jsonl \
      && echo '  labels re-keyed (old file kept as real-actions.oldkeys.jsonl)'; \
    fi; \
  else echo '  no labels file or no old run dir; skipping'; fi"

  say "stage-b: report + ambiguity on the pinned run"
  step_sh "report" "policygate report --run local/runs/pinned --format md > local/runs/pinned/report.md && echo '  report.md'"
  step_sh "ambiguity" "policygate ambiguity --run local/runs/pinned --format md > local/runs/pinned/ambiguity.md && echo '  ambiguity.md'"

  say "stage-b: eval with keyword baseline (written to results/, AC #19/#20)"
  step_sh "eval keyword baseline" "policygate eval --run local/runs/pinned --labels local/labels/real-actions.jsonl \
    --baseline keyword --format json > 'results/eval-pinned-$DATE.json' \
    && cp 'results/eval-pinned-$DATE.json' 'results/eval-pinned-latest.json' \
    && $JQ -r '\"  label_status: \(.label_status)\"' 'results/eval-pinned-$DATE.json' \
    && $JQ -r '.readings | to_entries[] | \"  \(.key): precision=\(.value.precision) recall=\(.value.recall)\"' 'results/eval-pinned-$DATE.json'"

  say "stage-b: scan-artifacts against the archive"
  step policygate_scan_artifacts policygate scan-artifacts --repo . --against-archive $AGENTS

  say "stage-b: results lint"
  step policygate_results_lint policygate results lint results/

  say "stage-b: host pytest"
  step host_pytest env PG_HOST_TESTS=1 python -m pytest -q -m host

  finish
}

case "${1:-}" in
  stage-a) stage_a ;;
  stage-b) stage_b ;;
  *) echo "usage: $0 stage-a|stage-b" >&2; exit 2 ;;
esac
