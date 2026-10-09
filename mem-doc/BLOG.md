# I Thought My Agent Ran on Documentation. It Runs on Both. Here's the Benchmark.

*MemDoc: a preregistered harness where the agent writes its own memory — doc-driven,
RAG, and hybrid, compared along write policy, read policy, and store size.*

## 1. The reveal

I'd have told you my agent system was doc-driven: AGENTS.md, MEMORY.md, persona files,
all curated by the working agent. Then I ran `openclaw memory status`: **12,778**
<!-- cite:openclaw-memory-status-2026-10-09 --> vector chunks indexed behind those docs,
hybrid BM25 + vector search, and a background "dreamer" that writes into the always-loaded
memory file. The system I would have described as documentation-driven runs both layers,
and has for months.

That matters because of Kevin Liao's October post, "Agents Don't Need Memory. They Need
Documentation." His argument, stated fairly: snippet-RAG memory fails in five ways —
similarity isn't correctness or currency, snippets lose context, the past gets treated as
truth, agents can't search for what they don't know exists, and the store can't be audited.
His alternative is a structured Markdown brain the agent consults before work and updates
after, with a lean catalog for discovery, freshness written by the working agent (not a
background dreamer), and discipline against bloat. The Hacker News thread
(384 points, roughly 310 comments as of 2026-10-09 <!-- cite:hn-49945933 -->) asked, over
and over, for evals. In his own repo's issue #48, Liao said existing memory benchmarks
can't test a system where the agent does work and then commits knowledge — and that he
couldn't afford to run long-horizon benchmarks himself.

So we built the harness for the benchmark he described. It's called **MemDoc**.

## 2. "Docs vs RAG" is the wrong axis

The best critique of Liao's post came from calvinx (the Astrocyte maintainer):
*"documentation is memory with a different write policy"* — a foreground end-of-task write
does the same job as a background extraction pass, just at a different time — and *"past a
certain size, reading the index is retrieval again."* Both points dissolve the binary.
What actually varies is:

- **Who writes memory, and when:** the working agent at session end (foreground), an
  extraction model per turn (background), or nobody (raw transcripts).
- **How it is read:** always-loaded, catalog plus on-demand reads, similarity top-k, or
  agent-driven search.
- **How big the store has grown:** the axis where answers flip.

MemDoc's arms cover the grid:

| id | name | write policy | read policy | inject |
|---|---|---|---|---|
| a0 | none | none | none | none |
| astar | oracle | n/a | oracle | prefix |
| a1 | doc_full | foreground | always_load | prefix |
| a2 | doc_catalog | foreground | catalog | prefix |
| a3 | rag_naive (weak baseline) | background | similarity | tail |
| a4 | rag_extract | background | similarity | tail |
| a5 | hybrid_tiered | foreground | hybrid_search | prefix |
| a5bg | hybrid_tiered_bg | background | hybrid_search | prefix |
| a6 | transcript_grep | none | agent_search | none |

A4 — the RAG baseline that counts — is Mem0-style extraction with ADD/UPDATE/DELETE
supersession plus a search tool, because that is the pattern Liao actually criticises. A3
(raw chunks, top-5, no tool) ships only as a labeled weak baseline. A2 adapts Operator
Memory's published guidance and catalog format verbatim, with BSD-3 attribution and the
upstream commit pinned, so "you wrote a bad doc prompt" is off the table. A6 is the HN
crowd's favorite: just grep your transcripts. And A5 is the honest model of what my own
system turned out to be: a budgeted, foreground-written core that always loads, plus an
episodic tier reached by hybrid search.

## 3. The cost term everyone misses

In an agent loop, the whole context is re-sent on **every model call** — every tool
iteration, not every user turn. Memory overhead is roughly memory-tokens-in-context times
number of calls, and prompt caching changes that by about an order of magnitude (Bedrock
Anthropic pricing: 5-minute cache writes bill at 1.25×, reads at 0.10×
<!-- cite:bedrock-prompt-caching-docs -->). The consequence nobody prices in: **where
memory is injected decides the cache hit rate.**

