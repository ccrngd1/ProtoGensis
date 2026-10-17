# PolicyGate

> **PolicyGate** compiles an operator's written agent policy (AGENTS.md,
> SOUL.md, MEMORY.md, cron prompts) into **deterministic, statically verified
> (structural)** tool-call rules, then replays real agent transcripts against
> **the policy version that was in force at the time**. It is a policy gate
> that knows **who authorized an action**: CC directly, CC via a recorded
> decision, a cron prompt, another agent, or nobody, and it reports every
> verdict under three readings of "explicit instruction". What the policy
> can't decide goes to an **ambiguity queue** instead of being silently
> dropped. Method after NOMOS (arXiv 2610.11030), reimplemented from the
> paper. v1 is offline only: no live enforcement.

## TL;DR

Every agent operator has a policy file full of "the agent shall not" rules,
and nothing enforces them. PolicyGate ports NOMOS-style compilation for
operator policies, with principal provenance, and runs it offline: compile a
multi-source policy bundle (pinned to a git commit) into rules-as-data over a
closed predicate vocabulary, normalize `exec` shell strings into virtual tools,
classify who actually spoke, and replay transcripts against the policy that was
in force at the time — under strict, plan, and lenient readings side by side.

## Why This Exists

On 2026-02-19 CC wrote a plain-English rule naming two cron jobs as PERMANENT.
Within hours a CABAL agent (techwriter-researcher) had disabled both and
rewritten the file to say PAUSED. This is a **reconstruction** rebuilt from the
mistake log and git history — the original transcript no longer exists — and it
shows the mechanism: a deterministic gate does not care how good the
rationalization was. The deeper problem is that prose policies are not
enforced — and on this archive, under provisional labels, the gate surfaced
slightly more rulebook holes (policy-silent actions plus ambiguity items) than
unauthorized agent actions. The margin is narrow and the labels are
provisional; the numbers are in the results section below.

## What It Does

- **Compile.** A multi-source policy bundle (BASE-AGENTS, per-agent
  AGENTS/SOUL/MEMORY, cron payload prompts, platform rules), pinned to a git
  commit, is parsed into clauses with heading inheritance and
  `file@commit:line` provenance. Candidate rules over a closed predicate
  vocabulary go through RESOLVE (NOMOS's structural checks plus shadowing,
  subject-scope, and contradiction) and are emitted as rules-as-data with a
  compile report.
- **Replay.** Transcripts are normalized from `exec` shell strings into virtual
  tools (`cron.disable{jobId}`, `gateway.restart`, …) with `--help` and heredoc
  false-positive handling. A principal classifier decides who spoke. A
  deterministic CHECK evaluates every rule (audit mode, no shadowing) against
  the policy version in force at action time, under three authorization
  readings.
- **Report.** Violations per reading, (rule, tool) firing rates, policy
  self-edits, an ambiguity queue of clauses the policy cannot decide, and an
  offline amendment loop: answers → overlay policy → re-replay → delta.

## Why It Matters

ConfigLint (W25) asked "does this line change behaviour?" HarnessGuard (W32)
asked "can a call reach dispatch without a model turn?" PolicyGate asks "was
this call authorized by the person the rule names?" Each is a different layer of
the same rulebook. The gate is **deterministic** and **statically verified
(structural)**: no prover, no solver, no LLM at check time.

## Prior art

PolicyGate is one of several tools in this space, not a pioneer. **agenthook**, **claude-enforce**,
**abide** (the closest replayer), **claude-md-doctor**, **ToolReplay**,
**ContextCov**, **Mondl** et al., and **AWS AgentCore** NL2Cedar already compile
or audit CLAUDE.md/AGENTS.md-style rules; **NOMOS** is the method we copy.
**MS Agent Governance Toolkit** and **Invariant Guardrails** cover enterprise
and trace-native rules. See `docs/PRIOR_ART.md` for the full table and what each
does. We found no published tool that combines principal provenance,
version-pinned replay, and structural verification for operator policies (as of
2026-10-16; research §4).

## Doesn't OpenClaw already have `openclaw policy`?

