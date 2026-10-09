# Results

**Status: pending live run.** `results/` holds no live run log; nothing here is
an accuracy number. Everything below is actual output of the offline mechanism
demos (scripted agent, hashing embedder, simulated cache), pasted verbatim, and
labeled "context delivery (mechanism)".

## `memdoc demo crossover` (terminal)

```
MECHANISM DEMO: scripted agent, hashing embedder, simulated cache. Not benchmark results.

context delivery (mechanism): what each memory layer hands the model, not what a model does with it
tokens: estimate (ApproxTokenizer: ceil(utf8_bytes/4))
pricing: research parameters ($3/$15 per M; write 1.25x, read 0.10x)

arm@size  gold-in-ctx%  stale-in-ctx%  stale-first%  mem-tok/call  $/sess cached  $/sess uncached  hit%
a0@100000  0.0  0.0  0.0  0.0  0.2113  0.7686  88.41
a0@25000  0.0  0.0  0.0  0.0  0.2113  0.7686  88.41
a0@5000  0.0  0.0  0.0  0.0  0.2113  0.7686  88.41
a1@100000  95.8  20.8  8.3  86506.4  1.3071  8.6749  96.0
a1@25000  95.8  20.8  8.3  23093.8  0.5058  2.8822  94.63
a1@5000  95.8  20.8  8.3  5454.7  0.2829  1.2709  91.93
a2@100000  85.8  20.8  5.8  8419.5  0.3203  1.5418  92.8
a2@25000  85.8  20.8  5.8  2620.4  0.2470  1.0120  90.65
a2@5000  85.8  20.8  5.8  1009.5  0.2632  0.8649  84.47
a4@100000  77.5  18.3  2.5  86.0  0.2216  0.7974  87.97
a4@25000  82.5  20.0  4.2  90.4  0.2219  0.7987  87.97
a4@5000  83.9  20.8  4.7  97.7  0.2223  0.8005  87.97
a5@100000  95.8  20.8  8.3  43.1  0.2193  0.7766  87.93
a5@25000  95.8  20.8  8.3  43.1  0.2193  0.7766  87.93
a5@5000  95.8  20.8  8.3  43.1  0.2193  0.7766  87.93
a6@100000  95.8  20.8  16.7  17.0  0.2128  0.7701  88.22
a6@25000  95.8  20.8  16.7  17.0  0.2128  0.7701  88.22
a6@5000  95.8  20.8  16.7  17.0  0.2128  0.7701  88.22
astar@100000  95.8  8.3  0.0  13.4  0.2125  0.7698  88.26
astar@25000  95.8  8.3  0.0  13.4  0.2125  0.7698  88.26
astar@5000  95.8  8.3  0.0  13.4  0.2125  0.7698  88.26

analytic break-even (costmodel §5.2): {'short': 4000, 'medium': 6000, 'long': 9000}
empirical crossover (A1 cached $ > A4): {'size': 5000, 'note': "first measured size where A1 cached $/session exceeds A4's"}

cause codes and unknown-unknown breakdowns: --format json
scripted agent; tells you what the memory layer hands the model, not what a model does with it
```

## `memdoc demo crossover --format md`

MECHANISM DEMO: scripted agent, hashing embedder, simulated cache. Not benchmark results.

context delivery (mechanism): what each memory layer hands the model, not what a model does with it
tokens: estimate (ApproxTokenizer: ceil(utf8_bytes/4))
pricing: research parameters ($3/$15 per M; write 1.25x, read 0.10x)