MemDoc models this with a deterministic cache simulator and reproduces the research cost
model exactly (`memdoc demo costmodel`). On the model's parameters ($3/$15 per million
tokens, Sonnet-class list price), always-loading the whole doc store stops being cheap at
**4,000 <!-- claim:breakeven-short --> / 6,000 <!-- claim:breakeven-medium --> / 9,000
<!-- claim:breakeven-long -->** store tokens for short / medium / long sessions — past
that, extraction RAG's per-turn floor is cheaper than re-reading the store every call,
even with caching.

Injection position is more dramatic. In a simulated 150-call session (`memdoc demo
cache`), snippets injected at the *head* of context and changed each turn re-write all
history behind them: **6.9× <!-- claim:cache-head-ratio --> the cacheWrite tokens of
tail-injection** (baseline: the same A4 arm with snippets appended at the tail, simulated
cache). Several memory plugins "attach to every prompt" exactly this way.

And a self-finding: my own system's always-loaded bootstrap is roughly 18–19K tokens
<!-- cite:research-5.3-cabal-bootstrap -->, which puts it past every one of those
break-evens. The system that prompted this benchmark should probably move toward
catalog-style or budgeted-core loading. That's the kind of concrete answer the cost model
alone already gives.

## 4. Why "similar" isn't "current"

The research spike behind this project embedded a tiny decision store with Titan v2 and
asked, "What database should the orders service use?" The superseded decision — *use
PostgreSQL* — scored 0.680; its own reversal — *do NOT use PostgreSQL; use DynamoDB* —
scored 0.493 <!-- cite:research-4.1-titan-spike -->. Top-1 retrieval serves the stale
fact. `memdoc demo stale` ships that store: offline it ranks with a hashing embedder
(labeled, arbitrary semantics — and amusingly, it also puts the stale decision first);
with `--live bedrock` it re-runs the Titan ranking. The benchmark's category-3 and
category-4 storylines turn this one example into a measured stale-answer rate per arm.

## 5. Eight months of documentation decay, measured

