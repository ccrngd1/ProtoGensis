# CoherenceGate

> **CoherenceGate** is an executable, commit-time version of the harness in Heng's *Global
> Coherence* paper (arXiv 2610.02036): models propose, an authoritative store holds the
> distinctions that matter, and a governed commit decides which proposals change the world. On top
> of the version checks that tools like [`agent-coherence`](https://github.com/Cohexa-ai/agent-coherence)
> already ship, it adds **invariant owners** (ledger and escrow), **read sets built from context**,
> a **committed-effect monitor**, and two audits (**identifiability**, **ownership alignment**).
> It's the sequel to CoherenceProbe: that tool *detected* team incoherence afterward, and this one
> *prevents* it at commit. The paper's code is not yet released; this is built from the paper text.

**Paper:** arXiv 2610.02036, Xin Heng (Tote AI), "Global Coherence: When Every Agent Is Right
and the Team Is Still Wrong" (2026). The paper's code is unreleased; this build follows the paper
text only and claims no parity with the authors' harness, TeamBench (2605.07073), or τ²-bench
(2506.07982).

**Related work / prior art.** 2026 brought a wave of agent concurrency control:
[`agent-coherence`](https://github.com/Cohexa-ai/agent-coherence) (Cohexa-ai; shipped OSS,
TLA+-verified compare-and-swap, from Token Coherence, 2603.15183), CoAgent (2606.15376),
S-Bus (2605.17076), STORM (2605.20563), Atomix (2602.14849), ATCC (2603.13906), OptiMA
(2511.03761), `tower-protocol`, and a position paper arguing MAS should prioritize concurrency
control (2608.18092). Those systems make shared writes serializable or non-clobbering.
CoherenceGate treats `agent-coherence` as compatible, not a competitor: use it for artifact-level
compare-and-swap; use CoherenceGate for the checks serializability alone doesn't buy. The
version-validation core is classical optimistic concurrency control, credited to
**Kung & Robinson (1981)** — the paper calls its own use "deliberately borrowed". Escrow quotas
follow O'Neil (1986); invariant confluence follows Bailis et al. (2014); the join-tree result is
Beeri–Fagin–Maier–Yannakakis (1983).

## The two failure modes (keep them separate)

| | Failure 1: observation aliasing | Failure 2: unowned invariants / non-gluing |
|---|---|---|
| What's wrong | Information is **missing**: two worlds look identical but need different actions | Information is **present but split**: each local piece passes, the whole is invalid |
| Formal statement | Thm 2.1/2.3 (1/k bound), Cor 2.2 (more agents don't help) | Thm 3.1 (trees fine, cycles not), Prop 3.3 (shared budget) |
| Does more context fix it? | **Yes**, if it adds the missing distinction | **No.** The live count in context still gave 4/5 violations (paper Study IV) |
| Fix | Put the distinction in context, or a query tool that splits the fiber | An owner at commit: ledger or escrow |
| Where it lives here | `IdentifiabilityAudit` (audit, not gate) | `Ledger`/`Escrow` owners in the `CommitGate` |

Stale reads are a third, classical thing: they live in the gate as read-set validation
(`StaleReadValidator` behavior via `CommitGate`), and a stale-read rejection is never called
"aliasing". Invariants refuse; notices advise. An orchestrator agent is never an "owner" — the
owner is code at commit (Cor 2.2 binds a manager agent too).

## Install

Not published to any package registry. Install from source:

```bash
git clone https://github.com/ccrngd1/ProtoGensis.git && cd ProtoGensis/coherence-gate && pip install -e .
```

Python ≥ 3.11, zero runtime dependencies (stdlib only). Optional extras:
`pip install -e ".[bedrock]"` (boto3, live tool-loop runs only), `pip install -e ".[langgraph]"`,
`pip install -e ".[dev]"` (pytest).

## What it does

```python
from coherencegate import (InMemoryStore, ContextAssembler, CommitGate,
                           Ledger, Unit, Proposal, EffectMonitor)

store = InMemoryStore({"price": 100})
monitor = EffectMonitor(store)
gate = CommitGate(store,
                  invariants=[Ledger("run_calls", 20, Unit("tool_call", "run"))],
                  monitor=monitor)

ctx = ContextAssembler(store).for_agent("assistant", "support")
price = ctx.show("price")        # renders "[price@v1] = 100", records the read
prompt = ctx.render()            # read set is now frozen; send prompt to the model

outcome = gate.commit(Proposal(
    agent="assistant", role="support",
    writes={"order": {"qty": 1, "unit_price": price}},
    read_set=ctx.read_set,                 # by construction, not by tracing
    draws={"run_calls": 1},                # commutative draw, owned by the Ledger
    postconditions={"order_placed": True}  # the monitor re-checks this later
))
# outcome is Accept | Repair(stale_keys, fresh) | Reject(reason, headroom)
```

The five pieces, mapped to the paper's harness X = (H, C, G, F; D):

- **Store** (D): versioned authoritative state, two backends (`InMemoryStore`, `SQLiteStore`)
  at parity. Owned-resource draws are stored separately from versioned keys, so spenders never
  version-conflict on a shared counter.
- **ContextAssembler** (D): the only path by which authoritative facts enter a prompt. Every fact
  is tagged `[key@vN]` and the read set is recorded as a side effect of rendering. This is the
  main technical differentiator: the harness assembled the prompt, so it knows what the proposal
  saw *by construction* — the read-set capture that CoAgent calls "opaque" and that S-Bus measures
  as 74% invisible at the HTTP layer. A model-cited `premises` field can narrow the read set,
  never widen it.
- **CommitGate** (C/F): authority → read-set validation → invariants → atomic apply. Cross-key
  stale reads are caught (a proposal that read `price@v1` and writes only `order` gets `Repair`
  after `price` moves) — a per-key compare-and-swap on the written key alone would accept it.
- **Ledger / Escrow** (F): invariant owners. A ledger refuses any draw past the global limit; an
  escrow refuses past the role's quota. Two in-limit draws from the same snapshot are both
  accepted — no OCC thrash on counters.
- **EffectMonitor** (C/D): committed postconditions are re-checked on store events and turn
  boundaries. A silent revert produces exactly one advisory notice per breakage.
- **Audits**: `IdentifiabilityAudit` (can this context determine the right action at all? Thm
  2.1/2.3 as a test) and `ownership_lint` (does the guard count the unit the grader counts?
  the paper's Panel 1 failure → lint `OWN001`/`OWN002`). `Topology` ships a GYO join-tree check
  (Thm 3.1) and a Bernstein parallel-safety table.

## Demos (deterministic, offline, scripted mock agents)

Every demo prints the citation and the banner **"reproduction-style, not a replication of paper
numbers"**: scripted mock agents show the *mechanism*; they are not evidence about real models.
Paper numbers appear only in separately labeled paper-reference blocks. Real-LLM behavior of this
harness: not benchmarked.

```bash
coherence-gate demo budget          # visible state held only via a conservative stop rule; ledger/escrow held without one
coherence-gate demo identifiability # the aliasing probe: chance-level collapse and recovery
coherence-gate demo telecom         # stale quote repaired; silent revert noticed; authority tie
coherence-gate demo single-agent    # the second predicted tie: the gate when you don't need it
coherence-gate demo warmup          # classical lost update; agent-coherence already prevents this
coherence-gate lint ownership --config coherencegate/demos/config/wrong_unit.json  # exit 1, OWN001
coherence-gate report --runlog run.jsonl --format md
coherence-gate topology check --config roles.json
```

(Equivalently `python3 -m coherencegate ...` without installing the console script.)

The budget demo's seeds, arms, policy parameters, escrow quotas, and progress metric are
pre-registered in `coherencegate/demos/config/budget.json` and were committed before the first
results run. The gate arms' 0/N is true by construction (the paper notes the same about its own
ledger arm); the informative rows are the non-gate arms and progress. The progress metric ignores
the budget, so non-gate arms can score high progress by overspending. On the pre-registered seeds,
ordinary went over 4/5 and visible_state 0/5: AC #8's ≥1/5 prediction for visible_state was
falsified for our scripted agents, and the pre-registered result is reported and final
([Amendment 1 in `.mastercontrol/preregistration.md`](.mastercontrol/preregistration.md)).
**Visible state stayed in budget only because every scripted agent obeyed a conservative stop
rule. The ledger and escrow held with no such rule.** That's the paper's "information is not
ownership" point, and their LLM teams overspent at 4/5 (paper result, not ours). A post-hoc
exploratory arm, `visible_state_lax` (same seeds and superstep, but each role spends whenever
the displayed count is under the limit, skipping the own-batch check), went over 3/5 — labeled
"exploratory, added after the pre-registered result" and reported in its own block, never in
the pre-registered table. A gate-property test checks that ledger and escrow stay 0/5 under the
lax rule too (a mechanism claim: the owner holds the invariant without any agent stop rule).
**The ties are shown on purpose**: a tool that never says "you don't need me here" isn't credible.

## Design notes / ambiguities

- The visible_state mock rule models Prop 3.3's mechanism: each round, every role that still has
  demand reads the same round-start snapshot (rendered into its context by `ContextAssembler`,
  display-only) and proposes exactly one 1–3-call batch against it, so no decision sees another
  role's same-round spending (Cor 2.2). The rule is conservative: a role that sees no room stops
  for good. Under this literal pre-registered policy, visible_state came out 0/5 over on the
  pre-registered seeds (vs ordinary's 4/5): one small blind batch per role per round plus the
  same-x stop rule lands at the limit rather than past it here. That conservative stop rule is
  scripted into every mock agent; the paper's LLM teams overspent at 4/5 (paper result, not
  ours; our harness has not been run with real LLMs). An earlier build's 0/5
  came from a different cause (it re-read the count between roles' turns — an implementation
  deviation from the spec, since corrected). All runs and changes are documented in
  `.mastercontrol/preregistration.md`; no seed search was performed.
- The escrow quota split `{planner: 2, executor: 12, verifier: 6}` is our choice, not the paper's
  configuration.
- `out_of_band` writes model environment actors (price moves, silent reverts) and are logged as
  `source=environment`; they are intentionally not subject to the gate.
- Live Bedrock mode (`--live bedrock`) imports boto3 lazily inside the adapter and is never used
  by tests. The Converse codec is tested against recorded JSON fixtures.
- Deferred to v0.2+: MCP server gate, translation-loop (G) checks (the paper's Prediction 2 says
  they add little without representation multiplicity), an `agent-coherence` Store backend,
  multi-host coordination.

## Relation to CoherenceProbe (W23)

CoherenceProbe did post-hoc NLI contradiction detection on team outputs (arXiv 2605.30335) — it
*detected* incoherence afterward. CoherenceGate *prevents* it at commit. The paper backs the
ordering: detection is linear, but minimum repair is Max-Cut-hard (Prop 3.6); its design rule is
"check before commit rather than repair afterward."

## Paper limits (stated wherever its numbers appear)

Single author; one model family (gpt-6-sol); small panels (5 seeds per cell); a synthetic aliasing
probe by design; injected τ²-style failures; the escrow-vs-ledger progress comparison is
descriptive (confounded attestation gates); code not yet released. Our demos use scripted mock
agents and are labeled accordingly.

## License

MIT. See [LICENSE](LICENSE).
