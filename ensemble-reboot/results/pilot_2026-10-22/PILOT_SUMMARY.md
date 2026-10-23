# Pilot Summary — run `pilot_2026-10-22`

**PILOT. n=10 items per task set. All accuracy numbers are n=10 (or vote-level
n=10); Wilson 95% CIs are wide and NO conclusions about arm or model ranking
should be drawn from them.** This document exists to (a) verify the harness
end-to-end on live Bedrock, (b) measure tokens/cost/latency for the full-run
estimate, and (c) pick the best single model B per set for arm construction.

Record provenance: `results/pilot_2026-10-22/records.jsonl` (1,139 records:
1,049 live API calls + 90 programmatic-vote records). Every cell below carries
its record_ids inline, or points at `summary.md` / `record_groups.json`
(written by `scripts/summarize.py pilot_2026-10-22`), or gives the exact
filter query. No mock records exist in this run (`is_mock=false` on all rows;
`RecordStore.load_all()` refuses mock records).

---

## 1. Stages completed and budget

| Stage | Status | Records | API cost |
|---|---|---|---|
| stage0 (calibration, 10 models × 3 sets × 10 items, default effort) | COMPLETE | 300 | $16.0842 |
| stage1 (arms A2/A3/A4a/A4b + vote baselines, default effort) | COMPLETE | 480 (390 API + 90 vote) | $6.8764 |
| stage2 (effort sweep) | PARTIAL — budget cap hit | 359 | $52.5022 |

**$75 cap: HIT.**

- **Billed spend: $75.4628 over 1,049 API calls** — equals the BudgetGuard
  final status (`results/pilot_run.log`,
  `manifest.json#budget.spent_known_usd = 75.4628`).
- **Attributed vote-event cost: $12.4328 over 90 programmatic-vote records —
  NOT billed.** Each vote record stores the sum of its parent proposal calls'
  costs (the a4-vote records even re-attribute stage0 panel records); those
  parents are already in the billed total, so adding vote rows on top
  double-counts. A naive `sum(cost_usd)` over all 1,139 records gives
  $87.8956 and is wrong as a spend figure.
- **Unrecorded spend:** up to 8 calls were in flight when the gateway
  restarted at ~22:03Z (stage0 gpt-6.1-sol math/code at default effort;
  observed max $0.02675/call, so ≤ about $0.22), plus any silent retries in
  the old client (not logged, unknown; none was likely, because max latency 849s < 1800s timeout (record 7f11cb33621441ff), but this is unverified). Not cross-checked against
  AWS billing.
- The overshoot past $75.00 is in-flight calls that were already reserved
  when the cap tripped. `unknown_price_calls = 0` — every call had an OK
  price.

### Spend reconciliation

Over `records.jsonl` (1,139 records; `ensemble_reboot.records.is_billed` =
`r.get("billed", r["model_id"] != "programmatic-vote")`):

| number | value | reproducible query |
|---|---|---|
| billed spend | $75.4628 | `sum(r["cost_usd"] for r in records if is_billed(r))` (= `billed_spend(records)`); 1,049 records |
| attributed vote cost | $12.4328 | `sum(r["cost_usd"] for r in records if not is_billed(r))`; 90 records |
| naive (double-counting) sum | $87.8956 | `sum(r["cost_usd"] for r in records)` — do not use as spend |
| guard final | $75.4628 | `manifest.json#budget.spent_known_usd`; also last `running total` line in `results/pilot_run.log` |
| per-stage billed | $16.0842 / $6.8764 / $52.5022 | `sum(r["cost_usd"] for r in records if is_billed(r) and r["stage"] == S)` for stage0/1/2 |
| unrecorded (gateway restart) | ≤ ~$0.22 | 8 workers × max observed stage0 gpt-6.1-sol math/code call ($0.02675; query: `max(cost_usd)` over those records) |
| silent-retry exposure (old client) | unknown, likely $0 | not logged pre-fix; max latency 849s < 1800s timeout ⇒ no timeout retries likely. Fixed going forward (`attempts` in records, `ambiguous_charge_usd` in guard status) |

