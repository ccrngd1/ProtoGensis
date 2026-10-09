# Design notes

## Ambiguities (resolved readings)

1. **AC #5 "cache hit %" denominator.** Defined as
   `cacheRead / (cacheRead + cacheWrite + uncached input)` exactly as the AC
   states; output tokens are excluded.
2. **"Every probe is cross-session, in a fresh context" vs compliance probes.**
   Mock compliance probes carry a style-tag canary as gold so the deterministic
   path (exact match) scores them; the offline rule checker
   (`scorer.COMPLIANCE_RULES`) exists and is unit-tested, and live compliance
   probes will use it (plus the judge, AC #8). This keeps mock scoring fully
   deterministic.
3. **Oracle context (AC #1/AC #7).** `bootstrap(session)` on A* receives the
   probe list; the runner rebuilds the oracle prefix per probe so each probe is
   scored against exactly its own current gold facts (superseded and implicitly
   invalidated values excluded). Without this, a session carrying several probes
   would mix their gold facts in one context and the "ceiling" would measure
   ContextReader disambiguation, not task validity.
4. **A1 store size at the 5K target (AC #3).** The seed workspace plus fact
   lines is ~0.5K tokens, so the band is reached with distractor sessions as
   specified; at 5K the ladder lands at ~5.4K (within ±15%). Measured values are
   in status.md.
5. **Mock-mode `memdoc run` default out dir.** The spec says mock runs write to
   "a tmp/--out dir (never results/)". Default is `/tmp/memdoc-mockrun` when
   `--out` is omitted; writing under `results/` is a usage error (exit 2).
6. **`demo stale` offline ranking.** The hashing embedder also happens to rank
   the superseded decision first on the committed store. Reported as-is
   (R1: surprises are reported, not tuned); the output is still labeled
   "hashing embedder, not Titan" and makes no semantic claim.
7. **`prereg verify --history` and `results/.gitkeep`.** Commits that touch only
   `results/.gitkeep` are not "results commits"; the placeholder commit would
   otherwise make the order check unsatisfiable.
8. **Cause rule order (AC #9).** The six causes are assigned by a fixed
   first-match rule (see `PREREGISTRATION.md`), hashed with the taxonomy. The
   rule was added to the hashed content before any demo or run was executed
   (see `.mastercontrol/preregistration.md` for the timeline).

## Validator relaxations

**None.** Both known-tight rules are satisfied as written:

- (d) unknown-unknown probes: stopword-filtered keyword overlap is exactly 0
  for every category-2/6 unknown-unknown probe (max measured overlap: 0; the
  generator asserts it and `tasks validate` enforces it).
- AC #3: A1's measured store lands within ±15% of every target (measured values
  in status.md) via the incremental distractor ladder.

## Mechanism notes (from the first demo run, reported as-is)

- The ContextReader resolves most ties by keyword overlap; stale-vs-current
  disambiguation on doc arms relies on the supersession markers the writer
  leaves ("Correction:", "now binds", ...). Implicit-conflict storylines
  (category 4) have no such marker by design, so arms that deliver both values
  depend on the later-date rule — the research §4.1 mechanism made explicit.
- A4's retrieval misses concentrate on unknown-unknown probes (no keyword in
  the prompt → the query embeds nothing useful), and on enumeration facts at
  the 100K size — consistent with the Gerald Chen anecdote the task design
  encodes.
- A0's cause code is `write_miss` by the preregistered rule (the fact was never
  stored, there being no store). This reads oddly but is the rule's first
  matching clause; noted here rather than special-cased.

## Should-ship arms

Both built: A3 `rag_naive` (= A4 with `extract=False`, no search tool, labeled
weak baseline) and A5-bg (`core_writer=background`, the H7 ablation). They are
not in the default demo arm list (which follows the committed
`config/demo_crossover.toml`), but are available via `--arms` and covered by the
conformance suite.
