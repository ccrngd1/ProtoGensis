# xMemory — Beyond RAG for Agent Memory

> **TL;DR:** xMemory fixes the "five versions of the same message" problem in AI agent memory retrieval by organizing conversation history into a semantic hierarchy and querying it top-down instead of with flat similarity search.

## Why This Exists

Standard memory retrieval for AI agents suffers from redundancy collapse: because conversation turns are closely related to each other, a similarity search returns near-duplicate results that eat up the context window without adding new information. You ask about a decision and get five messages that all say the same thing slightly differently.

## What It Does

xMemory organizes conversation history into four levels — raw messages, episode summaries, distilled facts, and topic clusters — built bottom-up by a lightweight model. When you query, it starts at the top (broad topic clusters) and drills down only as far as needed, explicitly selecting for *diversity* at each level. Simple queries get a concise answer; complex ones get enough detail without redundant padding.

## Why It Matters

Agent memory retrieval that actually returns diverse, useful context — instead of burning your token budget on variations of the same message.

---

**Reference:** [arXiv:2602.02007](https://arxiv.org/abs/2602.02007) — *"Beyond RAG for Agent Memory: Retrieval by Decoupling and Aggregation"* (ICML 2026)

---

## The Problem with Standard RAG for Agent Memory

Standard RAG is designed for **large, diverse, heterogeneous corpora** — the kind of corpus where retrieved passages are independent and non-redundant. Agent memory is the opposite: a **bounded, coherent conversation stream** where consecutive messages are highly correlated.

Under standard top-k retrieval over agent memory:
- Returned chunks are near-duplicates (redundancy collapse)
- Token budget fills up with repeated context
- Multi-fact queries return a single semantic neighborhood
- Post-hoc pruning breaks temporal evidence chains

xMemory solves this by organizing memories into a **4-level hierarchy** and retrieving top-down.

---

## Architecture

```
Raw Messages → Episodes → Semantic Nodes → Themes
     ↑              ↑             ↑            ↑
  individual    block         reusable      topic
  turns         summaries     facts         clusters
```

**Retrieval (top-down):**
```
Query → Theme Matching → Semantic Selection → Uncertainty-Gated Expansion
           (Sonnet)          (Sonnet)              (optional: episodes/messages)
```

**Construction (bottom-up):**
```
Messages → Episode Summaries → Fact Extraction → Theme Clustering
              (Haiku)               (Haiku)           (Haiku)
```

---

## Stack

| Component | Technology |
|-----------|-----------|
| LLM (construction) | Claude Haiku 4.5 via AWS Bedrock |
| LLM (retrieval) | Claude Sonnet 4.6 via AWS Bedrock |
| Storage | SQLite (4-level relational hierarchy) |
| Python | 3.11+ |
| Dependencies | boto3, pydantic |

No vector database required. All matching is LLM-based.

---

## Project Structure

```
xmemory/
├── __init__.py       # Public API
├── models.py         # Pydantic models: Message, Episode, SemanticNode, Theme, RetrievalResult
├── schema.py         # SQLite schema initialization
├── store.py          # CRUD for all hierarchy levels
├── episodes.py       # Episode construction (Haiku summarization)
├── semantics.py      # Semantic extraction + deduplication (Haiku)
├── themes.py         # Theme clustering (Haiku)
├── retrieval.py      # Top-down retrieval (Sonnet reranking)
├── updater.py        # Incremental hierarchy updates
└── _llm.py           # boto3 Bedrock client wrapper

benchmarks/
├── data.py           # Synthetic conversation generator (100+ messages)
├── runner.py         # xMemory vs flat top-k comparison
└── report.py         # Results table printer

tests/
├── test_schema.py
├── test_episodes.py
├── test_semantics.py
├── test_themes.py
├── test_retrieval.py
└── test_updater.py
```

---

## Quick Start

### Install

**Recommended: Use a virtual environment**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Quick setup and benchmark:** Use the provided `run.sh` script:
```bash
./run.sh
```
This creates a virtual environment, installs dependencies, and runs the benchmark.

### Ingest and Build Hierarchy

```python
from xmemory import init_db, MemoryStore, MemoryUpdater, Message
from datetime import datetime, timezone

# Initialize
conn = init_db("memory.db")
store = MemoryStore(conn)

# Add messages
messages = [
    Message(session_id="session_1", content="We decided to use PostgreSQL.",
            timestamp=datetime.now(timezone.utc)),
    Message(session_id="session_1", content="JWT will handle authentication.",
            timestamp=datetime.now(timezone.utc)),
    # ... add 50+ messages
]
for msg in messages:
    store.add_message(msg)

# Build hierarchy (Haiku constructs episodes → semantics → themes)
updater = MemoryUpdater(store)
result = updater.run()
print(result.summary)
# Update complete: 5 new episode(s), 23 new semantic node(s), 4 theme(s) updated.
```

### Retrieve Context

```python
from xmemory import MemoryRetriever

retriever = MemoryRetriever(store)
result = retriever.retrieve("What decisions were made about the database?")

print(result.retrieval_level)  # "semantic" or "episode" etc.
print(result.to_context_string())
print(f"Token estimate: {result.token_estimate()}")
```

### Incremental Updates

```python
# Add new messages after initial hierarchy is built
for msg in new_messages:
    store.add_message(msg)

# Only processes new messages — existing hierarchy untouched
result = updater.run()
```

---

## SQLite Schema

```sql
messages     (id, session_id, content, timestamp, episode_id)
episodes     (id, session_id, summary, message_ids JSON, created_at)
semantics    (id, fact, source_episode_ids JSON, created_at)
themes       (id, label, semantic_ids JSON, created_at)
retrieval_log(id, query, retrieved_ids JSON, level, timestamp)
```

---

## Running Tests

```bash
# All tests (mocked boto3 — no AWS calls required)
pytest tests/ -v

# With coverage
pytest tests/ --cov=xmemory --cov-report=term-missing
```

---

## Running Benchmarks

```bash
# Compare xMemory vs flat top-k on 7 synthetic sessions (~112 messages)
# Requires real AWS credentials for actual LLM calls
python -m benchmarks.runner --sessions 7 --db /tmp/xmemory_bench.db
```

Example output:
```
----------------------------------------------------------------------------------------------------
xMemory vs Flat Top-k Retrieval — Benchmark Results
----------------------------------------------------------------------------------------------------
Query                                                xMem Tok Flat Tok  Reduction Level
----------------------------------------------------------------------------------------------------
What decisions were made about the database?              312      890      64.9% semantic
What is the authentication approach?                      280      890      68.5% semantic
What are the performance problems and fixes?              198      890      77.8% semantic
...
----------------------------------------------------------------------------------------------------
AVERAGE                                                   287      890      67.8%
✅ Token reduction goal (≥40%): MET (actual: 67.8%)
```

**Important Benchmark Caveat:**
The "flat top-k" baseline in this benchmark uses **recency-based ordering** (`ORDER BY timestamp DESC LIMIT k`) rather than semantic similarity. This represents a weak baseline and makes the token reduction percentage less meaningful. Real-world RAG systems use embedding-based semantic retrieval, not simple recency ordering.

The benchmark demonstrates that xMemory achieves significant token reduction compared to a recency baseline, but comparison against a **semantic similarity baseline** would be needed to fully validate the approach for production use.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM for construction | Haiku | Mechanical tasks (summarize, extract, cluster) — cost efficiency |
| LLM for retrieval | Sonnet | Needs reasoning to judge relevance and diversity |
| Storage | SQLite | 4-level hierarchy fits relational cleanly; no Neo4j complexity |
| Updates | Incremental | Full rebuild on each new message is a non-starter |
| Semantic selection | LLM reranking | Simpler than submodular optimization, sufficient for v1 |
| Episode boundaries | session_id | Natural conversation breaks |
| Theme clustering | Haiku batched | Simple topic grouping over semantics — no formal sparsity objective |

---

## How Retrieval Works

**Stage 1 — Theme Matching (Sonnet):**
Sonnet ranks all themes by relevance to the query. Returns top-k themes with a confidence score.

**Stage 2 — Semantic Selection (Sonnet):**
Within matched themes, Sonnet selects a diverse, relevant subset of facts. Explicitly penalises redundancy.

**Stage 3 — Uncertainty-Gated Expansion (optional):**
If Sonnet's confidence in the semantic context is below threshold (default: 0.4), expansion triggers:
- First expand to episode summaries (adds narrative context)
- If still insufficient, expand to raw messages

This prevents over-expansion for simple queries while ensuring complex multi-hop queries get enough detail.

---

## Accepting Criteria Status

| Criterion | Status |
|-----------|--------|
| 50+ messages → episodes → deduplicated semantics → themes | ✅ |
| Top-down retrieval returns diverse context | ✅ |
| ≥40% fewer tokens than naive top-k | ✅ (benchmark target) |
| Incremental update without full rebuild | ✅ |
| Tests with mocked boto3 | ✅ |

---

*Built as part of Protogenesis Week 10. Blog: "I Upgraded My AI Agent's Memory Beyond RAG — Here's the Difference"*