Stage2 coverage at the cap:
- `claude-fable-5-1`: low/medium/xhigh/max complete (default high came from stage0)
- `claude-opus-5-5`: low/high/xhigh/max complete (default medium from stage0)
- `gpt-6-astra`: low/high/xhigh complete; max 29/30 (missing item `lcb-arc194_d`
  on code — query: compare `manifest.json#items_per_set.code` against
  `{r["item_id"]: r for r in records if r["model_id"]=="global.openai.gpt-6-astra" and r["effort"]=="max" and r["task_set"]=="code"}`)
- NOT reached: gpt-6.1-sol, grok-4.7, kimi-k3, sonnet-5-5, haiku-5-5,
  gpt-6-luna, nova-2-lite (no non-default-effort data for these)

---

## 2. Per model × task set (stage0, default effort) — PILOT, n=10

Columns: accuracy (Wilson 95% CI), mean input/output tokens per item, cost per
item, p50/p95 latency (s), truncation count (stop_reason=max_tokens at the
32,000-token limit), error count (failed API calls after retries).
**Error count is 0 for every cell**: zero `call failed` lines in
`results/pilot_run.log` and all 300 stage0 records carry a grader verdict.

Record_ids for every cell: `summary.md` table rows with `arm=a1` /
`stage=stage0` (10 ids inline per cell), or
`[r["record_id"] for r in records if r["stage"]=="stage0" and r["model_id"]==M and r["task_set"]==T]`.

### GPQA (n=10 each — PILOT, too small for conclusions)
| model | effort | acc [95% CI] | in/out tok | $/item | p50/p95 lat | trunc | err |
|---|---|---|---|---|---|---|---|
| anthropic.claude-opus-5-5 | medium | 9/10 (90%) [60%,98%] | 322 / 833 | $0.0180 | 7.7 / 15.9 | 0 | 0 |
| openai.gpt-6-astra | medium | 9/10 (90%) [60%,98%] | 233 / 377 | $0.0212 | 4.1 / 29.1 | 0 | 0 |
| moonshotai.kimi-k3 | max | 9/10 (90%) [60%,98%] | 316 / 5089 | $0.0773 | 20.4 / 668.6 | 0 | 0 |
| openai.gpt-6.1-sol | medium | 8/10 (80%) [49%,94%] | 233 / 344 | $0.0039 | 5.5 / 26.0 | 0 | 0 |
| anthropic.claude-sonnet-5-5 | medium | 8/10 (80%) [49%,94%] | 322 / 629 | $0.0069 | 5.0 / 9.7 | 0 | 0 |
| anthropic.claude-fable-5-1 | high | 8/10 (80%) [49%,94%] | 322 / 663 | $0.0364 | 6.6 / 36.8 | 0 | 0 |
| openai.gpt-6-luna | medium | 7/10 (70%) [40%,89%] | 233 / 1714 | $0.0009 | 14.2 / 43.1 | 0 | 0 |
| xai.grok-4.7 | high | 7/10 (70%) [40%,89%] | 237 / 14173 | $0.0855 | 204.8 / 828.0 | 2 | 0 |
| anthropic.claude-haiku-5-5 | medium | 6/10 (60%) [31%,83%] | 322 / 1860 | $0.0010 | 6.2 / 15.9 | 0 | 0 |
| amazon.nova-2-lite-v1:0 | medium | 5/10 (50%) [24%,76%] | 291 / 17198 | $0.0431 | 85.3 / 181.8 | 1 | 0 |

