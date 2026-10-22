# ensemble-reboot

Does cross-lab model diversity beat single models, best-of-N, and persona
panels at matched cost? This repo is the experiment harness (Phase 1: build +
offline verification; live Bedrock stages are run later by the root
orchestrator). This phase produced **no result numbers**: nothing here reports
accuracy or cost measurements until live records exist.

## Purpose

Prior April-era work compared persona panels on a single model. The reboot
tests the sharper hypothesis: **error decorrelation across labs** is the
mechanism that makes ensembles pay, so a cross-family panel should beat both
same-model best-of-N (correlated errors) and persona prompting (same weights,
cosmetic diversity) at the same spend. The co-failure matrix
(observed P(both wrong) vs independent P(A)·P(B), within-lab vs cross-lab)
is the direct check of that mechanism.

## Arms

| Arm | What it is | Aggregation |
|-----|-----------|-------------|
| A1  | Single best model B (per task set, picked in stage 0) | — |
| A2  | Best-of-N (N=5) on B, independent samples | programmatic majority vote; code: public-test filter → first passing (tie-break: output-signature majority). No LLM selector in the primary path. |
| A3  | 7-persona panel on B (April personas, prompt diversity only) | same programmatic aggregation; optional LLM-aggregator variant only if it passes rule 4 |
| A4a | Cross-family panel: best OpenAI (gpt-6.1-sol) + grok-4.7 + kimi-k3 | **strong** aggregator: claude-fable-5-1 |
| A4b | Same panel | **weak** aggregator: claude-haiku-5-5 (exempt from rule-4(b) BY DESIGN, labeled `WEAK-BY-DESIGN` in all outputs) |

A post hoc programmatic majority vote is also computed for every panel from
existing records at zero extra calls.

### Aggregator topology and why

The aggregator sees the problem plus all panel responses and must emit a final
answer in the task's required format, which is then graded programmatically —
same grader as every other arm, so the aggregator can't be graded on a
different rubric. **Rule 4**: (a) the aggregator's family must NOT be on the
panel (hard error — otherwise family self-preference contaminates the
diversity claim), and (b) the aggregator's own single-model accuracy must be
≥ every panel member's (point estimates; CI overlap reported). A4b
deliberately violates (b): if a *weak* cross-family aggregator still captures
most of the panel's gain, the value is in the diverse proposals, not the
aggregator's own capability. That contrast is the point of running both.

Panels **reuse** stage-0/A2 records as proposals via `parent_record_ids`;
arm cost = sum of parent call costs + aggregator call cost (programmatic
votes cost $0 extra).

## Roster

Exactly the 10 `global.` inference profiles in REQUIREMENTS.md (4 Anthropic,
3 OpenAI, xAI grok-4.7, Moonshot kimi-k3, Amazon nova-2-lite). The roster
loader hard-fails on any reference to retired April-era models (mantle,
grok-4.3, gpt-5.5, Claude 4.x, Nova 1, …) — see `ensemble_reboot/roster.py`
and `config/roster.yaml`. Per-provider reasoning-effort mapping (including the
Nova-2-Lite rule that `inferenceConfig.maxTokens` must be omitted at `high`)
lives in `ensemble_reboot/client.py`, shapes verified by
`scripts/smoke_roster.py`.

## Task sets

- **GPQA-Diamond** (198 items): official zip (password read from the repo
  README at runtime), per-item seeded choice shuffle, letter grading.
- **Math**: MathArena AIME 2026 + HMMT Feb 2026, filtered to single
  exact-answer items; `\boxed{}` / "Final answer:" extraction with exact
  normalization.
- **Code**: LiveCodeBench `code_generation_lite`, hard difficulty, most
  recent available window (see BUILD_NOTES — the requested post-2026-06
  window does not exist upstream). Public tests are used only for best-of-N
  selection; grading uses private tests in a sandbox (`unshare --net`, drop
  to `nobody`, rlimits, wall timeout).

Dataset text is **never committed** (GPQA asks that examples not be posted
online): `data/` is gitignored, and `ensemble_reboot/data/manifest.json`
records only item ids + sha256.

## How to run

```bash
git clone https://github.com/ccrngd1/ProtoGensis.git
cd ensemble-reboot
pip install -e .
python3 -m pytest -q                      # offline tests, no network/token needed

# live stages (need AWS_BEARER_TOKEN_BEDROCK; run by the root orchestrator):
python3 scripts/probe_levels.py           # which effort levels each model accepts
python3 scripts/headroom_check.py <run>   # best single model must be <80%/set
python3 scripts/run_pilot.py --cap 75     # stage 0 -> 1 -> 2, resumable
python3 scripts/run_pilot.py --dry-run    # plan + ASSUMED-labeled cost estimate
python3 scripts/summarize.py <run_id>     # summary.md/.json, co-failure, curves
python3 scripts/estimate_full_run.py <run_id>  # full-run cost projection
```

The pilot: stage 0 runs all 10 models at default effort on 10 fixed seeded
items per set (picks best model B per set); stage 1 runs A2/A3/A4a/A4b on B
reusing stage-0 records; stage 2 sweeps effort levels (frontier models first,
skipping levels stage 0 already covered). `BudgetGuard` enforces the spend cap
before each dispatch (counting in-flight calls, UNKNOWN prices billed at the
highest known rate) and aborts cleanly; re-running resumes by skipping
already-recorded calls.

## Record schema

One JSONL line per API call or grading event in
`results/<run_id>/records.jsonl` (append-only): `record_id, run_id, stage,
arm, task_set, item_id, item_sha256, seed, model_id, family, effort,
request_params` (sans token), `stop_reason, usage, input_tokens,
output_tokens, cache_read_tokens, cost_usd` (null + `price_status=UNKNOWN`
when pricing is unknown — never $0), `latency_s, extracted_answer, correct,
grader_details, parent_record_ids, response_sha256, truncated, timestamp,
git_commit, is_mock`. Full response text goes to gitignored
`results/raw_text/<record_id>.txt`. Reporting code **refuses** any record
with `is_mock=true`. Truncated responses (`stopReason=max_tokens`) are graded
wrong and counted separately.

## Known limitations

- LiveCodeBench has no post-2026-06 problems; we use the most recent window
  (recorded in the manifest). Newer-model contamination risk is therefore
  higher for the code set than for the 2026 math sets.
- Rule-4(b) uses pilot point estimates on n=10 items/set; CI overlap is
  reported but not enforced.
- Best-of-N/persona ties break deterministically (earliest proposal), which
  slightly favors lower seed indices.
- Code grading caps at 25 tests/item (flagged in grader details).
- Pricing was collected 2026-10-22 from the AWS Price List API and AWS docs
  model cards (two models were too new for the API — see BUILD_NOTES);
  prices change, re-verify before the full run.
- The sandbox needs root for network isolation (`unshare --net` + drop to
  `nobody`); non-root runs still get rlimits + timeout but no netns, and two
  tests skip.
