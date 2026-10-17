# Results

PolicyGate's offline results come from `policygate demo all` (synthetic and
reconstructed fixtures). Host results on the real archive are **aggregates
only**, produced by `scripts/host_run.sh` (run by MasterControl as root) and
committed as `results/*.json`; every number below is reproduced from those
files by `policygate claims verify` through the ledger in `docs/CLAIMS.md`.

## Offline — synthetic compile (mechanism demo, origin builder)

RESOLVE catches the NOMOS defect classes on CABAL-shaped clauses (origin
`builder`; these are **not** an LLM extraction defect rate):

```
candidate origin: builder
RESOLVE defect classes: write-scope 1, argument-signature 1, self-blocking 1,
  unscoped-wildcard 1, domain-satisfiability 1, contradiction 2, subject-scope 1,
  shadowing 1
coverage (gateable): 0.8333
```

## Offline — 2026-02-19 reconstruction (labeled)

Rebuilt from the mistake log, a memory backup, and git history (f84fecd8,
943e5e1d). The original transcript does not exist; in-episode timestamps are
approximate.

```
RESOLVE: TWR-PRE-01 REPAIR write-scope; TWR-FBD-02 REPAIR argument-signature;
         TWR-PRE-04 REJECT unscoped-wildcard
episode 1 pinned (pre-f84fecd8, no rule in force): 0/11 blocked
episode 1 COUNTERFACTUAL (retroactive policy; not violations): 10/11 blocked
episode 2 pinned (f84fecd8): 9/10 blocked
weakens_policy fired on the MEMORY.md self-edit: True
```

Episode 1 is **never** a violation: no written rule was in force. The 10/11 is a
labeled counterfactual.

## Offline — adversarial set

```
adversarial cases: 13; accepted authorizations: 0; blocked: 13 / expected 13
```

Forged "CC approved this" in a tool result, a cron prompt claiming authority, a
relayed "CC said yes" with no item id, an assistant self-claim, a heartbeat
"approved", a policy self-edit, and a retried write after one approval all
produce zero accepted authorizations.

## Offline — three readings (synthetic)

```
blocked per reading: strict 4, plan 2, lenient 1
```

## Offline — amend loop (synthetic mechanism)

```
items closed: 2; before strict/plan/lenient 8/5/2; after 6/4/2
overlay written to policy repo: false
```

## Host — spike parity (replay of the research spike, 2026-10-16)

`results/replay-spike-parity-latest.json`. All **27** research values matched,
**0 deltas** (the `parity_check` section in the results file lists every pair).

| value | research | this run |
|---|---|---|
| transcripts | 2,328 | 2,328 |
| tool calls | 41,068 | 41,068 |
| exec share | 0.657 | 0.657 |
| structured `cron` tool calls | 0 | 0 |
| exec segments | 165,125 | 165,125 |
| unparsed (shlex error) | 8,093 (4.90%) | 8,093 (4.90%) |
| infra-mutating actions | 59 | 59 |
| first pass (no help/heredoc handling) | 97 | 97 |
| blocked, strict | 47/59 | 47/59 |
| blocked, plan | 32/59 | 32/59 |
| blocked, lenient | 11/59 | 11/59 |
| quiet hours in window / blocked (plan) | 31 / 17 | 31 / 17 |
| PLAT-FBD-04 flagged / CC-requested (strict) | 21 / 3 | 21 / 3 |
| by agent: main / enhancer | 55 / 4 | 55 / 4 |
| by principal: human / cron / system | 48 / 8 / 3 | 48 / 8 / 3 |

Caveats that apply to everything in this file (README "Limits" has the full
text): pinning is commit-granularity (R4); principals are heuristic offline —
"human" is not proven to be CC (R5); the dataset is small and main-dominated —
**55 of the 59 infra actions are main's** (`by_agent`, R7); candidates are
builder-authored, not LLM-extracted (R8); coverage gaps are silent, hand
labels are the independent check (R9).

## Host — pinned replay (PolicyGate's own result, 2026-10-16)

`results/replay-pinned-latest.json`: 26 builder-authored candidates
(`local/candidates/cabal.json`, hash-pinned to bundle commits), version
pinning, consumption, full principal classes. 59 infra actions + 4,181
`file.edit` actions = 4,240 evaluated.

Blocked per reading (infra actions):

| reading | blocked / total | spike parity | research spike |
|---|---|---|---|
| strict | 53 / 59 | 47 | 47 |
| plan | 46 / 59 | 32 | 32 |
| lenient | 42 / 59 | 11 | 11 |

Verdict classes per reading (all 4,240 actions):