### Math (AIME/HMMT 2026, n=10 each — PILOT)
| model | effort | acc [95% CI] | in/out tok | $/item | p50/p95 lat | trunc | err |
|---|---|---|---|---|---|---|---|
| openai.gpt-6-luna | medium | 10/10 (100%) [72%,100%] | 127 / 4981 | $0.0025 | 24.5 / 159.6 | 0 | 0 |
| openai.gpt-6.1-sol | medium | 10/10 (100%) [72%,100%] | 127 / 1373 | $0.0140 | 18.4 / 61.3 | 0 | 0 |
| anthropic.claude-opus-5-5 | medium | 10/10 (100%) [72%,100%] | 189 / 2503 | $0.0508 | 13.3 / 78.3 | 0 | 0 |
| openai.gpt-6-astra | medium | 10/10 (100%) [72%,100%] | 127 / 1291 | $0.0658 | 15.1 / 60.9 | 0 | 0 |
| moonshotai.kimi-k3 | max | 10/10 (100%) [72%,100%] | 205 / 11367 | $0.1711 | 104.2 / 676.1 | 0 | 0 |
| anthropic.claude-fable-5-1 | high | 10/10 (100%) [72%,100%] | 189 / 4974 | $0.2506 | 23.7 / 310.6 | 0 | 0 |
| anthropic.claude-sonnet-5-5 | medium | 9/10 (90%) [60%,98%] | 189 / 2172 | $0.0221 | 9.9 / 49.7 | 0 | 0 |
| anthropic.claude-haiku-5-5 | medium | 8/10 (80%) [49%,94%] | 189 / 7387 | $0.0037 | 16.4 / 114.9 | 0 | 0 |
| amazon.nova-2-lite-v1:0 | medium | 7/10 (70%) [40%,89%] | 197 / 13942 | $0.0349 | 51.8 / 196.5 | 2 | 0 |
| xai.grok-4.7 | high | 5/10 (50%) [24%,76%] | 138 / 23580 | $0.1418 | 407.3 / 849.0 | 5 | 0 |

### Code (LiveCodeBench slice, n=10 each — PILOT)
| model | effort | acc [95% CI] | in/out tok | $/item | p50/p95 lat | trunc | err |
|---|---|---|---|---|---|---|---|
| openai.gpt-6.1-sol | medium | 9/10 (90%) [60%,98%] | 473 / 813 | $0.0091 | 11.9 / 39.1 | 0 | 0 |
| anthropic.claude-opus-5-5 | medium | 9/10 (90%) [60%,98%] | 629 / 1540 | $0.0333 | 15.7 / 25.3 | 0 | 0 |
| openai.gpt-6-astra | medium | 9/10 (90%) [60%,98%] | 473 / 799 | $0.0447 | 12.9 / 30.9 | 0 | 0 |
| anthropic.claude-fable-5-1 | high | 9/10 (90%) [60%,98%] | 629 / 1901 | $0.1013 | 18.3 / 82.6 | 0 | 0 |
| openai.gpt-6-luna | medium | 8/10 (80%) [49%,94%] | 473 / 3070 | $0.0016 | 18.0 / 66.6 | 0 | 0 |
| anthropic.claude-haiku-5-5 | medium | 8/10 (80%) [49%,94%] | 629 / 4978 | $0.0026 | 13.0 / 100.8 | 0 | 0 |
| anthropic.claude-sonnet-5-5 | medium | 8/10 (80%) [49%,94%] | 629 / 1145 | $0.0127 | 8.5 / 15.2 | 0 | 0 |
| moonshotai.kimi-k3 | max | 8/10 (80%) [49%,94%] | 546 / 13237 | $0.2002 | 161.3 / 661.5 | 0 | 0 |
| xai.grok-4.7 | high | 6/10 (60%) [31%,83%] | 438 / 20236 | $0.1223 | 415.8 / 844.2 | 3 | 0 |
| amazon.nova-2-lite-v1:0 | medium | 3/10 (30%) [11%,60%] | 537 / 11637 | $0.0293 | 51.4 / 103.7 | 0 | 0 |

Truncations total 23 across the whole run (incl. stage2); per-cell counts in
`summary.md` (`trunc` column). Query:
`[r["record_id"] for r in records if r["truncated"]]`.

---

## 3. Best single model B and headroom check

