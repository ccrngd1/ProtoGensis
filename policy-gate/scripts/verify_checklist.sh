#!/usr/bin/env bash
# PolicyGate Verify Checklist (requirements verbatim in intent), with every
# /tmp/pg_* path replaced by paths under one T=$(mktemp -d). Each line is
# reported as "PASS|FAIL|SKIP <n> <command>"; a final TOTAL line follows.
# Off-host (or without PG_HOST_TESTS=1) the [host] block prints SKIP.
#
# Run from the repo root with the venv active:
#   source .venv/bin/activate && scripts/verify_checklist.sh

set -u
T="$(mktemp -d)"
JQ=/usr/bin/jq
PASS=0; FAIL=0; SKIP=0; N=0

run() {   # run "<description>" <command...>
  N=$((N+1))
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "PASS $N $desc"; PASS=$((PASS+1))
  else
    echo "FAIL $N $desc"; FAIL=$((FAIL+1))
  fi
}

runsh() {  # runsh "<description>" '<shell snippet>'
  N=$((N+1))
  local desc="$1"; shift
  if bash -c "$1" >/dev/null 2>&1; then
    echo "PASS $N $desc"; PASS=$((PASS+1))
  else
    echo "FAIL $N $desc"; FAIL=$((FAIL+1))
  fi
}

skip() {
  N=$((N+1))
  echo "SKIP $N $1"; SKIP=$((SKIP+1))
}

# ---- structure + license + ignore rules ----
runsh "structure files present" 'test -f pyproject.toml && test -f README.md && test -f BLOG.md && test -f LICENSE && test -f THIRD_PARTY_NOTICES.md && test -f .gitignore'
runsh "MIT license" 'grep -q "MIT License" LICENSE'
run "gitignore local/" git check-ignore -q local/anything
runsh "package modules present" 'for f in cli guard gitread bundle parse vocab vtools rules resolve emit normalize principal facts readings check replay report ambiguity amend evaluate scan results_lint claims demos; do test -f policygate/$f.py || exit 1; done'
runsh "subpackage modules present" 'for f in extract/candidates extract/vote extract/live_bedrock adapters/legacy_jsonl adapters/trajectory baselines/keyword; do test -f policygate/$f.py || exit 1; done'
runsh "docs + config present" 'for f in docs/RESULTS.md docs/CLAIMS.md docs/LABEL_RUBRIC.md docs/LIVE_ENFORCEMENT.md docs/PRIOR_ART.md docs/SCAN_ALLOWLIST.toml config/research_values.toml config/readings.toml config/vtools.toml config/platform_rules.toml config/bundle.cabal.toml fixtures/feb19/SOURCES.md fixtures/normalizer/cases.jsonl; do test -f $f || exit 1; done'

# ---- stdlib-only core, no plugin/live-enforcement code (AC 1, 26) ----
runsh "stdlib-only core" '! grep -rnE "^\s*(import|from) (boto3|botocore|pydantic|bashlex|yaml|requests|httpx|openai|anthropic|numpy)\b" policygate --include=*.py | grep -v policygate/extract/live_bedrock.py'
runsh "no declared runtime deps" "python -c 'import tomllib,sys; d=tomllib.load(open(\"pyproject.toml\",\"rb\")); sys.exit(1 if d[\"project\"].get(\"dependencies\") else 0)'"
runsh "no plugin manifest/package.json" 'test -z "$(find . -path ./node_modules -prune -o \( -name openclaw.plugin.json -o -name package.json \) -print)"'
runsh "no live-enforcement code in policygate" '! grep -rnE "before_tool_call|registerTrustedToolPolicy|requireApproval|plugins install" policygate --include=*.py'
runsh "LIVE_ENFORCEMENT not-implemented heading" 'grep -q "NOT IMPLEMENTED: requires CC approval" docs/LIVE_ENFORCEMENT.md'

# ---- read-only guard (AC 2) ----
runsh "guard selftest 9/9 (fresh root)" "rm -rf $T/pg_guard_root && policygate guard selftest --root $T/pg_guard_root | grep -q 'GUARD OK: 9/9'"
runsh "openclaw only named in guard.py" '! grep -rnE "['"'"'\"]openclaw['"'"'\"]\s*,|subprocess\.[a-z_]+\(\s*\[?\s*['"'"'\"]openclaw" policygate | grep -v policygate/guard.py'

# ---- offline tests, no creds, empty HOME (AC 24) ----
runsh "pytest offline, empty HOME, no creds" "env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN -u AWS_PROFILE -u OPENAI_API_KEY -u ANTHROPIC_API_KEY HOME=$(mktemp -d) python -m pytest -q"
runsh "conftest blocks socket" 'grep -q socket tests/conftest.py'