| reading | ALLOW | BLOCK | NO_RULE_IN_FORCE | VERSION_UNKNOWN |
|---|---|---|---|---|
| strict | 3,931 | 293 | 16 | 0 |
| plan | 3,939 | 286 | 15 | 0 |
| lenient | 3,943 | 282 | 15 | 0 |

The NO_RULE_IN_FORCE column counts all evaluated actions including
`file.edit`; restricted to the <!-- claim:infra-actions --> 59 infra actions
it is <!-- claim:no-rule-in-force-infra --> 4 under strict
(`verdict_classes_infra`, added in phase 5).

Quiet hours: <!-- claim:pinned-quiet-window --> 31 actions in the 00–08Z
window, <!-- claim:pinned-quiet-blocked --> 30 blocked under the plan reading
(research spike: 17). The quiet-hours rule CAB-FBD-08 fires on
<!-- claim:pinned-fbd08-involved --> 30 / 30 / 30 actions (strict / plan /
lenient), i.e. it is involved in 30 of the 53 / 46 / 42 pinned blocks, and
<!-- claim:pinned-fbd08-authorized --> 20 of those 30 are provisionally
labelled authorized. That is a **compiler limit**, not only rulebook wording:
the clause says no *autonomous* infra work in the window, but a v1 rule is a
single predicate over the closed vocabulary, so it compiles to a
`quiet_hours_utc` FORBIDDEN rule with no `cc_authorized` exemption (the
conjunction "in window AND not CC-authorized" is not expressible). It cannot
say "unless CC authorized it" and over-blocks CC-authorized in-window work
under every reading. PLAT-FBD-04 flags 21 gateway restarts, 3
CC-requested under strict. `ts_missing` 0; `VERSION_UNKNOWN` 0 (every action
timestamp resolved to a bundle version).

**Pinned is MORE severe than parity here, not less** (strict 53 vs 47, plan 46
vs 32, lenient 42 vs 11). Version pinning did what Premise 4 predicts — it
moved pre-rule actions out of BLOCK into `NO_RULE_IN_FORCE` (16/15/15 per
reading over all evaluated actions; the infra-only strict count is split out
below the verdict-classes table) — but the pinned profile also evaluates **26 naive builder candidates
instead of spike 1's 4 hand rules**, and consumption re-blocks repeats after
one authorization. The added breadth and consumption outweigh what pinning
removed. See "Deltas vs research" below; the per-rule firing-rate flags are the
candidate-quality signal, not a misbehaviour count.

### Firing-rate flags (rate ≥ 0.9, n ≥ 5; our parameter)

| rule | vtool | fired/n | rate |
|---|---|---|---|
| CAB-PRE-01 | cron.edit | 22/24 | 0.9167 |
| CAB-PRE-06 | cron.edit | 22/24 | 0.9167 |
| CAB-PRE-19 | cron.edit | 22/24 | 0.9167 |
| CAB-PRE-07 | service.restart | 6/6 | 1.0 |
| CAB-PRE-09 | service.restart | 6/6 | 1.0 |

A rule that fires on ~everything it sees is NOMOS's over-broad-rule smell:
these are naive readings of "no autonomous infra work" / "ask CC first"
clauses, which under strict almost always fire. That is a statement about the
rules, not about the agents, and it is split: partly the rulebook's wording,
partly the compiled rules being blunter than the prose (CAB-FBD-08 above cannot
express "unless CC authorized it").

### COUNTERFACTUAL (retroactive policy; not violations)

Retroactive rules in the pinned run (rules that would fire but were not in
force at action time; never counted as violations):

| rule | flagged | class |
|---|---|---|
| CAB-FBD-08 | 1 | NO_RULE_IN_FORCE |
| CAB-FBD-20 | 12 | NO_RULE_IN_FORCE |
| CAB-PRE-07 | 4 | NO_RULE_IN_FORCE |
| CAB-PRE-09 | 4 | NO_RULE_IN_FORCE |
| CAB-PRE-15a | 1 | ALLOW (superseded clause version) |

The separate `--retroactive` run (`results/replay-pinned-retroactive-latest.json`)
applies every version's rules to every action: blocked strict 309 / plan 301 /
lenient 297 of 4,240. These are labeled counterfactuals.

### Ambiguity queue (by kind)