Selection rule (`ensemble_reboot.pilot.pick_best_by_set`): highest stage0
accuracy, ties broken toward lower total cost.

| set | B (best single model) | acc | tie group (same accuracy) |
|---|---|---|---|
| gpqa | **claude-opus-5-5** | 9/10 | astra ($0.21), kimi-k3 ($0.77) — opus cheapest at $0.180/10 |
| math | **gpt-6-luna** | 10/10 | sol, opus, astra, kimi, fable all 10/10 — luna cheapest at $0.025/10 |
| code | **gpt-6.1-sol** | 9/10 | opus, astra, fable — sol cheapest at $0.091/10 |

Overall (sum across 3 sets): gpt-6-astra and claude-opus-5-5 tie at 28/30;
query: group stage0 records by model, sum `correct`.

**Headroom check (<80%?): FAILS on all three sets** (output of
`python3 scripts/headroom_check.py pilot_2026-10-22`, record_ids printed there):

| set | best B accuracy | <80%? | recommended harder slice |
|---|---|---|---|
| gpqa | 90% [60%,98%] | NO | no official harder slice; use consensus-wrong items only, or GPQA-Extended hard subdomains |
| math | 100% [72%,100%] | NO | HMMT-only (drop AIME), or problems 20+ of each contest |
| code | 90% [60%,98%] | NO | LCB hard-only already in use; restrict to the newest contest window or platform=codeforces |

Caveat: with n=10 the point estimates are unstable (CI lower bounds reach down
to 60–72%), but since all three point estimates are ≥90% the full run should
move to harder slices or expect little headroom for ensembles to show gains.

---

## 4. Arm results at default effort — PILOT (n=10 per cell)

B per set as in §3; A2 = best-of-5 (B × 5 seeds, majority/programmatic vote);
A3 = 7 personas × B, vote; A4 = cross-family panel (gpt-6.1-sol, grok-4.7,
kimi-k3, each at its default level) with either an LLM aggregator (A4a =
claude-fable-5-1@high, A4b = claude-haiku-5-5@medium) or a plain majority
vote (`a4-vote`). Cost/item for A4a/A4b rows below is the aggregator call
only; the shared panel costs $0.1667 (gpqa) / $0.3269 (math) / $0.3316 (code)
per item on top (from the a4-vote records, which carry the summed panel cost).

Record_ids: `summary.md` rows with matching (arm, set); vote-record parents
link each vote to its proposal records via `parent_record_ids`.

| arm | gpqa | math | code |
|---|---|---|---|
| A1 (= B stage0) | 9/10 (90%) | 10/10 (100%) | 9/10 (90%) |
| A2 best-of-5 | 9/10 (90%) | 10/10 (100%) | 9/10 (90%) |
| A3 persona panel | 9/10 (90%) | 10/10 (100%) | 9/10 (90%) |
| A4 panel, majority vote | 8/10 (80%) | 10/10 (100%) | 9/10 (90%) |
| A4a strong aggregator | 9/10 (90%) | 10/10 (100%) | 9/10 (90%) |
| A4b weak aggregator | 9/10 (90%) | 10/10 (100%) | 9/10 (90%) |

All CIs overlap heavily at n=10 — **no arm separation is measurable in the
pilot, by design**. (CI per cell in `summary.md`.)

### Rule-4 check per aggregator

Panel families: openai, xai, moonshot. Both aggregators are Anthropic, so
rule-4(a) (aggregator family not on panel) **passes** for both — checked as a
hard error at stage1 start (`ensemble_reboot/pilot.py:317-322`).

Rule-4(b) (aggregator single-model accuracy ≥ every panel member, point
estimates from stage0; query: `check_rule4` with stage0 Wilson CIs):