| arm@size | gold-in-ctx% | stale-in-ctx% | stale-first% | mem-tok/call | $/sess cached | $/sess uncached | hit% |
|---|---|---|---|---|---|---|---|
| a0@100000 | 0.0 | 0.0 | 0.0 | 0.0 | 0.2113 | 0.7686 | 88.41 |
| a0@25000 | 0.0 | 0.0 | 0.0 | 0.0 | 0.2113 | 0.7686 | 88.41 |
| a0@5000 | 0.0 | 0.0 | 0.0 | 0.0 | 0.2113 | 0.7686 | 88.41 |
| a1@100000 | 95.8 | 20.8 | 8.3 | 86506.4 | 1.3071 | 8.6749 | 96.0 |
| a1@25000 | 95.8 | 20.8 | 8.3 | 23093.8 | 0.5058 | 2.8822 | 94.63 |
| a1@5000 | 95.8 | 20.8 | 8.3 | 5454.7 | 0.2829 | 1.2709 | 91.93 |
| a2@100000 | 85.8 | 20.8 | 5.8 | 8419.5 | 0.3203 | 1.5418 | 92.8 |
| a2@25000 | 85.8 | 20.8 | 5.8 | 2620.4 | 0.2470 | 1.0120 | 90.65 |
| a2@5000 | 85.8 | 20.8 | 5.8 | 1009.5 | 0.2632 | 0.8649 | 84.47 |
| a4@100000 | 77.5 | 18.3 | 2.5 | 86.0 | 0.2216 | 0.7974 | 87.97 |
| a4@25000 | 82.5 | 20.0 | 4.2 | 90.4 | 0.2219 | 0.7987 | 87.97 |
| a4@5000 | 83.9 | 20.8 | 4.7 | 97.7 | 0.2223 | 0.8005 | 87.97 |
| a5@100000 | 95.8 | 20.8 | 8.3 | 43.1 | 0.2193 | 0.7766 | 87.93 |
| a5@25000 | 95.8 | 20.8 | 8.3 | 43.1 | 0.2193 | 0.7766 | 87.93 |
| a5@5000 | 95.8 | 20.8 | 8.3 | 43.1 | 0.2193 | 0.7766 | 87.93 |
| a6@100000 | 95.8 | 20.8 | 16.7 | 17.0 | 0.2128 | 0.7701 | 88.22 |
| a6@25000 | 95.8 | 20.8 | 16.7 | 17.0 | 0.2128 | 0.7701 | 88.22 |
| a6@5000 | 95.8 | 20.8 | 16.7 | 17.0 | 0.2128 | 0.7701 | 88.22 |
| astar@100000 | 95.8 | 8.3 | 0.0 | 13.4 | 0.2125 | 0.7698 | 88.26 |
| astar@25000 | 95.8 | 8.3 | 0.0 | 13.4 | 0.2125 | 0.7698 | 88.26 |
| astar@5000 | 95.8 | 8.3 | 0.0 | 13.4 | 0.2125 | 0.7698 | 88.26 |

analytic break-even (costmodel §5.2): {'short': 4000, 'medium': 6000, 'long': 9000}
empirical crossover (A1 cached $ > A4): {'size': 5000, 'note': "first measured size where A1 cached $/session exceeds A4's"}

cause codes and unknown-unknown breakdowns: --format json
scripted agent; tells you what the memory layer hands the model, not what a model does with it

## `memdoc demo cache`

```
MECHANISM DEMO: scripted agent, hashing embedder, simulated cache. Not benchmark results.

one session: 150 calls / 15 turns, A1 store 10000 tok, snippets 750 tok

a1_prefix  totals: cacheRead=7,223,520 cacheWrite=87,480 uncached=60,000
           first-10-call cacheWrite curve: 10000 520 520 520 520 520 520 520 520 520
a4_tail    totals: cacheRead=6,611,020 cacheWrite=88,730 uncached=71,250
           first-10-call cacheWrite curve: 0 1270 520 520 520 520 520 520 520 520
a4_head    totals: cacheRead=5,194,800 cacheWrite=616,200 uncached=172,500
           first-10-call cacheWrite curve: 0 520 520 520 520 520 520 520 520 520

head-inject cacheWrite / tail-inject cacheWrite = 6.9x (baseline: A4 tail-inject, same session)
head injection changed each turn re-writes all history behind it; tail injection reads history from cache. Ratio names its baseline: head cacheWrite vs tail cacheWrite.
```

## `memdoc demo costmodel`

