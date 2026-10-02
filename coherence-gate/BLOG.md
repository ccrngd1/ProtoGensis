# Information Is Not Ownership

*Part 2 of CoherenceProbe. Prevent at commit instead of detecting afterward.*

Here's a result from Heng's "Global Coherence" paper (arXiv [2610.02036](https://arxiv.org/abs/2610.02036)) that stopped me mid-scroll.

A team of LLM agents shares a budget of 20 tool calls. Without any visibility into the team's spending, the team went over budget 5 out of 5 times. No surprise. Then Heng put the **live call count in every agent's context**. They could see exactly how many calls the team had used. They still overspent 4 out of 5 times.

A commit-time ledger (code that refuses any draw past the limit) brought that to 0/5. Per-role escrow quotas brought it to 0/5 too. The agents didn't need to be more careful. The constraint needed an **owner**.

That's the paper's key insight: information is not ownership. And it's why I built CoherenceGate.

## Two Failure Modes (Keep Them Separate)

The paper formalizes two root causes for team-level failures. They look similar but need completely different fixes. Conflating them is how you build the wrong tool.

**Failure 1: Missing information (observation aliasing).** Two world states look identical from the agent's perspective, but they require different actions. More reasoning doesn't help. More agents don't help. The information isn't there. The fix: add the missing distinction to context, or give the agent a tool that can see it. Thm 2.1 proves that the best any policy can do under aliased observations is 1/k, where k is the number of states that look the same. Cor 2.2 proves a manager agent is bound by the same limit.

**Failure 2: Present but split information (unowned invariants).** Every agent sees its piece, every local check passes, and the global constraint still breaks. This is the budget result. The fix: code that owns the constraint at commit time. Not a smarter agent, not a manager agent (Cor 2.2 binds a manager too). A ledger. An escrow. Prop 3.3 shows that locally legal spends on a shared snapshot can jointly exceed the limit.

If you build agent infrastructure and use the same mitigation for both, one of them isn't getting fixed.

## What I Built

CoherenceGate is an executable, commit-time version of the paper's harness. Models propose, an authoritative store holds the facts that matter, and a governed commit decides which proposals change the world. The gate returns **accept**, **repair** (here are the fresh values, re-propose), or **reject** (here's the reason and remaining headroom).

It sits alongside existing tools, not above them. The version-check foundations that [`agent-coherence`](https://github.com/Cohexa-ai/agent-coherence) already ships are compatible. On top of those, CoherenceGate adds five things the paper calls out: **read sets built from context assembly** (not traced from HTTP or parsed from model output), **invariant owners at commit** (ledger and escrow), **a committed-effect monitor** (catches silent reverts), **an identifiability audit** (can this context determine the right action?), and **an ownership-alignment lint** (is the guard counting the same unit the grader counts?).

The paper's code is not yet released. This build follows the paper text.

```python
from coherencegate import (InMemoryStore, ContextAssembler, CommitGate,
                           Ledger, Unit, Proposal)

store = InMemoryStore({"price": 100})
gate  = CommitGate(store,
                   invariants=[Ledger("run_calls", 20, Unit("tool_call", "run"))])

ctx   = ContextAssembler(store).for_agent("assistant", "support")
price = ctx.show("price")          # "[price@v1] = 100", records the read

outcome = gate.commit(Proposal(
    agent="assistant", role="support",
    writes={"order": {"qty": 1}},
    read_set=ctx.read_set,          # by construction, not tracing
    draws={"run_calls": 1}          # owned by the Ledger
))
# outcome: Accept | Repair(stale_keys, fresh) | Reject(reason, headroom)
```

The read set is the key differentiator from other approaches. Because the harness assembled the prompt, it knows what the proposal saw by construction. You don't trace HTTP calls or parse model outputs. The read set is a byproduct of context assembly. S-Bus (arXiv [2605.17076](https://arxiv.org/abs/2605.17076)) measured that 74% of agent reads are invisible at the HTTP layer. CoherenceGate sidesteps that problem by building the context itself.

## Demo: The Budget

*All demos use scripted mock agents, fixed seeds, and pre-registered parameters. Reproduction-style, not a replication of paper numbers. They show the mechanism; they are not evidence about real model behavior.*

Three mock roles (Planner, Executor, Verifier) share a limit of 20 `run` calls. Seeds, demand ranges, batch sizes, escrow quotas, and the stop rule were committed before the first run. Five seeds, five arms:

| Arm | Over budget (of 5) | Calls (median, range) | Refusals | Progress |
|---|---:|---:|---:|---:|
| ordinary | 4/5 | 23 (18-30) | 0 | 1.000 |
| visible_state | 0/5 | 19 (18-20) | 0 | 0.890 |
| ledger | 0/5 | 20 (18-20) | 11 | 0.902 |
| escrow | 0/5 | 19 (17-20) | 17 | 0.759 |
| wrong_unit_ledger | 4/5 | 23 (18-30) | 0 | 1.000 |

A few things to notice. Progress ignores the budget, so non-gate arms can score high by overspending. The gate arms (ledger, escrow) are 0/5 by construction. The informative rows are the non-gate arms and progress. And `wrong_unit_ledger` is the ownership-alignment trap: the guard counts `write_file` calls while the grader counts `run`. The lint catches it (OWN001). If you've ever alarmed on the wrong CloudWatch metric while the thing you actually cared about burned, you've felt this one.

The escrow quotas (`{planner: 2, executor: 12, verifier: 6}`) are our choice, not the paper's configuration.

**Now the honest part.** I predicted `visible_state` would overspend on at least 1 of 5 seeds. It didn't. The prediction was falsified. The pre-registered result is final.

Why did it hold? Every scripted agent obeyed a conservative stop rule: a role that sees no room stops for good. With one small batch per role per round and that rule, the worst case lands at the limit rather than past it on these seeds. Visible state stayed in budget only because every scripted agent obeyed that conservative stop rule. The ledger and escrow held **without** that stop rule.

That's the paper's point. And their LLM teams (gpt-6-sol) overspent at 4/5 under the same visible-state design (paper result, not ours). Prop 3.3 says nothing forces locally legal spends on a shared snapshot to stay under a global limit. Our scripted agents stayed under because we wrote them to be careful, not because visible state guarantees it. We haven't run this harness with real LLMs. 41 of 56 role decisions across the 5 seeds were made against a displayed count greater than zero, so the arm is not degenerate.

**Exploratory arm** (post-hoc, added after the pre-registered result): `visible_state_lax` uses the same seeds and superstep, but each role spends whenever the displayed count is under the limit, skipping the conservative own-batch check.

| Arm | Over budget (of 5) | Calls (median, range) | Progress |
|---|---:|---:|---:|
| visible_state_lax | 3/5 | 21 (18-23) | 0.937 |

Without the conservative stop rule, visible state went over 3/5. The ledger and escrow still held at 0/5 under this relaxed rule (tested as a mechanism claim). Safety under visible state depended on every agent's own discipline. Ownership doesn't.

*Paper reference (arXiv 2610.02036 Study IV, gpt-6-sol; not our numbers): ordinary 5/5 over (57-72 calls). visible_state 4/5 over (median 70 to 29 calls). ledger 0/5, stopping at exactly 20. escrow 0/5, mean partial 0.960 vs ledger 0.874 (descriptive; confounded attestation gates). Paper limits: single author, one model family, 5 seeds per cell.*

The full pre-registration record, including changes and Amendment 1, is in [`.mastercontrol/preregistration.md`](.mastercontrol/preregistration.md).

## Demo: Thinking Harder Doesn't Help

The identifiability probe (Study I analogue). Same task, 40 instances, 3 possible truths. In the identifiable variant, every arm scores 120/120 (40 tasks times 3 truths, evaluated against all truths). In the aliased variant, the critical event is redacted. The prompts across the 3 truths are byte-identical (sha256-verified).

Every deterministic mock arm on the aliased variant scored exactly 40/120: the competent policy, planner+verifier, 5-vote majority, and a tool that can't see the event. That's exactly 1/k = 1/3. Adding one authoritative sentence, or a tool that can read the event, brought it back to 120/120.

The theorem in plain words: if the worlds consistent with what you see don't all share a valid action, no policy can do better than 1/k. More reasoning won't help. More agents won't help. Majority voting won't help. The only fix is putting the missing distinction in the agent's context.

The mock arms *show* the theorem. The paper's arms *measured* it on a real model: aliased accuracy ranged from 12/40 to 17/40 across effort levels, planner+verifier scored 13, and 5-vote majority scored 13/39. A reading tool brought it back to 40/40. One authoritative sentence did the same.

## Demo: Stale Quotes and Silent Reverts

A telecom-style scenario with three tasks. Agent S quotes a price, and the price changes before the order commits. Agent P sets roaming, and a background process silently reverts it. Agent A triggers an authority-restricted action.

| Task | Unguarded | Conventional | CoherenceGate |
|---|---|---|---|
| S (stale quote) | committed stale | committed stale | repaired, re-quoted |
| P (silent revert) | undetected | undetected | 1 notice, holds |
| A (authority) | not blocked | blocked | blocked |

Conventional checks (current-state preconditions at call time) caught the authority violation but committed the stale quote. The gate's cross-key read-set validation caught it: S's proposal had read `price@v1`, and `price` had moved to v2. A per-key compare-and-swap on the written key (`order`) alone would have accepted it. The repair returned the fresh value. S re-quoted. The order committed at the right price.

The silent revert is the effect monitor in action. One notice to the committing agent was enough.

Task A is a **predicted tie**: conventional checks already own this state, and the gate adds nothing here. Zero false rejections across all arms.

*Paper reference (arXiv 2610.02036 Study V, gpt-6-sol; not our numbers): silent reverts scored 0.00 / 0.07 / 1.00 (15/15) for unguarded / conventional / coherence. Conventional checks committed the stale quote 10/10. Predicted tie on authority-precondition cases confirmed.*

## When You Don't Need It

The single-agent demo is the second predicted tie. With one agent and full state, the gate changes no outcome and makes zero rejections (Cor 4.2: needed only where the context map can lose information). It tells you when you don't need it.

Both ties are tested and labeled. A tool that never says "you don't need me here" isn't credible. CoherenceGate says it twice.

## Where This Sits

This is Part 2 of a two-part build. [CoherenceProbe](https://github.com/ccrngd1/ProtoGensis/tree/main/coherenceprobe) (arXiv [2605.30335](https://arxiv.org/abs/2605.30335)) detected team incoherence after the fact using NLI contradiction detection. It worked, but detection is linear and minimum repair is NP-hard (Max-Cut-hard per Prop 3.6). The paper's design rule: check before commit rather than repair afterward. CoherenceGate is that check.

The past year brought serious prior art in agent concurrency control. [`agent-coherence`](https://github.com/Cohexa-ai/agent-coherence) (from Token Coherence, arXiv [2603.15183](https://arxiv.org/abs/2603.15183)) ships TLA+-verified compare-and-swap with framework adapters. CoAgent (arXiv [2606.15376](https://arxiv.org/abs/2606.15376)) adds advisory notifications plus saga undo. S-Bus (arXiv [2605.17076](https://arxiv.org/abs/2605.17076)) measured that 74% of agent reads are invisible at the HTTP layer. STORM (arXiv [2605.20563](https://arxiv.org/abs/2605.20563)), Atomix (arXiv [2602.14849](https://arxiv.org/abs/2602.14849)), ATCC (arXiv [2603.13906](https://arxiv.org/abs/2603.13906)), and OptiMA (arXiv [2511.03761](https://arxiv.org/abs/2511.03761)) each tackle coordination and serialization from different angles. A position paper (arXiv [2608.18092](https://arxiv.org/abs/2608.18092)) argued that MAS should prioritize concurrency control above new capabilities.

Those systems make shared writes serializable or non-clobbering. CoherenceGate treats `agent-coherence` as compatible, not a competitor: use it for artifact-level compare-and-swap, use CoherenceGate for the checks serializability alone doesn't buy. The classical lost-update scenario (`agent-coherence` already prevents this) ships as `demo warmup` for completeness, with explicit credit to Kung and Robinson (1981). What the paper adds on top is invariant ownership, context sufficiency as a formal property, and committed-effect tracking. CoherenceGate is that checklist in executable form.

If you work with DynamoDB, the analogies are direct. A conditional write on a version attribute is OCC. Escrow quotas are provisioned capacity per tenant. A guard on the wrong variable is alarming on the wrong CloudWatch metric.

## Limits

Single author. One model family (gpt-6-sol). Five seeds per cell. A synthetic aliasing probe by design. Injected failures in the telecom panel. The escrow vs. ledger progress comparison is descriptive (confounded attestation gates). The paper's code is not yet released. Our demos use scripted mock agents and show the mechanism, not model behavior. Real-LLM behavior of this harness has not been benchmarked.

## Try It

Not published to a package registry. Install from source:

```bash
git clone https://github.com/ccrngd1/ProtoGensis.git
cd ProtoGensis/coherence-gate
pip install -e .
```

Python 3.11+, zero runtime dependencies.

```bash
coherence-gate demo budget
coherence-gate demo identifiability
coherence-gate demo telecom
coherence-gate demo single-agent
coherence-gate lint ownership --config coherencegate/demos/config/wrong_unit.json
```

---

**Paper:** Xin Heng (Tote AI), "Global Coherence: When Every Agent Is Right and the Team Is Still Wrong," arXiv [2610.02036](https://arxiv.org/abs/2610.02036), 2026.

**Part 1:** CoherenceProbe, arXiv [2605.30335](https://arxiv.org/abs/2605.30335).

**Code:** [github.com/ccrngd1/ProtoGensis](https://github.com/ccrngd1/ProtoGensis) (MIT).
