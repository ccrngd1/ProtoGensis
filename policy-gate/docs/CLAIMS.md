# Claims ledger (AC #22)

Every own-run number in README.md / BLOG.md carries a `<!-- claim:ID -->`
marker whose ID appears here. `policygate claims verify` re-runs each command
and checks that `expected` appears in the output. `kind` is `offline` (re-run
anywhere) or `host_only` (SKIPPED off-host). The `research` column holds the
research-spike value where one exists; a mismatch needs a row in the
`docs/RESULTS.md` "Deltas vs research" table.

`PENDING_RERUN` marks a row whose value depends on a stage-b re-run (no row is
pending now; the phase-4 ambiguity rows and the phase-5
`verdict_classes_infra` row are filled). `claims verify` treats it like `PENDING_HOST` (SKIP
off-host, FAIL on-host); after the re-run MasterControl runs
`python scripts/fill_rerun_claims.py`, which replaces each `PENDING_RERUN` —
here and on the matching `<!-- claim:ID -->` lines in README/BLOG/RESULTS —
with the value the row's command prints.

External numbers use `<!-- cite:... -->` instead and are not in this table.

| id | kind | command | expected | research | note |
|---|---|---|---|---|---|
| feb19-ep1-pinned | offline | `policygate demo feb19 --format json \| jq -r '.episodes.ep1_pinned.blocked'` | `0` |  | no rule in force |
| feb19-ep1-counterfactual | offline | `policygate demo feb19 --format json \| jq -r '.episodes.ep1_counterfactual.blocked'` | `10` |  | labeled retroactive |
| feb19-ep2-pinned | offline | `policygate demo feb19 --format json \| jq -r '.episodes.ep2_pinned.blocked'` | `9` |  | pinned to f84fecd8 |
| feb19-ep2-calls | offline | `policygate demo feb19 --format json \| jq -r '.episodes.ep2_pinned.calls'` | `10` |  | episode 2 calls |
| feb19-double-fire | offline | `policygate demo feb19 --format json \| jq '[.calls[] \| select(.episode=="ep2_pinned" and (.fired\|length)==2)] \| length'` | `4` |  | both rules fire |
| adversarial-accepted | offline | `policygate demo adversarial --format json \| jq -r '.accepted_authorizations'` | `0` |  | forged auth rejected |
| adversarial-cases | offline | `policygate demo adversarial --format json \| jq -r '.cases'` | `13` |  | synthetic set size |
| normalizer-corpus-precision | offline | `policygate normalize --corpus fixtures/normalizer/cases.jsonl --format json \| jq -r '.precision'` | `1` |  | synthetic corpus |
| normalizer-corpus-recall | offline | `policygate normalize --corpus fixtures/normalizer/cases.jsonl --format json \| jq -r '.recall'` | `1` |  | synthetic corpus |
| synthetic-compile-coverage | offline | `policygate demo compile --format json \| jq -r '.coverage'` | `0.8333` |  | origin builder |
| archive-transcripts | host_only | `policygate results get results/replay-spike-parity-latest.json source.transcripts` | `2328` | `2328` | parity |
| archive-tool-calls | host_only | `policygate results get results/replay-spike-parity-latest.json source.tool_calls` | `41068` | `41068` | parity |
| exec-share | host_only | `policygate results get results/replay-spike-parity-latest.json source.exec_share` | `0.657` | `0.657` | parity |
| infra-actions | host_only | `policygate results get results/replay-spike-parity-latest.json normalizer.infra_actions` | `59` | `59` | parity |
| infra-actions-first-pass | host_only | `policygate results get results/replay-spike-parity-latest.json normalizer.ablation.no_help_no_heredoc` | `97` | `97` | ablation |
| unparsed-segments | host_only | `policygate results get results/replay-spike-parity-latest.json normalizer.unparsed` | `8093` | `8093` | parity |
| parity-strict | host_only | `policygate results get results/replay-spike-parity-latest.json readings.strict.blocked` | `47` | `47` | parity |
| parity-plan | host_only | `policygate results get results/replay-spike-parity-latest.json readings.plan.blocked` | `32` | `32` | parity |
| parity-lenient | host_only | `policygate results get results/replay-spike-parity-latest.json readings.lenient.blocked` | `11` | `11` | parity |
| parity-quiet-blocked | host_only | `policygate results get results/replay-spike-parity-latest.json quiet_hours.blocked_plan` | `17` | `17` | parity |
| parity-deltas-zero | host_only | `policygate results get results/replay-spike-parity-latest.json parity_check \| jq -r '.deltas \| length'` | `0` |  | 27/27 match |
| parity-replay-check | host_only | `policygate replay --source legacy-archive --path /root/.openclaw/agents --profile spike-parity --format json --out local/runs/parity_claim \| jq -r '.normalizer.infra_actions'` | `59` | `59` | re-runs the replay |
| pinned-strict | host_only | `policygate results get results/replay-pinned-latest.json readings.strict.blocked` | `53` | `47` | PolicyGate's own |
| pinned-plan | host_only | `policygate results get results/replay-pinned-latest.json readings.plan.blocked` | `46` | `32` | PolicyGate's own |
| pinned-lenient | host_only | `policygate results get results/replay-pinned-latest.json readings.lenient.blocked` | `42` | `11` | PolicyGate's own |
| no-rule-in-force | host_only | `policygate results get results/replay-pinned-latest.json verdict_classes.strict.NO_RULE_IN_FORCE` | `16` |  | version pinning |
| no-rule-in-force-infra | host_only | `policygate results get results/replay-pinned-latest.json verdict_classes_infra.strict.NO_RULE_IN_FORCE` | `4` |  | infra-only verdict split (phase-5 aggregate) |
| version-unknown | host_only | `policygate results get results/replay-pinned-latest.json verdict_classes.strict.VERSION_UNKNOWN` | `0` |  | version pinning |
| pinned-quiet-window | host_only | `policygate results get results/replay-pinned-latest.json quiet_hours.in_window` | `31` | `31` | pinned |
| pinned-quiet-blocked | host_only | `policygate results get results/replay-pinned-latest.json quiet_hours.blocked_plan` | `30` | `17` | pinned, plan reading |
| retroactive-rules-count | host_only | `policygate results get results/replay-pinned-latest.json retroactive_rules \| jq -r 'keys \| length'` | `5` |  | never violations |
| main-share | host_only | `policygate results get results/replay-spike-parity-latest.json by_agent.main` | `55` | `55` | main-dominated |
| eval-strict-precision | host_only | `policygate results get results/eval-pinned-latest.json readings.strict.precision` | `0.2453` |  | provisional labels |
| eval-plan-precision | host_only | `policygate results get results/eval-pinned-latest.json readings.plan.precision` | `0.2826` |  | provisional labels |
| eval-lenient-precision | host_only | `policygate results get results/eval-pinned-latest.json readings.lenient.precision` | `0.2619` |  | provisional labels |
| eval-strict-recall | host_only | `policygate results get results/eval-pinned-latest.json readings.strict.recall` | `1.0` |  | 13 positives, small n |
| eval-plan-recall | host_only | `policygate results get results/eval-pinned-latest.json readings.plan.recall` | `1.0` |  | 13 positives, small n |
| keyword-baseline-precision | host_only | `policygate results get results/eval-pinned-latest.json baselines.keyword.precision` | `0.1887` |  | reimplementation |
| keyword-baseline-recall | host_only | `policygate results get results/eval-pinned-latest.json baselines.keyword.recall` | `0.7692` |  | reimplementation |
| label-status | host_only | `policygate results get results/eval-pinned-latest.json label_status` | `provisional` |  | CC-D4 unanswered |
| label-policy-silent | host_only | `policygate results get results/eval-pinned-latest.json label_counts.policy-silent` | `4` |  | holes side of the title margin |
| label-unauthorized | host_only | `policygate results get results/eval-pinned-latest.json label_counts.unauthorized` | `13` |  | agents side of the title margin |
| normalizer-real-precision | host_only | `policygate results get results/eval-pinned-latest.json normalizer_precision_real` | `1.0` |  | no not-an-action rows |
| ambiguity-items-by-kind | host_only | `policygate results get results/replay-pinned-latest.json ambiguity_items` | `{"conflict": 4, "deferred_authorization": 1, "plan_reading": 4, "subject_scope": 2, "temporal_scope": 1}` |  | collapsed in phase 4 |
| ambiguity-items-total | host_only | `policygate results get results/replay-pinned-latest.json ambiguity_items \| jq -r '[.[]] \| add'` | `12` |  | collapsed in phase 4 |
| holes-vs-agents | host_only | `python -c "import json;e=json.load(open('results/eval-pinned-latest.json'));r=json.load(open('results/replay-pinned-latest.json'));h=e['label_counts'].get('policy-silent',0)+sum(r['ambiguity_items'].values());u=e['label_counts'].get('unauthorized',0);print(f'holes={h} unauthorized={u} holes_gt_agents={str(h>u).lower()}')"` | `holes=16 unauthorized=13 holes_gt_agents=true` |  | decides the BLOG title |
| feb19-ep1-calls | offline | `policygate demo feb19 --format json \| jq -r '.episodes.ep1_pinned.calls'` | `11` |  | episode 1 calls |
| spike-hand-rules | offline | `python -c "import tomllib;print(len(tomllib.load(open('config/profiles/spike_parity.toml','rb'))['rule']))"` | `4` |  | spike 1's hand-compiled rules |
| parity-matches | host_only | `policygate results get results/replay-spike-parity-latest.json parity_check \| jq -r '.matches \| length'` | `27` | `27` | tracked research values |
| parity-reading-swing | host_only | `policygate results get results/replay-spike-parity-latest.json readings \| jq -r '.strict.blocked / .lenient.blocked * 10 \| round / 10'` | `4.3` |  | strict/lenient ratio, naive replay |
| pinned-reading-swing | host_only | `policygate results get results/replay-pinned-latest.json readings \| jq -r '.strict.blocked / .lenient.blocked * 10 \| round / 10'` | `1.3` |  | strict/lenient ratio, pinned |
| candidates-count | host_only | `policygate candidates check --parse-dump local/host/parse-2026-02-19T16:00:00Z.json --parse-dump local/host/parse-2026-02-19T17:00:00Z.json --parse-dump local/host/parse-2026-04-03T03:00:00Z.json --parse-dump local/host/parse-2026-09-27T23:59:59Z.json --candidates local/candidates/cabal.json --format json \| jq -r '"\(.candidates_in) builder=\(.per_origin.builder)"'` | `26 builder=26` |  | builder-authored candidates |
| pinned-fbd08-involved | host_only | `policygate results get results/replay-pinned-latest.json rules.CAB-FBD-08 \| jq -r '"\(.strict) \(.plan) \(.lenient)"'` | `30 30 30` |  | quiet-hours rule fires (= blocks) per reading strict/plan/lenient |
| pinned-fbd08-authorized | host_only | `policygate results get results/eval-pinned-latest.json readings.strict.fired_by_label \| jq -r '.["CAB-FBD-08"] \| ."authorized-explicit" + ."authorized-plan"'` | `20` |  | of the 30 quiet-hours blocks, labelled authorized (provisional) |
| eval-strict-fp | host_only | `policygate results get results/eval-pinned-latest.json readings.strict.fp` | `40` |  | strict false positives, provisional labels |
| eval-strict-fp-authorized | host_only | `policygate results get results/eval-pinned-latest.json readings.strict.blocked_by_label \| jq -r '"explicit=\(."authorized-explicit") plan=\(."authorized-plan") silent=\(."policy-silent" // 0)"'` | `explicit=13 plan=27 silent=0` |  | strict blocks by provisional label |
| label-borderline-total | host_only | `policygate results get results/eval-pinned-latest.json borderline_counts \| jq -r '[.[]] \| add'` | `31` |  | borderline rows, CC-D4 |
| label-borderline-by-label | host_only | `policygate results get results/eval-pinned-latest.json borderline_counts \| jq -r '"plan=\(."authorized-plan" // 0) unauthorized=\(.unauthorized // 0) silent=\(."policy-silent" // 0) explicit=\(."authorized-explicit" // 0)"'` | `plan=23 unauthorized=6 silent=2 explicit=0` |  | borderline rows by label |
| feb19-commit-times | host_only | `jq -r '[.. \| objects \| select(.sha? and ((.sha\|startswith("f84fecd8")) or (.sha\|startswith("943e5e1d")))) \| .time] \| unique \| (((.[1]\|fromdate) - (.[0]\|fromdate)) / 60 \| round) as $m \| "\(.[0]) \(.[1]) gap=\($m/60\|floor)h\($m%60)m"' local/host/bundle-history.json` | `2026-02-19T16:38:16Z 2026-02-20T01:01:12Z gap=8h23m` |  | reconstruction (labeled): committer times of the rule commit and the rewrite commit, from the stage-a policygate bundle history dump |
| eval-strict-blocked-plan | host_only | `policygate results get results/eval-pinned-latest.json readings.strict.blocked_by_label.authorized-plan` | `27` |  | strict blocks on authorized-plan labels |
| eval-strict-blocked-explicit | host_only | `policygate results get results/eval-pinned-latest.json readings.strict.blocked_by_label.authorized-explicit` | `13` |  | strict blocks on authorized-explicit labels |
| label-borderline-plan | host_only | `policygate results get results/eval-pinned-latest.json borderline_counts.authorized-plan` | `23` |  | borderline authorized-plan rows |
| label-borderline-unauthorized | host_only | `policygate results get results/eval-pinned-latest.json borderline_counts.unauthorized` | `6` |  | borderline unauthorized rows (positives) |
| label-borderline-silent | host_only | `policygate results get results/eval-pinned-latest.json borderline_counts.policy-silent` | `2` |  | borderline policy-silent rows |
| amend-items-closed | offline | `policygate demo amend --format json \| jq -r '.items_closed'` | `2` |  | synthetic amend loop |
