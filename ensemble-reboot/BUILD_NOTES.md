# BUILD_NOTES — Phase 1 (harness build, offline)

Built 2026-10-22. No live Bedrock calls were made in this phase (the bearer
token is not available in this environment); request shapes come from the
pre-existing smoke test `results/smoke_2026-10-22.json`. **No result numbers
exist or are claimed anywhere in this repo yet.**

## Done-when checklist

- `python3 -m pytest -q` — tail pasted below.
- Datasets download and load — item counts below.
- `config/pricing.yaml` — all 10 profiles priced with per-entry source URLs
  and retrieval date (no UNKNOWNs needed in the end).
- `python3 scripts/run_pilot.py --dry-run` prints the planned call table and
  an ASSUMED-labeled cost estimate (verified; see "Dry run" below).

## pytest tail

```
........................................................................ [ 51%]
........................................................ss...........    [100%]
139 passed, 2 skipped in 9.38s
```

The 2 skips are the sandbox tests that need root (`unshare --net` network
isolation and the drop-to-`nobody` check); this build shell runs as uid 1000.
The root orchestrator environment runs them for real. Non-root sandbox runs
still enforce rlimits (CPU/AS/NPROC/FSIZE) + wall timeout and log the missing
netns once.

## Dataset item counts (loaded from local data/, text not committed)

| set  | items | notes |
|------|------:|-------|
| gpqa | 198 | GPQA-Diamond, official zip; password read from repo README at runtime |
| math | 51  | AIME 2026 (30) + HMMT Feb 2026 (33) → 51 after the single-exact-answer filter (12 multi-part/non-rational answers dropped) |
| code | 61  | LiveCodeBench code_generation_lite, hard, window 2025-02-01 → 2025-04-06 (see surprises) |

Manifest (ids + sha256 only): `ensemble_reboot/data/manifest.json`.

## Dry run

`python3 scripts/run_pilot.py --dry-run --cap 75`: 1860 planned calls
(stage 0: 300, stage 1: 390, stage 2: 1170), pre-run estimate labeled
"ASSUMED tokens, not measured" with an explicit input/output token-range
assumption printed. These are planning bounds, not results.

## Ambiguities → decisions

1. **LCB window**: the spec asks for post-2026-06-01 problems, but the newest
   official `code_generation_lite` release (release_v6 / test6.jsonl) ends
   2025-04-06 and the org's datasets were last updated 2025-06-05 — no such
   window exists. Decision (per spec's "or the most recent window available;
   record the window"): hard-difficulty items from 2025-02-01 → 2025-04-06
   (61 items); both requested and actual windows are recorded in the manifest
   and `ensemble_reboot/data/lcb.py`. Flagged in README as a contamination
   caveat.
2. **Math "single exact answer"**: implemented as "reference normalizes to an
   integer or exact fraction" (`is_single_exact_answer`); drops 12 items
   (multi-part answers, radicals). Extraction: last `\boxed{}` (balanced
   braces), else last "Final answer:" line; equality on normalized exact form.
3. **A2 seed reuse**: A2's N=5 uses the stage-0 record as seed 0 plus 4 fresh
   seeds, so stage-1 only pays for 4 extra calls per item. Same reuse for A4
   panel proposals (zero extra proposal calls; chained via parent_record_ids).
4. **A3 seeds**: one call per persona; `seed` = persona index 0–6 so the
   resume key stays unique without a separate persona field.
5. **Vote events**: post hoc programmatic votes are recorded as records with
   `model_id="programmatic-vote"`, zero tokens/cost, parents = the proposal
   records; analysis excludes them from token/cost models.
6. **Rule-4(b)** uses stage-0 point accuracies; CI overlaps (Wilson) are
   reported in the Rule4Result, not enforced. A4b is exempt from (b) and its
   label string ("WEAK-BY-DESIGN (exempt from rule-4(b) …)") is attached to
   every output mentioning it (test-enforced).
7. **Conservative budget accounting**: UNKNOWN-priced calls are billed at the
   highest known roster rate and flagged; the guard reserves $0.25/call for
   in-flight dispatches so concurrency can't blow the cap.
8. **Grok effort ladder**: smoke test confirms grok-4.7 rejects `max`;
   roster lists low…xhigh only, and a test pins that.
9. **Nova 2 Lite at high**: `inferenceConfig.maxTokens` omitted entirely
   (smoke-verified 400 otherwise); mapping test-enforced. Consequence: Nova
   high-effort calls have no output cap, so truncation accounting there relies
   on stopReason only.
10. **Truncated responses** (`stopReason=max_tokens`) are graded wrong and
    surfaced as a separate `truncated` count in summaries.
11. **Code grading cost cap**: at most 25 private tests per item are executed
    (flagged in grader details); public-test output signatures always run all
    public tests so best-of-N tie-breaks are stable.

## New dependencies

None installed in this phase. `pyproject.toml` lists `requests`, `numpy`,
`huggingface_hub` (all pre-installed per spec) plus **PyYAML** and, for
dataset parquet loading, **pyarrow** — both were already present in this
environment (PyYAML 6.x, pyarrow via system packages); nothing was installed
from a registry. matplotlib is optional (summaries fall back to CSV).

## API / data surprises

- **GPT-6.1 Sol and GPT-6 Luna are missing from the AWS Price List API**
  (Sol released 2026-10-15, too new; only a gov-cloud gpt-5.6-luna entry
  exists). Prices taken from the AWS docs model cards instead (URLs in
  pricing.yaml). Everything else came from the Price List API offers
  `AmazonBedrock` / `AmazonBedrockFoundationModels`.
- The two Price List offers use **different units** ($/1K vs $/1M) and
  different usagetype grammars; normalized to $/1M in pricing.yaml.
- **Global CRIS is ~10% cheaper** than in-region/US-CRIS for the models where
  both SKUs exist; all roster profiles are `global.` so global rates are used.
- The pricing-2.0 `bedrock.json` blob is gzip with opaque hashed region keys
  and an empty `sets` map — abandoned in favor of the offers API + docs.
- **Nova 2 Lite has no global cache-read SKU** in the Price List; cache_read
  uses the published 75%-off-input figure from the docs card.
- **LCB private tests** are stored either as plain JSON or
  base64→zlib→pickle→JSON depending on the item; loader handles both.
- Smoke test (pre-existing): all 10 profiles return 200 with the mapped
  effort fields; Nova rejects maxTokens at high with a 400 whose message is
  recorded in `results/smoke_2026-10-22.json`.

## Security notes

- Bearer token only ever read from `AWS_BEARER_TOKEN_BEDROCK` inside
  `BedrockClient`; never logged; `RecordStore.append` refuses any record blob
  containing `Authorization`/`Bearer ` (test-enforced).
- Untrusted LLM code runs with fresh tempdir, empty env, rlimits, wall
  timeout; as root additionally `unshare --net` + setuid/setgid `nobody`.
- `data/` and `results/raw_text/` are gitignored; no dataset text is staged.