```
MECHANISM DEMO: scripted agent, hashing embedder, simulated cache. Not benchmark results.
analytic model from research §5.2 (memory overhead only); research parameters ($3/$15 per M, Sonnet-class list price)

## short (5 calls, 2 turns)
| store S (tokens) | doc full-load (cached) | doc full-load (no cache) | doc catalog+on-demand | RAG tail-inject (+extract) | RAG tail (no extract) | RAG head-inject (cache-busting) |
|---|---|---|---|---|---|---|
| 2,000 | $0.0189 | $0.0390 | $0.0236 | $0.0273 | $0.0063 | $0.0402 |
| 10,000 | $0.0585 | $0.1590 | $0.0286 | $0.0273 | $0.0063 | $0.0402 |
| 25,000 | $0.1328 | $0.3840 | $0.0311 | $0.0273 | $0.0063 | $0.0402 |
| 50,000 | $0.2565 | $0.7590 | $0.0360 | $0.0273 | $0.0063 | $0.0402 |
| 100,000 | $0.5040 | $1.5090 | $0.0459 | $0.0273 | $0.0063 | $0.0402 |

## medium (30 calls, 5 turns)
| store S (tokens) | doc full-load (cached) | doc full-load (no cache) | doc catalog+on-demand | RAG tail-inject (+extract) | RAG tail (no extract) | RAG head-inject (cache-busting) |
|---|---|---|---|---|---|---|
| 2,000 | $0.0339 | $0.1890 | $0.0424 | $0.0804 | $0.0279 | $0.3909 |
| 10,000 | $0.1335 | $0.9090 | $0.0548 | $0.0804 | $0.0279 | $0.3909 |
| 25,000 | $0.3203 | $2.2590 | $0.0611 | $0.0804 | $0.0279 | $0.3909 |
| 50,000 | $0.6315 | $4.5090 | $0.0735 | $0.0804 | $0.0279 | $0.3909 |
| 100,000 | $1.2540 | $9.0090 | $0.0984 | $0.0804 | $0.0279 | $0.3909 |

## long (150 calls, 15 turns)
| store S (tokens) | doc full-load (cached) | doc full-load (no cache) | doc catalog+on-demand | RAG tail-inject (+extract) | RAG tail (no extract) | RAG head-inject (cache-busting) |
|---|---|---|---|---|---|---|
| 2,000 | $0.1059 | $0.9090 | $0.1324 | $0.4368 | $0.2793 | $5.8706 |
| 10,000 | $0.4935 | $4.5090 | $0.1808 | $0.4368 | $0.2793 | $5.8706 |
| 25,000 | $1.2202 | $11.2590 | $0.2051 | $0.4368 | $0.2793 | $5.8706 |
| 50,000 | $2.4315 | $22.5090 | $0.2535 | $0.4368 | $0.2793 | $5.8706 |
| 100,000 | $4.8540 | $45.0090 | $0.3504 | $0.4368 | $0.2793 | $5.8706 |

short (5 calls, 2 turns) breakeven S ≈ 4000
medium (30 calls, 5 turns) breakeven S ≈ 6000
long (150 calls, 15 turns) breakeven S ≈ 9000
```

## `memdoc demo stale`

```
MECHANISM DEMO: scripted agent, hashing embedder, simulated cache. Not benchmark results.

query: What database should the orders service use?
ranking below is from the hashing embedder, not Titan; offline scores are arbitrary w.r.t. semantics and only exercise the code path:

  0.571  Decision: use PostgreSQL for the orders service.
  0.505  Decision reversed: do NOT use PostgreSQL for the orders service; use DynamoDB.
  0.309  Orders service runs on ECS Fargate.
  0.309  The billing service uses DynamoDB streams.
  0.126  PostgreSQL connection pooling notes: use pgbouncer, pool size 20.

--- labeled research spike block ---
research spike, 2026-10-09 (Titan v2, live): 'Decision: use PostgreSQL...' scored 0.680; 'Decision reversed: do NOT use PostgreSQL... use DynamoDB' scored 0.493. The superseded decision outranked its reversal.
```

## Decay host run (filled by MasterControl)

_Placeholder: MasterControl runs
`memdoc decay --repo /root/.openclaw --file workspace/MEMORY.md --until 2026-10-08`
as root after the build and pastes the output here. Expected (research §4.4):
156 commits; survival medians 0.90 / 0.83 / 0.81 / 0.62; 1,973 vs 182 → 10.8×.
If the tool's output differs, the tool's output is used and the difference is
noted here._

## Mechanism observations (reported as-is, not tuned; R1)

- The oracle (A*) shows 95.8% gold-in-context: the remaining 4.2% are
  abstention probes, whose gold is ABSTAIN and which the oracle correctly
  leaves empty (the ContextReader answers ABSTAIN with nothing in context, so
  those probes still pass; A*'s delivery rate is 1.0000 in the mock report).
- A1/A5/A6 deliver the same gold-in-context rate (95.8%) at every size — the
  always-load, hybrid-search, and grep paths all surface the fact lines on this
  scripted tool policy; they differ in what that costs (A1's $/session grows
  ~4.6x from 5K to 100K; A5 and A6 stay flat).
- A2 (catalog) misses unknown-unknown probes mechanically (85.8% delivery):
  when the probe prompt shares no keyword with any read_if, no doc is opened —
  the research §4.1 "can't search for what you don't know" mechanism.
- A4 (similarity) delivery *degrades with store size* (83.9% → 77.5%): at 100K
  the distractor mass crowds the top-5. Its stale-first rate is the lowest of
  the delivering arms because extraction UPDATEs remove superseded values.
- A6 has the highest stale-first rate (16.7%): transcripts keep every
  superseded value, and position in context is the only ordering.
- The empirical A1-vs-A4 cached-cost crossover sits at the smallest measured
  size (5K): A1's cached $/session (0.2829) already exceeds A4's (0.2223)
  there, consistent with the analytic medium-session break-even of 6K
  (the measured 5K cell actually holds ~5.4K store tokens, inside the ±15%
  band; the next measured size is 25K).