| set | A4a (fable-5-1) | A4b (haiku-5-5) |
|---|---|---|
| gpqa | **FAIL (b)**: fable 8/10 < kimi-k3 9/10 (all CIs overlap, n=10) | weak aggregator; rule-4 strength clause relaxed by design (haiku 6/10) |
| math | PASS: 10/10 ≥ all panel members | weak aggregator; rule-4 strength clause relaxed by design (haiku 8/10) |
| code | PASS: 9/10 ≥ all panel members | weak aggregator; rule-4 strength clause relaxed by design (haiku 8/10) |

**A4b is the "weak aggregator; rule-4 strength clause relaxed by design"
arm** — its aggregator is deliberately below the panel; the rule-4(b)
exemption is intentional and must be carried through all downstream reports.

The A4a gpqa rule-4(b) failure is a point-estimate difference of one item at
n=10 (every pairwise CI overlaps; overlap notes emitted by `check_rule4`).
For the full run, either re-confirm B/aggregator strength on the larger
stage0, or swap the A4a aggregator to the strongest non-panel-family model on
that set (claude-opus-5-5 was the gpqa best single model).

---

## 5. Preliminary co-failure matrix — stage0, n=10 per pair

**n=10 cannot support co-failure claims. 45 pairs × 10 items means the
"matrix" below is directional noise; it is included only to prove the
pipeline computes it.** Full per-pair table (P(both wrong), independent
expectation, ratio, grouping): `summary.md` §"Co-failure matrix"; item ids
per pair in `record_groups.json` (`cofail_*` keys).

Condensed (mean observed/expected ratio across pairs; ratio > 1 = more
correlated failure than independence):

| set | within-lab pairs (9) | cross-lab pairs (36) | note |
|---|---|---|---|
| gpqa | 3.52 | 3.50 | ratios inflated by shared hard items |
| math | 0.00 (8/9 pairs have an all-correct member) | 0.60 (31/36 undefined) | too few failures to measure |
| code | 5.83 | 3.77 | within-lab > cross-lab, consistent with the diversity hypothesis, but n=10 |

Query: `analysis.stats.co_failure_matrix(group_correct_by_model(stage0_records))`
per task set, grouping by `family` field.

---

## 6. Accepted effort levels per model (from the probe)

Source: `results/probe_levels_2026-10-22.jsonl` (70 rows: 10 models × 7
candidate levels; status + verbatim 400 bodies recorded per row).

| model | accepted (200) | rejected (400) and why |
|---|---|---|
| claude-fable-5-1 | low, medium, high, xhigh, max | `none`, `minimal`: "unknown variant …, expected one of low/medium/high/xhigh/max" |
| claude-opus-5-5 | low, medium, high, xhigh, max | same as fable |
| claude-sonnet-5-5 | low, medium, high, xhigh, max | same |
| claude-haiku-5-5 | low, medium, high, xhigh, max | same |
| gpt-6-astra | low, medium, high, xhigh, max | `none`, `minimal`: "Unsupported value" (note: the two error messages disagree about whether `none` is supported — see BUILD_NOTES) |
| gpt-6.1-sol | low, medium, high, xhigh, max | `none`, `minimal`: "Unsupported value" |
| gpt-6-luna | **none**, low, medium, high, xhigh, max | `minimal` only |
| grok-4.7 | low, medium, high, xhigh | **no `max`** ("Supported values are: low, medium, high, and xhigh"); `none`, `minimal` also 400 |
| kimi-k3 | **none**, low, medium, high, xhigh, max | `minimal` only |
| nova-2-lite-v1:0 | low, medium, high | `none`, `minimal`, **`xhigh`, `max`**: "#/reasoningConfig/maxReasoningEffort: X is not a valid enum value" |

These match `manifest.json#accepted_levels`, which is what the runner used.

---

## 7. What this pilot does NOT establish

- No arm ranking (n=10, all CIs overlap).
- No effort-vs-accuracy conclusion (stage2 covered only 3 of 10 models).
- No co-failure conclusion (§5).
- Accuracy numbers here must NOT be projected to the full run; the full-run
  estimate (`COST_ESTIMATE.md`) projects **cost only**, from measured tokens.