# ---- vocabulary + compile determinism (AC 5, 7, 8) ----
runsh "vocab list has MVP predicates" "policygate vocab list --format json | $JQ -e '[.[].name] | contains([\"cc_authorized\",\"principal_is\",\"agent_in\",\"quiet_hours_utc\",\"target_protected\",\"path_in\",\"weakens_policy\",\"checkpoint_seen\",\"host_in\",\"confirmation_fresh\",\"secret_in_args\"])'"
runsh "compile byte-identical" "rm -rf $T/pg_repo && python tests/fixtures/make_policy_repo.py $T/pg_repo >/dev/null && for i in 1 2; do policygate compile --root $T/pg_repo --bundle fixtures/bundle.synthetic.toml --at 2026-03-01T00:00:00Z --candidates fixtures/candidates/synthetic.json --out $T/pg_c\$i --format json > $T/pg_c\$i.json; done && cmp $T/pg_c1.json $T/pg_c2.json && cmp $T/pg_c1/rules.json $T/pg_c2/rules.json"
runsh "compile report fields" "$JQ -e '.candidate_origin == \"builder\" and (.coverage|type==\"number\") and (.resolve_counts|keys|length>=8) and (.unenforced_gateable|type==\"array\")' $T/pg_c1/compile-report.json"
runsh "rules check hand-edited wildcard exits 1" "cp fixtures/resolve/hand_edited_wildcard.rules.json $T/pg_he.json; policygate rules check $T/pg_he.json; test \$? -eq 1"
runsh "extract --live without --max-usd exits 2" "policygate extract --live bedrock --model-id x --votes 5 --bundle config/bundle.cabal.toml; test \$? -eq 2"

# ---- normalizer (AC 9) ----
runsh "normalizer corpus P/R" "policygate normalize --corpus fixtures/normalizer/cases.jsonl --format json | $JQ -e '.precision >= 0.95 and .recall >= 0.95 and .cases >= 150 and .negatives >= 60'"
runsh "heredoc + help handled" "policygate normalize --cmd \$'cat > /x.sh <<\\'EOF\\'\nopenclaw gateway restart\nEOF\nopenclaw cron disable abc --help' --format json | $JQ -e '.actions == [] and .heredoc_lines_skipped == 1'"

# ---- Feb-19, audit, adversarial, readings, amend (AC 12,13,15,16,17,20) ----
runsh "feb19 counts" "policygate demo feb19 --format json | $JQ -c '[.episodes.ep1_pinned.calls, .episodes.ep1_pinned.blocked, .episodes.ep1_counterfactual.blocked, .episodes.ep1_counterfactual.retroactive, .episodes.ep2_pinned.calls, .episodes.ep2_pinned.blocked, .weakens_policy_fired]' | grep -qx '\[11,0,10,true,10,9,true\]'"
runsh "feb19 double-fire = 4" "policygate demo feb19 --format json | $JQ -e '[.calls[] | select(.episode==\"ep2_pinned\" and (.fired|length)==2)] | length == 4'"
runsh "feb19 resolve block" "policygate demo feb19 --format json | $JQ -c '[.resolve[] | [.id,.outcome,.class]]' | grep -qx '\[\[\"TWR-PRE-01\",\"REPAIR\",\"write-scope\"\],\[\"TWR-FBD-02\",\"REPAIR\",\"argument-signature\"\],\[\"TWR-PRE-04\",\"REJECT\",\"unscoped-wildcard\"\]\]'"
runsh "feb19 banner first line" "policygate demo feb19 | head -1 | grep -q 'RECONSTRUCTED FIXTURE'"
# known-real IDs: sha256-hashed banned list + redacted-prefix rule in
# policygate/scan.py (this script holds no real ID or fragment). Covers every
# tracked/untracked file incl. tests/ and scripts/, raw and concatenation-split.
runsh "no real IDs committed (hashed list, incl. tests/ scripts/)" "policygate scan-artifacts --repo . --ids-only | grep -q 'SCAN OK'"
runsh "feb19 keyword baseline label" "policygate demo feb19 --baseline keyword --format json | $JQ -e '.baselines.keyword.label == \"agenthook-style keyword baseline (our reimplementation, not agenthook)\"'"
runsh "adversarial 0 accepted" "policygate demo adversarial --format json | $JQ -e '.accepted_authorizations == 0 and .cases >= 12'"
runsh "readings three totals" "policygate demo readings --format json | $JQ -e '(.totals | keys) == [\"lenient\",\"plan\",\"strict\"]'"
runsh "amend overlay not written" "policygate demo amend --format json | $JQ -e '.items_closed >= 1 and .overlay_written_to_policy_repo == false'"

# ---- version-pinned replay (AC 14) ----
runsh "pinning tests (AC 14)" "python -m pytest -q tests/test_pinning.py"

# ---- eval on synthetic fixture (AC 19) ----
runsh "eval matches expected" "diff <(policygate eval --run fixtures/eval/run --labels fixtures/eval/labels.jsonl --baseline keyword --format json) fixtures/eval/expected.json"

# ---- headline demo: offline, deterministic, bannered (AC 25) ----
runsh "demo all < 60s deterministic" "HOME=$(mktemp -d) timeout 60 policygate demo all --format json > $T/pg_d1.json && policygate demo all --format json > $T/pg_d2.json && cmp $T/pg_d1.json $T/pg_d2.json"
runsh "demo all 4 synthetic banners" "test \"\$(policygate demo all | grep -c 'SYNTHETIC FIXTURE: mechanism demo, not results from real transcripts')\" -eq 4"
runsh "demo all 1 recon banner" "test \"\$(policygate demo all | grep -c 'RECONSTRUCTED FIXTURE')\" -eq 1"

