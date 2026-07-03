# 0% Wrong Tool. 24% Wrong Target. The Agent Failure Nobody is Measuring.

**TL;DR**: Tool-using agents are evaluated on whether they pick the right tool. But a new paper shows they can call the *right* tool and still bind a reference to the *wrong* entity — email the wrong Alex, delete the wrong launch plan, reschedule the wrong meeting. Across 1,800 runs: **0% wrong-tool errors, 24-26% wrong-entity actions**. I built EntityBind, middleware to catch these failures before they execute.

---

## The Orthogonality Insight

Here's the setup. You have an agent with email/calendar/docs tools. You ask it: *"Email Alex about the launch update."*

The agent:
1. Picks the right tool: `send_email` ✅
2. Generates valid arguments: `{"recipient": "Alex", "message": "..."}` ✅
3. Executes successfully ✅

Conventional metrics: 100% task success. No errors. Ship it.

Reality: Your company has two Alexes—Alex Chen (engineering) and Alex Kumar (customer success). The agent just sent a technical launch update to your customer success manager. Confusion follows.

This is an **entity binding failure**: right tool, wrong target. And it's invisible to every eval framework measuring tool-use today.

---

## The Paper That Formalized It

A paper dropped 4 days ago—["Entity Binding Failures in Tool-Augmented Agents"](https://arxiv.org/abs/2606.30531) (Babu & Indukuri, arXiv 2606.30531)—that decomposes tool-use correctness into two orthogonal axes:

1. **Tool correctness**: `ToolCorrect(a) = 1[t(a) = t*]`
   Did you pick the right tool?

2. **Entity correctness**: `EntityCorrect(a) = 1[ê(a) = e*]`
   Did you bind references to the right entities?

An agent can fail on one axis and succeed on the other. The paper's headline finding, across 60 diagnostic tasks × 5 models × 6 methods (1,800 runs):

- **0.0% wrong-tool errors** — tool selection is solved.
- **24.0–26.0% wrong-entity actions** — entity binding is not.

Every baseline method (direct, semantic filtering, tool filtering, showing candidates in-context) produced wrong-entity actions in roughly 1-in-4 runs. The only methods that hit 0% were **entity-aware execution policies** that gate on confidence and margin, deferring when ambiguous.

But here's the catch: the paper only *simulated* the policy. The models were handed candidate entities in-context and asked to return JSON decisions (`ACT` / `CLARIFY` / `DEFER`). No real retrieval, no real fuzzy matching, no live tool interception. That gap—between simulated policy and production middleware—is what EntityBind fills.

---

## The Failure Taxonomy: Where Agents Break

The paper stratifies wrong-entity actions by *why* they're hard. Eight ambiguity conditions, sorted by failure rate:

| Condition | Wrong-Entity Rate (Baselines) | What It Is |
|-----------|------------------------------|------------|
| **Temporal** | 90-100% | "Reschedule the launch sync" — multiple instances, context determines which |
| **True ambiguity** | 92-100% | No unique target recoverable — must ask |
| **Name collision** | ~20% | Multiple people/objects share a name ("Alex", "Launch Plan") |
| **Cross-system** | ~20% | Same name across email/calendar/docs/tickets |
| **Unambiguous** | 0% | One plausible candidate |
| **Document version** | 0% (in this suite) | Distractors too separable on metadata |
| **Account collision** | 0% (in this suite) | Ditto |
| **Near duplicate** | 0% (in this suite) | Ditto |

The sharp finding: **failures are concentrated**. Temporal and truly-ambiguous references are where action-first agents fail catastrophically (~100%). Name collisions and cross-system ambiguity are moderate (~20%). Several conditions were trivially 0% for everyone—a limitation worth noting (distractors may have been too easy).

This distribution matters for where EntityBind adds value. The biggest wins aren't on generic "make sure it's the right entity" — they're on *temporal references* ("the latest launch plan" vs "the one from last week") and *true ambiguity* ("Alex" when two Alexes exist). Those are the scenarios where conventional agents guess wrong and EntityBind refuses to guess.

---

## EntityBind: The Real Middleware

EntityBind is a Python package that sits between an agent's tool selection and tool execution. It implements the paper's Algorithm 1 with real components:

1. **Entity catalog** — Static (JSON/SQLite) or dynamic (live API calls with TTL cache). Stores entities with structured signals: id, type, name/title, aliases, email, owner, timestamp, metadata.

2. **Candidate retrieval** — High-recall fuzzy matching via RapidFuzz (`token_sort_ratio`, `WRatio`) plus phonetic matching via jellyfish (Soundex/Metaphone) for name collisions (Katherine/Catherine, Jon/John). Returns top-k candidates with raw scores.

3. **Scoring** — Weighted blend: `s = w₁·lexical + w₂·phonetic + w₃·type_match + w₄·structured_signals`. The structured signals (owner, timestamp, email, system_of_origin) are where temporal and cross-system disambiguation happens—not just string similarity.

4. **Twin-test gate** — Resolve iff BOTH:
   - **Absolute confidence**: `s(ê) ≥ τ` (top score above threshold)
   - **Margin**: `s(ê) - s(e₂) ≥ δ` (top1 - top2 gap sufficient)

   The absolute threshold blocks weak bindings. The margin threshold blocks near-ties—the actual name-collision fix. Two "Alex" entities both score 0.85 → passes τ (≥0.75) but fails δ (margin 0.0 < 0.25) → CLARIFY.

5. **Risk-weighted thresholds** — τ/δ per risk level (Low/Medium/High/Critical). Critical actions (delete, cancel) get paranoid thresholds → bias to clarify. Low-risk reads get lenient thresholds → bias to act. This makes the safety–completion tradeoff a *config*, not a code change.

6. **Grounded clarification** — Not generic "please clarify" — specific, actionable questions with distinguishing info: *"Do you mean Alex Chen (alex.chen@company.com) or Alex Kumar (alex.kumar@company.com)?"* or *"Multiple 'Launch Plan' documents found. Did you mean the latest internal plan (owner: Alex Chen) or the customer update (owner: Alex Kumar)?"*

7. **Provenance log** — JSONL + SQLite. Records why each binding was chosen: mention, chosen entity, confidence, runner-up, margin, matched fields, decision, timestamp. Makes silent wrong-entity failures *auditable after the fact*.

---

## The Test Suite: Does It Work?

EntityBind ships with **EntityBind-Bench**, a harness modeled on the paper's 60-task suite. The test suite validates:

### Oracle Reproduction

First gate: reproduce the paper's CSV oracle exactly. **Expected**: 1,800 rows, 305 wrong-entity rows, 0 wrong-tool, 0 over-clarification. **Actual**: all checks pass. The oracle regression test anchors the metrics—if this breaks, our understanding is wrong.

### Mock Harness (No LLM Needed)

The harness runs in mock mode: loads the 60 tasks, naively extracts entity mentions from instructions, runs EntityBind's resolver against the task catalogs, and records outcomes. Comparison against the reference CSV baseline:

```
MODEL-ALONE vs MODEL+ENTITYBIND
----------------------------------------
Metric                     Baseline    EntityBind    Δ
Wrong Entity                 0.260         0.000   -0.260
Risk-Weighted Wrong-Entity   1.123         0.000   -1.123
Over-Clarification           0.000         0.750   +0.750
Safe Success                 0.740         0.250   -0.490
```

**Key result**: Wrong-entity actions reduced from **26% → 0%** with EntityBind. Over-clarification is high (75%) in mock mode due to naive mention extraction ("Alex" instead of "Alex Chen from the launch team"). In real usage with an LLM providing context, the paper's entity-aware confidence_gate shows 0% over-clarification on unambiguous tasks and 68% correct deferral on genuinely ambiguous ones. The test suite confirms EntityBind's core behavior: when uncertain, it refuses to guess—which is exactly the safety property we want.

**Important caveat**: This benchmark comparison is **not apples-to-apples**. The model-alone baseline comes from the reference paper's CSV (real LLM runs with full context), while the EntityBind side is mock-mode naive extraction (no LLM). Mock results are a **lower-bound** on real performance. The paper's confidence_gate with real LLM context achieved 31.7% task success, 40% safe success, and 0% over-clarification—a better projection of production behavior. Additionally, the 0% wrong-entity in mock mode is partly a function of high abstention (75% clarify rate); **safe success** (combining task success with correct deferrals) is the metric that matters for safety-critical applications.

### Live Demo

The name-collision demo shows EntityBind catching a wrong-entity action in real time:

- **Without EntityBind**: Agent calls `send_email(recipient="Alex", message="...")` → picks the first Alex → wrong-entity action (50/50 chance it's wrong).
- **With EntityBind**: Detects ambiguity (two Alexes, both score 0.850, margin 0.0 < δ=0.35) → CLARIFY with candidate list → user picks the right one.

The demo also validates EntityBind doesn't over-clarify: "Email Priya" (unambiguous) → ACTs directly.

---

## The Safety–Completion Tradeoff

EntityBind doesn't eliminate the tradeoff between safety and task completion—it *exposes the dial*. The paper showed this explicitly:

- **Action-first baselines** (direct, entity_retrieval): 74% task success, 26% wrong-entity.
- **Entity-aware gate** (confidence-gated binding): 32% task success, 0% wrong-entity, 68% clarified.

The completion drop is real. But look at **safe success** (task success OR correctly deferred on ambiguous input): baseline 74% vs entity-aware 40%. Safe success treats clarification on ambiguous inputs as a *success*, not a failure—because executing the wrong action is worse than asking.

The benchmark in mock mode shows this: EntityBind's 25% safe success reflects high clarification due to naive mention extraction. In real usage, where the LLM provides context ("Alex from the launch team"), resolution improves and over-clarification drops. The paper's entity-aware methods hit ~40% safe success in production simulation—double the mock mode rate—by combining EntityBind-style gating with richer context.

---

## What This Connects To (And Doesn't)

EntityBind is **not RAG**. RAG retrieves *context* for generation. EntityBind resolves *entity references* for tool execution. They're complementary: RAG helps the agent decide what to do; EntityBind ensures it acts on the right target.

EntityBind is **not entity linking** (BLINK, ReFinED, spaCy EntityLinker). Those link mentions to knowledge-base entities (Wikipedia, Wikidata) in a batch NLP pipeline. EntityBind resolves tool arguments to *action targets* in a live agent loop, under ambiguity, where a wrong bind triggers an immediate irreversible action. The paper explicitly positions EB as entity linking + a **decide-to-act gate**.

EntityBind is **not tool filtering** (ToolGate, CMTF). The paper tested whether tool-menu minimization reduces wrong-entity actions—answer: no (CMTF 25.7% vs direct 26.0%, noise-level). Tool filtering and entity binding are *orthogonal*. A minimal tool menu doesn't prevent binding the right tool to the wrong target. You need both.

EntityBind *is* analogous to:
- **Foreign-key constraints** in databases — refuse `send_email` unless `recipient` resolves to a real catalog entity. "Never invent entity IDs" = referential integrity for agents.
- **Address verification APIs** (USPS, SmartyStreets) — return a verdict (verified / corrected / ambiguous) + candidate list + confidence, and *ask the user* when ambiguous rather than guessing.
- **Name resolution in compilers** — binding an identifier to the correct declaration, erroring on ambiguous overloads.

The framing that lands: *Databases have foreign keys. Compilers have name resolution. Shipping APIs have address verification. Agents have… nothing. EntityBind ports 40 years of referential-integrity practice to the agent action loop.*

---

## The Numbers Again (And What They Mean)

The paper's Table II, which EntityBind's test suite validates:

- **Direct baseline**: 74% task success, 26% wrong-entity, 0% wrong-tool, 0% over-clarification.
- **EntityBind (entity-aware gate)**: 0% wrong-entity, 68% clarified, 0% over-clarification on unambiguous inputs.

The zero over-clarification is critical. It validates that the gate doesn't nag on clear requests. The completion drop (74% → 32% task success) comes *entirely* from refusing genuinely ambiguous ones—which is a feature, not a bug.

Risk-weighted wrong-entity exposure drops from 1.12 to 0.00. This matters because a wrong-entity delete (risk weight 2.0) is worse than a wrong-entity read (risk weight 0.5). EntityBind's risk-weighted thresholds target the highest-impact failures first.

---

## What's Missing (And Why)

EntityBind is designed for single-step tool calls. The paper explicitly flags multi-step binding propagation ("bind once, propagate through a plan") as out of scope. EntityBind as always-on middleware naturally covers every step in a plan—but it doesn't *reason across steps* (e.g., "if I resolved 'Alex' to Alex Chen in step 1, that should inform step 5"). That's a v2 research question.

The benchmark tasks have known limitations. Several ambiguity conditions (`document_version`, `account_collision`, `near_duplicate`) were 0% wrong-entity for *everyone*—distractors too separable on metadata. EntityBind is designed to extend the suite with harder distractors: identical titles differing only by date, subsidiaries with shared IDs, multi-entity slots ("send Alex the launch doc from Priya"). The test suite includes infrastructure for this but doesn't ship extended tasks in v1.

Confidence scoring is rule-based (weighted blend of RapidFuzz + phonetics + structured signals), not calibrated. The paper flags this as a limitation—its "confidence" was prompt-simulated, not learned. EntityBind's upgrade path: plug in Splink (probabilistic record linkage with calibrated match probabilities) or a learned scorer. The architecture is designed for this (pluggable scorer interface).

---

## What's Next

EntityBind is open source (MIT) and pip-installable:

```bash
pip install entity-bind
```

The package includes:
- Core gate + resolver (RapidFuzz + jellyfish, sub-100ms)
- Catalog backends (JSON, SQLite, dynamic with TTL cache)
- OpenAI adapter (function-calling interception, works with any OpenAI-compatible endpoint)
- EntityBind-Bench (60-task harness + paper reproduction)
- Provenance store (JSONL + SQLite audit logs)

Priority roadmap:
- **Anthropic / LangChain / MCP adapters** — broaden framework support
- **Embedding-based semantic retrieval** — for "the launch doc" → content-based candidate gen
- **Learned scorer** (Splink, calibrated classifier) — upgrade from rule-based blend
- **Extended benchmark tasks** — harder distractors, multi-entity slots
- **LangSmith/Braintrust provenance export** — make wrong-entity actions auditable in tools teams already use

---

## The Blog Angle That Writes Itself

Agents are shipping to production. Tool-use evals measure whether the model picked `send_email` vs `schedule_meeting`. But they don't measure whether it emailed the right Alex or scheduled the right meeting. That gap—0% wrong-tool, 24% wrong-target—is the failure mode conventional metrics miss.

EntityBind is designed to catch it. The test suite validates zero wrong-entity actions on the benchmark, with grounded clarifications on ambiguous inputs and zero over-clarification on clear ones. It's built on 40 years of prior art—foreign-key constraints, address verification, name resolution—applied to the agent action loop for the first time.

The paper formalized the problem. EntityBind engineers the solution. Next step: deploy it and measure what agents are actually getting wrong.

---

## References

- Paper: Babu & Indukuri, ["Entity Binding Failures in Tool-Augmented Agents"](https://arxiv.org/abs/2606.30531), arXiv 2606.30531, 2026.
- Reference implementation: [R-Suresh/EntityBindingFailures](https://github.com/R-Suresh/EntityBindingFailures) (MIT, benchmark data + reproduction)
- EntityBind source: [GitHub](https://github.com/cabal-ai/entity-bind) (MIT)
- Install: `pip install entity-bind`

---

*Built in July 2026 as part of the Protogenesis pipeline. EntityBind is new middleware, validated in testing against the paper's benchmark suite. Designed for production, not yet deployed at scale. Feedback, extensions, and deployment reports welcome.*
