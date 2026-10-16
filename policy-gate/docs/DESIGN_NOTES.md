# Design notes

## Ambiguities (resolved during the build, per the build-prompt instruction)

- **SecretScanner over-matching (AC #21).** The vendored AEGIS `SecretScanner`
  flags every UUID (its `heroku_api` pattern) and emits `secret_keyword` /
  `high_entropy_string` findings on ordinary prose and source code. Scanning
  committed artifacts with those enabled would flag the synthetic job IDs and
  the scanner's own source. Reading most faithful to the requirements: judge
  UUIDs with the explicit synthetic-form rule the spec defines
  (`^[0-9a-f]{8}-0000-4000-8000-[0-9a-f]{12}$`) and use the SecretScanner only
  for its high-confidence credential **formats** (AWS keys, JWTs, private keys,
  etc.), excluding `heroku_api`, `secret_keyword`, and `high_entropy_string`.
  The explicit extra patterns (Slack IDs, non-synthetic UUIDs, RFC1918, `xox`,
  `AKIA`, token assignments) remain in force, and secret-class hits still
  cannot be allowlisted. Test fixtures assemble any detector-triggering literal
  from fragments at runtime so nothing real is committed (R10).

- **`token_assign` value shape.** The spec pattern
  `(token|key|secret|password|bearer)[=: ]+\S{8,}` self-matches source lines
  that merely *name* those keywords (e.g. a regex literal). Narrowed the value
  to credential characters (`[A-Za-z0-9+/_.\-]{8,}`) and required the separator
  to be adjacent (`[=:]`), so a genuine assignment is still caught while prose
  like "the token is rotated" is not.

- **spike-parity blocked semantics.** Spike 1 computes "blocked under reading r"
  as "infra action not cc_authorized under r" (INF-PRE-01/02 are the only
  authorization rules and they guard all infra vtools). PolicyGate's
  `spike-parity` profile reproduces exactly that: blocked[r] = infra actions
  where `authorized(r)` is false. This is what reproduces 47/32/11.

- **PLAT-FBD-04 modeled as a flag, not a block, in parity.** The spike reports
  PLAT-FBD-04 as "would flag N gateway restarts, of which M were CC-requested",
  not as additional blocks. The aggregates carry `plat_fbd_04 {flagged,
  cc_requested_strict}` for the parity comparison; pinned replay gives it
  `effective_from = "unknown"` → `VERSION_UNKNOWN` (never a violation).

- **Pinned verdict precedence (AC #14, phase 3).** When several rules bind one
  action, per reading: any in-force rule firing → `BLOCK`; else any firing rule
  from a later version → `NO_RULE_IN_FORCE`; else any firing rule with
  `effective_from = "unknown"` (or a missing timestamp, R14) →
  `VERSION_UNKNOWN`; else `ALLOW`. A rule that fired only in earlier versions
  (since removed) leaves the action `ALLOW` and is listed under
  `retroactive_rules` with class `ALLOW` (the removal is listed, never a
  violation). Boundaries are commit times from gitread `log` (one call per
  bundle source); bundle text is read once per (sha, path) and snapshots are
  memoized by the per-source commit tuple, so a few dozen commits never cost
  one `git show` per action.

- **Built-in rules under pinning.** A candidate with `clause_ref {"builtin"}`
  has no bundle clause to hash-match; it is in force from the time its
  `src.file` exists in the bundle (or from the first bundle commit when it
  names no file). Platform rules keep `effective_from` (dated or "unknown"),
  inherited by rule id from `config/platform_rules.toml` via the bundle.

- **Clause-hash prefix matching.** `clause_ref.clause_sha256` /
  `section_hash` match by prefix (so 8/16-hex pins work), consistent with
  `candidates check`. "Present in the bundle at t" means some clause or
  section hash of a parsed source starts with the ref's hash; `file` narrows
  the search when given.

- **Non-gateable classes never gate (AC #17e, phase 3).** Candidate classes
  route as: `gateable | temporal | ordering | counting` → gate (their
  predicates are runtime predicates: `quiet_hours_utc`, `checkpoint_seen`,
  `attempts_lt`); `obligation` → end-of-trace obligations report section
  (counts per rule in `aggregates.obligations`); `ambiguous` → one
  `unclassified_clause` ambiguity item; `text-only` → not evaluated.
  `compile` and `candidates check` print this routing per class
  (`class_routing`). This fixes the host finding where an obligation-class
  cc_authorized candidate BLOCKed ~4.2k file.edit actions.

- **action_key occurrence index (AC #19, phase 3).** The key hashes
  `agent|ts|vtool|<full segment text>`; when one (agent, ts, vtool, segment)
  tuple recurs (two identical commands in one call), a deterministic
  occurrence index (stream order) is appended as `|<n>` for the second and
  later ones. Keys stay profile-independent. `scripts/rekey_labels.py` maps an
  old-key labels file onto new keys given two run dirs of the same archive
  (match on agent/ts/vtool and order; duplicated old keys fan out to all their
  new keys with the same label).

- **Ambiguity queue is per (clause, action-class) (AC #17, phase 4).** The
  phase-3 generators emitted one item per *action* (the pinned run had 1,181
  items, 1,139 of them `deferred_authorization`, with `clause_ref` pointing at
  the action, not a clause). Phase 4 collapses every generator onto the key
  `(kind, clause_ref, action_class)` where `action_class` is the vtool family
  (`cron.*` for infra-mutating vtools, the vtool itself otherwise) and
  `clause_ref` is the policy clause `file@commit:line` (rule id for builtins) —
  resolved from the gating rule that binds the action's vtool. Per-reading
  `affected` counts are summed; item ids are deterministic
  (`AMB-<KIND4>-<sha256(kind|clause|class)[:8]>`); per-action evidence stays as
  `action_keys` lists in local/tmp run dirs only (eval's ambiguity-coverage
  joins on them). `deferred_authorization` is restricted to research §3.2:
  principal `cron` AND the triggering prompt references a queued/validated item
  AND no provenance (approver/Temple item) is recorded — not every
  cron-triggered action; and no item is emitted when no authorization clause
  binds the vtool (there is no clause to ask about). Items whose kind derives
  from a reading swing count one affected action per reading they swing.

- **PENDING_RERUN claim rows (AC #22, phase 4).** Rows whose value depends on
  a stage-b re-run carry `PENDING_RERUN`, treated by `claims verify` exactly
  like `PENDING_HOST` (SKIP off-host, FAIL on-host). First used for the
  phase-4 ambiguity-queue collapse (filled); used again in phase 5 for the
  infra-only verdict-class split (`verdict_classes_infra`), because the
  all-actions `verdict_classes` sums infra and `file.edit` verdicts and the
  prose needs the infra-only NO_RULE_IN_FORCE count exactly.
  `scripts/fill_rerun_claims.py` (generic) re-runs each such row's command and
  writes the printed value into the ledger and into README/BLOG/RESULTS lines
  carrying the same claim marker; it also prints which BLOG title the
  `holes-vs-agents` rule selects, without editing the title itself.

## Open questions carried from requirements

Q1 (97 first-pass count not in spike output — ablation flags make it the tool's
number), Q2 (spike's own rules were retroactive), Q5 (platform rule effective
date unknown → VERSION_UNKNOWN), Q6 (preflight threshold min_support=5, our
choice), Q7 (`cron.add` not infra-mutating in v1). See
`.mastercontrol/requirements.md` Open Questions for the full list.
