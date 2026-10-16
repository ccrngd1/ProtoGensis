# Predicate vocabulary (closed set)

Run `policygate vocab list` for the machine-readable form. Each predicate has a
`kind`, `reads` (argument keys it inspects), `enable` (virtual tools or fact
kinds that clear it), and a deterministic evaluator.

**Type is derived, never chosen.** Candidates express only polarity
(`block_when_true` / `block_until_true`); `derive_type()` maps them to
FORBIDDEN / PRECONDITION (NOMOS §3.1). A candidate carrying an explicit `type`
field is rejected (`REJECT type-not-derivable`).

**Fail-safety asymmetry.** A missing fact makes a PRECONDITION block and a
FORBIDDEN pass; every such evaluation is logged as `fact_missing`.

## MVP predicates

| Predicate | Kind | Reads | Enable |
|---|---|---|---|
| `cc_authorized(action_class)` | principal | — | a CC turn naming the class |
| `principal_is(p)` | principal | — | — |
| `agent_in(list)` | subject | — | — |
| `quiet_hours_utc(start, end)` | temporal | ts | time |
| `target_protected(key)` | arg | jobId / unit / path | — |
| `path_in(globs)` | arg | path | — |
| `weakens_policy` | arg | path, removed_text | CC authorization |
| `checkpoint_seen(target)` | ordering | target | `backup.*` vtools |
| `host_in(list)` | arg | url | — |
| `confirmation_fresh` | principal | — | consumed on use |
| `secret_in_args` | arg | * | — (vendored SecretScanner) |

## Should-ship predicates

| Predicate | Kind | Notes |
|---|---|---|
| `attempts_lt(target, 3)` | counting | 3-strike rule; a CC turn resets it |
| `channel_shared` | read-gate | write-scope repair must not touch it |
| `obligation:*` | liveness | end-of-trace, a report section not a gate |