Liao's critics said doc stores rot. They're right — and now there's a number. `memdoc
decay` replays the git history of a memory file and computes exact-line survival. On my
production system's MEMORY.md (156 commits <!-- claim:decay-commits --> over eight
months): median 90-day line survival 0.62 <!-- claim:decay-90d -->, 1,973 distinct lines
ever against 182 current <!-- claim:decay-lines --> — a 10.8× <!-- claim:decay-churn -->
churn ratio, with a sawtooth size curve (steady growth, one manual consolidation). Plainly:
**about 4 in 10 lines of curated memory are rewritten or removed within 90 days.** Be
careful with the reading, though — exact-line survival measures *churn*, not wrong facts.
A rewritten status line counts as a removal. The honest interpretations run both ways:
either freshness maintenance is working, or this is how fast truth moves. Either way, a
write-once store with no supersession would still be serving those superseded lines.

## 6. The hybrid failure nobody talks about

The sharpest thing the research turned up is a failure of our own system. A background
consolidation pass ("dreaming") promoted a batch of context-free, dated fragments —
queue-status snapshots, "no new surfacing" notes — into the always-loaded memory file.
They carried `recalls=0`: nothing had ever retrieved them. The configured promotion gate
says `minRecallCount=2`. Whether that's a bug or a misread of the config is an open
question we've flagged, not a settled verdict. But the mechanism is exactly what Liao
warns about: a background writer feeding an always-loaded doc gets the worst of both
worlds — unaudited fragments, treated as truth, re-sent on every call. That failure is why
MemDoc has H7: hold the read policy constant and vary only who writes the core.

## 7. Results

**Status: pending live run.** No accuracy numbers exist, and none appear here: the offline demo
uses a scripted agent, a hashing embedder, and a simulated cache, and every offline
surface prints `MECHANISM DEMO: scripted agent, hashing embedder, simulated cache. Not
benchmark results.` Mock output tells you what each memory layer *hands* the model — gold
or stale values in context, at what cost — not what a model does with it. Real-LLM
behavior: not benchmarked.

What is locked, before any run, are the hypotheses (hash in `PREREG.lock`; `memdoc run`
refuses to start if it doesn't verify):

- **H1 (size crossover):** A1 ≥ A4 at 5K; A1 < A2 ≈ A5 at 100K; A1's cost crosses A4's
  between 4K and 9K tokens. Would mean: always-load is a small-store strategy.
- **H2 (rationale):** doc arms beat extraction RAG by ≥10 points on decision-continuity
  and procedural-lesson categories. Would mean: fragments lose the *why*.
- **H3 (supersession):** stale answers highest for naive RAG and transcript grep, lower
  with extraction supersession, lowest for docs if write fidelity holds. Would mean:
  rewrite-in-place is the point of docs.
- **H4 (implicit conflict):** no arm clears 60% when the world changes without an explicit
  correction. Would mean: this is everyone's open problem.
- **H5 (hybrid):** the tiered arm has the best overall success at ≤1.5× catalog cost.
  Would mean: the production convergence is defensible.
- **H6 (silent failure):** RAG failures are ≥2× more often invisible from the store alone.
  Would mean: auditability is measurable, not definitional.
- **H7 (write policy):** foreground-written cores beat background-written ones at equal
  read policy. Would mean: the dreaming incident generalizes.

Each gets a verdict — SUPPORTED, NOT_SUPPORTED, or NOT_TESTED — after a live run, with
McNemar on paired cells, seeded bootstrap CIs, and Holm correction across all seven.

## 8. The decision tree (the hypothesis under test)

Until live data exists, this is the claim the cost model and mechanism demos support,
stated as a hypothesis, not a result: keep memory under ~5K tokens of facts the
environment can't reveal and always-load it; past ~10K, switch to a catalog with read-when
conditions; with a large episodic history or many unknown-unknowns, add a searchable
episodic tier; and never let a background writer feed an always-loaded doc without a gate
you trust.

## 9. The reference workspace

`memdoc reference init <dir>` writes the template we'd actually deploy: a budgeted
always-loaded core (AGENTS/SOUL/USER/MEMORY-style, synthetic), a one-level `catalog.md`
whose entries carry `read_if` conditions, and a `notes/` episodic tier meant for indexing.
`memdoc reference check` lints the budget, the catalog conditions, and the one-level rule
(a second routing level never helped in the progressive-disclosure study
<!-- cite:2607.17598 -->).

> **Irony sidebar.** The planning brief for this very benchmark contained three stale
> facts: it said the blog should be ready for WikiJS (retired to read-only on Oct 5), it
> quoted the HN thread at 91 points (it was 384 <!-- cite:hn-49945933 -->), and it
> described the reference system as "documentation-driven, no RAG" (12,778
> <!-- cite:openclaw-memory-status-2026-10-09 --> indexed chunks say otherwise).
> Documentation decays even when the topic is documentation decay.

## 10. Limits

Storylines are synthetic and CABAL-shaped; no production data ships. One provider
(Bedrock), one or two model tiers, pinned IDs and dates — results may age as models get
better at knowledge updates. Offline demos use a scripted agent, a hashing embedder, and a
simulated cache: mechanism only, and offline similarity rankings are arbitrary with
respect to semantics. Cache-simulator fidelity is checked against live usage fields only
on the runs we make, and the usage fields win. The decay data comes from one production
system and measures churn, not correctness. A4 is Mem0-*style*, not Mem0; A2 uses
Operator's guidance but not the real Operator harness (that arm is deferred). And the
expected outcome is a crossover with conditions, not a verdict for either side.

---

*MemDoc lives in the ProtoGensis monorepo (`ccrngd1/ProtoGensis`, `mem-doc/`), MIT, with
Operator Memory's guidance adapted under BSD-3. Related internal threads: state-management,
guidance-as-architecture (the context-files null result <!-- cite:2602.11988 -->),
memory-dreaming, and MemoryGuard (W28) — the same write path this benchmark measures is
also a security boundary. The earlier memory-systems survey (Temple, research page
"memory-systems-survey", March 2026) recommended "keep file-based, add semantic
retrieval"; MemDoc is the test of whether that was right.*

*Ready for Temple publish.*