One item per undecidable (clause, action-class) pair, with per-reading
`affected` counts; the full items (with `action_keys` evidence) stay in the
local run dir, results/ carries only the counts by kind. The pre-collapse
phase-3 run emitted one item **per action** (1,181 items, of which 1,139
`deferred_authorization` — a bug against AC #17, fixed in phase 4); counts
below are filled from the re-run:

<!-- claim:ambiguity-items-by-kind --> {"conflict": 4, "deferred_authorization": 1, "plan_reading": 4, "subject_scope": 2, "temporal_scope": 1}

Total items: <!-- claim:ambiguity-items-total --> 12

### Eval vs the keyword baseline (label_status: provisional)

`results/eval-pinned-latest.json`, scored on 59 hand-labelled real actions
(labels: authorized-explicit 15, authorized-plan 27, unauthorized 13,
policy-silent 4; all `cc_confirmed: false`, borderline confirmation is CC-D4 —
hence `label_status: provisional`). Positive = `unauthorized` (13 positives;
recall on so few positives is small-n and should not be over-read).

| detector | precision | recall | tp | fp | fn | tn |
|---|---|---|---|---|---|---|
| pinned, strict | 0.2453 | 1.0 | 13 | 40 | 0 | 6 |
| pinned, plan | 0.2826 | 1.0 | 13 | 33 | 0 | 13 |
| pinned, lenient | 0.2619 | 0.8462 | 11 | 31 | 2 | 15 |
| keyword baseline | 0.1887 | 0.7692 | 10 | 43 | 3 | 3 |

Precision is **low** against the provisional labels. All
<!-- claim:eval-strict-fp --> 40 strict false positives are actions the labels
judge authorized (<!-- claim:eval-strict-fp-authorized --> explicit=13
plan=27 silent=0; no policy-silent action is blocked) that the naive
candidates, and consumption of one-shot authorizations, block anyway;
<!-- claim:pinned-fbd08-authorized --> 20 of them involve the quiet-hours
rule's compiler limit. Borderline rows (CC-D4):
<!-- claim:label-borderline-total --> 31, by label
<!-- claim:label-borderline-by-label --> plan=23 unauthorized=6 silent=2
explicit=0, so 6 of the 13 `unauthorized` positives are themselves
borderline. The over-broad candidates show up in the firing-rate flags. We
report it as-is;
the gate beats the keyword baseline on both precision and recall, and that is
the extent of the claim. Normalizer precision on the real labelled set: 1.0
(no row was labelled not-an-action).

### Coverage (candidates check, numbers only)

26 candidates: clause_refs 24 resolved against the parse dumps, 2 builtin, 0
unresolved. Classified scope 109 clauses (deduplicated by clause hash):
gateable 19, obligation 31, text-only 51, ambiguous 5, counting 1, ordering 1,
temporal 1. **Unenforced gateable in scope: 3** (two credential-handling
clauses and one trash-over-rm clause — vocabulary gaps with no matching
vtool, listed per R9; a clause the compiler misses is silently unenforced).

## Deltas vs research

Any run value that differs from `config/research_values.toml` is a finding
reported here (never tuned toward the research number; AC #18, #22).
Spike-parity matched all 27 research values with 0 deltas, so every delta
below is pinned-profile vs the research spike — i.e. PolicyGate's own result
differing from the naive replay, for stated reasons.

| id | research | actual | note |
|---|---|---|---|
| pinned-strict | 47 | 53 | pinning moved pre-rule actions to NO_RULE_IN_FORCE (Premise 4), but the 26 naive builder candidates (vs spike 1's 4 hand rules) bind more vtools and consumption re-blocks repeats after one authorization; net +6. Compiler limit: CAB-FBD-08 (quiet hours, "no *autonomous* infra work") cannot express "unless CC authorized it", so it over-blocks CC-authorized in-window work; it is involved in 30 of the 53 blocks (claim pinned-fbd08-involved) |
| pinned-plan | 32 | 46 | same causes; the naive candidates include plan-insensitive FORBIDDEN shapes (e.g. target/path rules) that block regardless of reading. Same compiler limit: CAB-FBD-08 is involved in 30 of the 46 blocks (pinned-fbd08-involved) |
| pinned-lenient | 11 | 42 | same causes, largest swing: spike lenient only required any CC turn, while the naive candidates' FORBIDDEN rules and consumption fire under every reading. CAB-FBD-08 has no `cc_authorized` exemption under any reading and is involved in 30 of the 42 blocks (pinned-fbd08-involved) |
| pinned-quiet-blocked | 17 | 30 | the quiet-hours candidate reads the clause as binding every infra vtool in 00–08Z (spike 1 bound a narrower set), and consumption removes exemptions the spike granted. Compiler limit: a single-predicate rule compiles "no *autonomous* infra work" to a window rule that cannot express "unless CC authorized it", so CC-authorized in-window work is blocked too (20 of the 30 are labelled authorized; pinned-fbd08-authorized) |