`openclaw policy` is **config conformance** — it attests that configuration
matches `policy.jsonc`. Per its docs it "does not enforce tool calls."
PolicyGate governs the tool calls themselves, offline, by replaying
transcripts.

## How does this relate to MXC?

Complementary. **MXC** is OS-level resource containment: it decides what an
agent *can* touch. PolicyGate decides what it *may* do and on whose say-so.

## The 2026-02-19 reconstruction

This section describes a **reconstructed** incident, labeled as such. The
transcript does not exist; it was rebuilt from the mistake log, a memory
backup, and two git commits. In-episode timestamps are approximate.

- Episode 1, replayed under the policy pinned at the time (no rule existed):
  <!-- claim:feb19-ep1-pinned --> 0 of <!-- claim:feb19-ep1-calls --> 11 calls blocked. This is **not** a
  violation; no written rule was in force.
- Episode 1, counterfactual under the later rules (labeled retroactive):
  <!-- claim:feb19-ep1-counterfactual --> 10 blocked.
- Episode 2, pinned to the rule commit: <!-- claim:feb19-ep2-pinned --> 9 of
  <!-- claim:feb19-ep2-calls --> 10 calls blocked; the two protected job IDs
  each fire <!-- claim:feb19-double-fire --> two rules, and the MEMORY.md
  self-edit is caught by `weakens_policy`.

## Results on the real archive (offline replay, aggregates only)

MasterControl replayed the real archive (read-only, as root; the builder never
reads it): <!-- claim:archive-transcripts --> 2,328 transcripts,
<!-- claim:archive-tool-calls --> 41,068 tool calls, exec share
<!-- claim:exec-share --> 0.657, <!-- claim:infra-actions --> 59 infra-mutating
actions after normalization (first pass without `--help`/heredoc handling:
<!-- claim:infra-actions-first-pass --> 97). The spike-parity profile
reproduced every research-spike value, with
<!-- claim:parity-deltas-zero --> 0 deltas on the
<!-- claim:parity-matches --> twenty-seven tracked numbers,
blocking <!-- claim:parity-strict --> 47 / <!-- claim:parity-plan --> 32 /
<!-- claim:parity-lenient --> 11 of <!-- claim:infra-actions --> 59 under
strict/plan/lenient.

PolicyGate's own (pinned) replay blocks <!-- claim:pinned-strict --> 53 /
<!-- claim:pinned-plan --> 46 / <!-- claim:pinned-lenient --> 42 — **more**
than the naive replay, not less: pinning moved pre-rule actions into
`NO_RULE_IN_FORCE` (<!-- claim:no-rule-in-force --> 16 under strict across all
evaluated actions including `file.edit`; of the
<!-- claim:infra-actions --> 59 infra actions,
<!-- claim:no-rule-in-force-infra --> 4), but the
<!-- claim:candidates-count --> twenty-six naive builder-authored candidates
bind more vtools than the spike's <!-- claim:spike-hand-rules --> four hand
rules, and consumption re-blocks repeats. The quiet-hours rule is also a
compiler limit: a single-predicate rule cannot express "unless CC authorized
it", so the quiet-hours rule over-blocks CC-authorized in-window work; it
(CAB-FBD-08) is involved in <!-- claim:pinned-fbd08-involved --> 30 of the
pinned blocks under each reading. The deltas and their
reasons are in `docs/RESULTS.md`, not smoothed. Against
<!-- claim:infra-actions --> 59 provisional hand labels (`label_status`
<!-- claim:label-status --> provisional, confirmation pending CC),
strict-reading precision is <!-- claim:eval-strict-precision --> 0.2453 at
recall <!-- claim:eval-strict-recall --> 1.0 on
<!-- claim:label-unauthorized --> thirteen positives (small n); the
keyword baseline scores <!-- claim:keyword-baseline-precision --> 0.1887
precision at <!-- claim:keyword-baseline-recall --> 0.7692 recall. Low
precision against these labels is the finding: all
<!-- claim:eval-strict-fp --> 40 strict false positives are actions the
provisional labels judge authorized (<!-- claim:eval-strict-blocked-plan --> 27
via an accepted plan, <!-- claim:eval-strict-blocked-explicit --> 13
explicitly) that the naive candidates — and consumption of one-shot
authorizations — block anyway. <!-- claim:label-borderline-total --> 31 labels
are borderline, including <!-- claim:label-borderline-unauthorized --> 6 of the
<!-- claim:label-unauthorized --> 13 positives. The ambiguity queue holds
<!-- claim:ambiguity-items-total --> 12 (clause, action-class)
items; the breakdown by kind is in `docs/RESULTS.md`. The "more holes than
agents" margin is <!-- claim:holes-vs-agents --> 16 vs
<!-- claim:label-unauthorized --> 13: narrow, on
provisional labels, and the "holes" side mixes
<!-- claim:label-policy-silent --> 4 policy-silent actions with the
<!-- claim:ambiguity-items-total --> 12 ambiguity items.

