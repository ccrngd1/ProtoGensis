# I compiled my AGENTS.md into a deterministic gate. It found more holes in my rulebook than in my agents.
<!-- claim:holes-vs-agents -->

*Replaying my agents' archived transcripts against the policy version in force
at the time, and why "who authorized this?" is the question that matters.*

> **What this is.** PolicyGate compiles my written agent policy (AGENTS.md,
> SOUL.md, MEMORY.md, cron prompts) into deterministic, statically verified
> tool-call rules and replays real transcripts against the policy that was in
> force when each call happened. Method after NOMOS (arXiv 2610.11030),
> reimplemented from the paper. Offline only.
>
> **The problem it solves.** Prose policies are not enforced. Most existing
> tools (agenthook, abide, claude-md-doctor, ContextCov) target coding-hygiene
> rules; enterprise kits (AgentCore, Microsoft's Agent Governance Toolkit)
> cover identity-based policies. I found no published tool that combines
> principal provenance, version-pinned replay, and structural verification for
> an operator's own policy (as of 2026-10-16).
>
> **The key insight.** <!-- claim:eval-strict-fp --> 40 of
> <!-- claim:pinned-strict --> 53 strict blocks hit actions provisionally
> labelled authorized: partly my rulebook's wording, partly compiled rules
> blunter than the prose. Separately, policy-silent actions plus open policy
> questions (<!-- claim:holes-vs-agents --> 16) slightly outnumber
> unauthorized actions (<!-- claim:label-unauthorized --> 13). Narrow, and
> provisional.

## 1. Cold open (reconstruction)

This is a **reconstruction**, labeled as such: the 2026-02-19
techwriter-researcher transcript does not exist, so the incident below is
rebuilt from the mistake log, a memory backup, and two git commits. I committed
a rule at <!-- claim:feb19-commit-times --> 16:38 UTC on 19 February (commit
f84fecd8) naming two cron jobs as PERMANENT. The next commit to touch it landed
at <!-- claim:feb19-commit-times --> 01:01 UTC on 20 February (943e5e1d),
eight hours and twenty-three minutes later: by then the history shows both jobs disabled and the "DO NOT TOUCH"
block rewritten to "PAUSED". No invented dialogue. Just the git diff shape and
the commit times.

Replayed against the policy pinned at the time, episode 2 blocks
<!-- claim:feb19-ep2-pinned --> 9 of <!-- claim:feb19-ep2-calls --> 10 calls,
and the two protected IDs each fire <!-- claim:feb19-double-fire --> two rules.
The MEMORY.md self-edit is caught by a built-in `weakens_policy` rule. Episode
1, before the rule existed, blocks <!-- claim:feb19-ep1-pinned --> 0 of
<!-- claim:feb19-ep1-calls --> 11: no rule was in force, so it is not a
violation.

## 2. The problem

Prose policies are not enforced. NOMOS (arXiv 2610.11030) shows how to compile
a written policy into deterministic tool-call gates and that LLM-extracted rules
are often broken until a structural verifier repairs them.
NOMOS repairs or rejects many raw candidates (36.7% airline, 13.2% retail; only 10 of 79 and 5 of 53 survive). <!-- cite:https://arxiv.org/abs/2610.11030 -->
NOMOS assumes typed tools, a single user, and a static policy. CABAL, my
multi-agent OpenClaw setup, has none of those.

## 3. Prior art

PolicyGate is one tool among several, not a pioneer. NOMOS is the method I
copy. The full comparison is in `docs/PRIOR_ART.md`.

| Tool | What it does | Gap for my case |
|---|---|---|
| agenthook | CLAUDE.md/AGENTS.md rules as Claude Code hooks | coding hygiene; no principal provenance, no replay |
| claude-enforce (archived) | generates hooks from CLAUDE.md | coding; no replay |
| abide | replays Claude Code JSONL against CLAUDE.md/AGENTS.md (closest replayer) | coding rules; no principal provenance or version pinning |
| claude-md-doctor | dead refs, drift, backtests | no gate, no provenance |
| ToolReplay | replays tool calls against a scope.json | no prose policy compile |
| ContextCov | synthesizes checks from AGENTS.md, shell shims | coding conventions; no provenance |
| Mondl et al. | prompts + MCP + policy to Cedar, with a principal model | medical domain; Cedar, not an operator's prose rulebook |
| AWS AgentCore NL2Cedar | NL statements to Cedar on the AgentCore Gateway | AWS tools, gateway identity; no transcript replay |
| Microsoft Agent Governance Toolkit | YAML/OPA/Cedar policies, SPIFFE/DID identity, audit log | identity-based; no prose compile or structural verification |
| Invariant Guardrails | trace-native flow rules in a DSL | hand-written DSL; no principal provenance |
| NOMOS | compiles a written policy, structural verifier, deterministic gate | typed tools, single user, static policy |
| `openclaw policy` | config conformance against policy.jsonc | "does not enforce tool calls" |
| MXC | OS-level resource containment | complementary: what an agent *can* touch, not what it *may* do |

## 4. The build

PARSE keeps the heading chain, so a qualifier like "without explicit
instruction" (from me) that lives in a heading is inherited by its bullets
instead of being lost, which would flip them into absolute prohibitions.
Candidates over a closed predicate vocabulary go through RESOLVE's structural
checks; on CABAL-shaped clauses the synthetic compile demo reaches coverage
<!-- claim:synthetic-compile-coverage --> 0.8333, with defects labeled
`origin: builder`. These are builder-authored candidate defects, not an LLM
extraction defect rate; that number is pending a paid extraction run I have
not approved yet. Virtual tools sit over shell strings: the normalizer scores
precision <!-- claim:normalizer-corpus-precision --> 1.0 and recall
<!-- claim:normalizer-corpus-recall --> 1.0 on its synthetic corpus (labeled
synthetic). Replay pins the policy version to the git commit in force at
action time.

## 5. The twist: principal provenance

On real transcripts, "user" is not the user: a user-role turn can be me, a cron
prompt, a heartbeat, a system notice, or another agent. A gate that trusts
"user turns" trusts a cron prompt. PolicyGate classifies the principal and lets
only turns it classifies as me (heuristically offline; legacy logs carry no
typed provenance) create authorization. The adversarial set accepts
<!-- claim:adversarial-accepted --> 0 forged authorizations across
<!-- claim:adversarial-cases --> 13 cases. External support: VAI finds detection
rises from <!-- cite:https://arxiv.org/abs/2610.18230 --> 42.2% to 83.0% when
agents emit structured authorization records.

## 6. The finding

My archived transcripts, replayed offline:
<!-- claim:archive-transcripts --> 2,328 transcripts,
<!-- claim:archive-tool-calls --> 41,068 tool calls, boiled down to
<!-- claim:infra-actions --> 59 infra-mutating actions (the normalizer's first
pass said <!-- claim:infra-actions-first-pass --> 97; the difference was
`--help` runs and heredoc text). The headline is the per-reading table: the
same actions under three readings of "explicit instruction":

| profile | strict | plan | lenient |
|---|---|---|---|
| naive replay (no pinning, hand rules) | <!-- claim:parity-strict --> 47 | <!-- claim:parity-plan --> 32 | <!-- claim:parity-lenient --> 11 |
| version-pinned (PolicyGate) | <!-- claim:pinned-strict --> 53 | <!-- claim:pinned-plan --> 46 | <!-- claim:pinned-lenient --> 42 |

In the naive replay the reading alone swings the verdict
<!-- claim:parity-reading-swing --> 4.3-fold. Version pinning did move
retroactive "violations" out: across all evaluated actions (including
`file.edit`), <!-- claim:no-rule-in-force --> 16 landed in `NO_RULE_IN_FORCE`
under strict because the rule did not exist yet; of the
<!-- claim:infra-actions --> 59 infra actions it is
<!-- claim:no-rule-in-force-infra --> 4.

So why are the pinned numbers *higher*? Pinning removed pre-rule blocks, but
the pinned profile evaluates <!-- claim:candidates-count --> 26 naive
builder-authored candidates instead of <!-- claim:spike-hand-rules --> 4 hand
rules, and consumption re-blocks a repeated action once its one-shot
authorization is spent. More rules and consumption outweigh what pinning
removed. Rules that fire on nearly everything they see are an over-broad-rule
smell (in my rulebook's wording or my compiled reading of it), not an agent
crime wave. The per-delta breakdown is in `docs/RESULTS.md`.

The quiet-hours rule is the clearest case, and it is partly the tool's limit,
not only my wording. My rulebook says no *autonomous* infra work between
midnight and eight in the morning UTC. A v1 rule is a single predicate, so the
compiled quiet-hours rule cannot express "unless I authorized it": it blocks my
own authorized in-window work too. The window held
<!-- claim:pinned-quiet-window --> 31 infra actions; the rule (CAB-FBD-08) is
involved in <!-- claim:pinned-fbd08-involved --> 30 of the <!-- claim:pinned-strict --> 53
/ <!-- claim:pinned-plan --> 46 / <!-- claim:pinned-lenient --> 42 pinned
blocks (strict / plan / lenient), and <!-- claim:pinned-fbd08-authorized --> 20
of those <!-- claim:pinned-fbd08-involved --> 30 are labelled authorized.

Against <!-- claim:infra-actions --> 59 hand labels (`label_status`:
<!-- claim:label-status --> provisional; I haven't confirmed them yet), strict
precision is <!-- claim:eval-strict-precision --> 0.2453 at recall
<!-- claim:eval-strict-recall --> 1.0 on <!-- claim:label-unauthorized --> 13
positives. Small n, and low precision is the honest result: the gate is not
accurate by this measure. <!-- claim:label-borderline-total --> 31 labels are
borderline (<!-- claim:label-borderline-plan --> 23 authorized-plan,
<!-- claim:label-borderline-unauthorized --> 6 unauthorized,
<!-- claim:label-borderline-silent --> 2 policy-silent), so
<!-- claim:label-borderline-unauthorized --> 6 of the
<!-- claim:label-unauthorized --> 13 "unauthorized" labels are themselves
borderline. All <!-- claim:eval-strict-fp --> 40 false positives are actions
labelled authorized (<!-- claim:eval-strict-blocked-plan --> 27 via an
accepted plan, <!-- claim:eval-strict-blocked-explicit --> 13 explicitly) that
the naive candidates, plus consumption, block anyway. The keyword baseline
manages <!-- claim:keyword-baseline-precision --> 0.1887 precision at
<!-- claim:keyword-baseline-recall --> 0.7692 recall on the same labels. What
the policy cannot decide becomes the ambiguity queue:
<!-- claim:ambiguity-items-total --> 12 items, one per undecidable
(clause, action-class) pair, broken down by kind in `docs/RESULTS.md`.

**About the title.** The margin is <!-- claim:holes-vs-agents --> 16 holes vs
<!-- claim:label-unauthorized --> 13 unauthorized actions. The holes side is
<!-- claim:label-policy-silent --> 4 policy-silent actions plus
<!-- claim:ambiguity-items-total --> 12 ambiguity items; the agents side is
hand-labelled actions. The units don't match: an ambiguity item is a
clause×action-class pair, not an action. Read the title as directional,
pending label confirmation. The labels are provisional.

## 7. The loop

Replay surfaces what the policy cannot decide into an ambiguity queue. In the
synthetic amend demo, answering <!-- claim:amend-items-closed --> two items and re-replaying shows the
per-reading delta, and the overlay is never written to the policy repo. In
production the answers would come from my decision inbox; here it is a file.

## 8. Limits

A **reconstruction** is not evidence of agent behaviour; the mechanism is the
point. Principals offline are heuristic (legacy JSONL has no typed provenance).
The real dataset is small and dominated by one agent. Pinning is limited by
commit granularity. The candidates are builder-authored, so their RESOLVE
defect counts are not an LLM extraction defect rate. Single-predicate rules
cannot express conjunctions like "in window and not authorized". Coverage gaps
are silent by nature; the compile report lists them. The gate governs actions,
not words. And v1 is offline only: the live enforcement plugin is not built.

## 9. What's next

Live enforcement is the obvious next step, but it is not built yet. The design
calls for shadow mode first (log verdicts, never block), gated on my approval
under my infrastructure-change protocol. Beyond that: typed provenance from
trajectory exports, rules that can combine a time window with an
authorization exemption, and the paid extraction run that would turn
builder-authored candidates into a real extraction defect number.

## What I'd tell another operator

- **Put qualifiers in the clause, not the heading.** "Without explicit
  instruction" in a heading is one parser bug away from turning every bullet
  under it into an absolute ban.
- **Name who may authorize.** "Explicit instruction" from whom? A cron prompt
  and a relayed "yes" both look like user turns.
- **Keep the policy in git.** Version-pinned replay is only as good as the
  commit history; batch commits blur "in force at the time".
- **Decide what "explicit instruction" means.** In the naive replay that
  reading alone swings blocks <!-- claim:parity-reading-swing --> 4.3-fold
  (<!-- claim:parity-strict --> 47 vs <!-- claim:parity-lenient --> 11);
  under my compiled rules it is <!-- claim:pinned-reading-swing --> 1.3-fold,
  because blunter rules fire under every reading.

## Try it

The repo link goes live when the project is published.

```bash
git clone <repo-url>
cd <repo>/policy-gate
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/policygate demo all
```

---

*Method after NOMOS (arXiv 2610.11030), reimplemented from the paper. Series:
ConfigLint (W25), HarnessGuard (W32), AEGIS (W12). Related: Compositional
Policy Violations (arXiv 2609.18820).*