# ---- privacy (AC 21) ----
runsh "scan-artifacts SCAN OK" "policygate scan-artifacts --repo . | grep -q 'SCAN OK'"
runsh "results lint" "policygate results lint results/"

# ---- claims + honesty (AC 22, 23) ----
runsh "claims verify CLAIMS OK" "policygate claims verify | tail -1 | grep -q 'CLAIMS OK'"
runsh "no banned wording" '! grep -rniE "first (agents\.md|policy|tool|compiler|gate)|zero (existing )?alternatives|no (other )?tool (exists|does)|formal(ly)? (verif|security contract|gate|proof)|would have prevented (the )?cve|prevents? cve-2026-65616" README.md BLOG.md docs policygate'
runsh "reconstruction labels" "python scripts/check_reconstruction_labels.py README.md BLOG.md docs/*.md"
runsh "README prior-art names" 'for t in agenthook claude-enforce abide claude-md-doctor ToolReplay ContextCov Mondl AgentCore NOMOS "openclaw policy" MXC; do grep -q "$t" README.md || exit 1; done'
runsh "README deterministic + statically verified" 'grep -qi deterministic README.md && grep -qi "statically verified" README.md'
runsh "README has monorepo clone" 'grep -q "ccrngd1/ProtoGensis" README.md'
runsh "arXiv IDs allowlisted" 'test -z "$(grep -oE "\b[0-9]{4}\.[0-9]{5}\b" README.md BLOG.md | cut -d: -f2 | sort -u | grep -vxE "2610\.11030|2610\.18230|2609\.18820|2603\.00822|2606\.26649|2607\.07405|2606\.29225|2602\.16708|2507\.16459|2503\.18666|2606\.25189|2610\.20437")"'

# ---- [host] block: only with PG_HOST_TESTS=1 and readable /root/.openclaw ----
if [ "${PG_HOST_TESTS:-}" = "1" ] && [ -r /root/.openclaw ]; then
  runsh "[host] bundle show at 16:00Z = b314fe85" "policygate bundle show --root /root/.openclaw --bundle config/bundle.cabal.toml --at 2026-02-19T16:00:00Z --format json | $JQ -r '.sources[\"global/BASE-AGENTS.md\"].commit[:8]' | grep -qx b314fe85"
  runsh "[host] bundle show at 17:00Z = f84fecd8" "policygate bundle show --root /root/.openclaw --bundle config/bundle.cabal.toml --at 2026-02-19T17:00:00Z --format json | $JQ -r '.sources[\"global/BASE-AGENTS.md\"].commit[:8]' | grep -qx f84fecd8"
  runsh "[host] parse qualifiers >= 3" "policygate parse --root /root/.openclaw --bundle config/bundle.cabal.toml --at 2026-02-19T17:00:00Z --format json | $JQ -e '[.clauses[] | select(.src.file==\"global/BASE-AGENTS.md\" and (.inherited_qualifiers | index(\"without explicit CC instruction\")))] | length >= 3'"
  runsh "[host] demo feb19 --verify-sources 4 PASS" "test \"\$(policygate demo feb19 --verify-sources /root/.openclaw | grep -c '^PASS')\" -eq 4"
  runsh "[host] spike-parity parity_check 27" "policygate replay --source legacy-archive --path /root/.openclaw/agents --profile spike-parity --format json --out local/runs/parity | $JQ -e '.parity_check | (.matches|length)+(.deltas|length) == 27'"
  runsh "[host] pinned NO_RULE_IN_FORCE >= 3" "policygate replay --source legacy-archive --path /root/.openclaw/agents --root /root/.openclaw --bundle config/bundle.cabal.toml --candidates local/candidates/cabal.json --profile pinned --format json --out local/runs/pinned | $JQ -e '.verdict_classes.strict.NO_RULE_IN_FORCE >= 3'"
  runsh "[host] scan --against-archive SCAN OK" "policygate scan-artifacts --repo . --against-archive /root/.openclaw/agents | grep -q 'SCAN OK'"
  runsh "[host] host pytest" "PG_HOST_TESTS=1 python -m pytest -q -m host"
else
  skip "[host] bundle show at 16:00Z = b314fe85"
  skip "[host] bundle show at 17:00Z = f84fecd8"
  skip "[host] parse qualifiers >= 3"
  skip "[host] demo feb19 --verify-sources 4 PASS"
  skip "[host] spike-parity parity_check 27"
  skip "[host] pinned NO_RULE_IN_FORCE >= 3"
  skip "[host] scan --against-archive SCAN OK"
  skip "[host] host pytest"
fi

echo "TOTAL pass=$PASS fail=$FAIL skip=$SKIP"
rm -rf "$T"
[ "$FAIL" -eq 0 ]