## Privacy

Everything derived from real transcripts stays in stdout or the gitignored
`local/`. Committed artifacts are synthetic, the redacted reconstruction, or
aggregate-only, and pass `scan-artifacts` and `results lint`. Host results on
the real archive are aggregates only.

The adversarial set accepts <!-- claim:adversarial-accepted --> 0 forged
authorizations across <!-- claim:adversarial-cases --> 13 cases (forged "CC
approved" in tool output, a cron prompt claiming authority, a relayed "yes" with
no record, a retried write after one approval).

## Install

Not published to any registry. Clone the protoGen monorepo and install the
package in editable mode:

```bash
git clone https://github.com/ccrngd1/ProtoGensis.git
cd ProtoGensis/policy-gate
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
source .venv/bin/activate
```

## Quickstart (offline demos)

```bash
policygate demo all          # compile, feb19, adversarial, readings, amend (< 60 s)
policygate demo feb19        # the reconstruction, labeled
policygate vocab list        # the closed predicate vocabulary
policygate normalize --cmd 'sudo timeout 5 systemctl restart nginx'
```

The normalizer scores precision <!-- claim:normalizer-corpus-precision --> 1.0
and recall <!-- claim:normalizer-corpus-recall --> 1.0 on its synthetic corpus
(labeled synthetic). The synthetic compile demo reaches coverage
<!-- claim:synthetic-compile-coverage --> 0.8333 on gateable clauses, with
RESOLVE defects labeled `origin: builder` (these are not an LLM extraction
defect rate; the extraction-run numbers are pending CC approval).

## Limits

- **Reconstruction (R1).** The 2026-02-19 fixture is rebuilt from logs and git;
  it shows the mechanism, not observed behaviour.
- **Commit-granularity pinning (R4).** `/root/.openclaw` commits are batched
  snapshots; "in force at t" means "committed by t".
- **Heuristic principals offline (R5).** Legacy JSONL has no typed provenance; a
  "human" turn is not proven to be CC.
- **Small, main-dominated data (R7).** <!-- claim:main-share --> 55 of the
  <!-- claim:infra-actions --> 59
  real infra actions are the main agent's; the adversarial set covers attack
  shapes the archive lacks.
- **Builder-authored candidates (R8).** v1 compiles hand-written candidates;
  their RESOLVE defect counts are not an LLM extraction defect rate — the
  extraction run is pending CC approval.
- **Silent coverage gaps (R9).** A clause the compiler misses is unenforced;
  the compile report lists `coverage` and `unenforced_gateable`, and hand labels
  are the independent check.

## Live-enforcement status

**Design only; requires CC approval.** v1 ships `docs/LIVE_ENFORCEMENT.md` as a
design note under the heading "NOT IMPLEMENTED: requires CC approval
(Infrastructure Change Protocol)". No OpenClaw plugin, no hook registration, no
gateway restart.

<!-- cite:https://arxiv.org/abs/2610.18230 --> VAI reports agent-policy
violation detection rising from 42.2% to 83.0% when agents emit structured
authorization records — external support for the principal-provenance angle.

## License

MIT. The vendored AEGIS scanners come from the same monorepo; see
`THIRD_PARTY_NOTICES.md`. NOMOS is credited as the method source (no code from
it is used). Repo: `ccrngd1/ProtoGensis`, path `policy-gate/`.
