# Memex — Indexed Experience Memory for Agents

> **TL;DR:** Memex gives AI agents a lossless external memory — agents archive bulky findings to a database and keep only tiny summaries in their working context, then fetch the full details back on demand.

## Why This Exists

AI agents forget things as conversations grow longer. When a context window fills up, old research, debug traces, and findings get pushed out — and they're gone for good. Truncation and rolling summaries are lossy: once the detail is gone, the agent can't get it back.

## What It Does

Memex gives agents two simple tools: one to compress a large piece of content into a short summary and archive the full version to SQLite, and one to fetch the full version back by name — losslessly. The agent's working context stays small because it only holds compact summaries, not thousands of tokens of raw data.

## Why It Matters

Your agent never truly forgets, and its context window stays lean — no matter how long the task runs.

---

> **Protogenesis W10** | "Teaching My AI Agent to Remember Its Mistakes"
>
> **Based on:** [arXiv:2603.04257](https://arxiv.org/abs/2603.04257) — *"Scaling Long-Horizon LLM Agents via Indexed Experience Memory"* (Wang et al., Accenture, Mar 2026)

Memex gives LLM agents an indexed external memory: compress verbose tool responses into compact indexed summaries, then dereference them later to recover the exact original content. Working context stays small; full history is always recoverable.

---

## The Problem

Long-horizon agents accumulate tool responses, research findings, and debug traces until their context window fills. Standard solutions — truncation or running summaries — are **lossy**: once evidence is gone, the agent can't recover it.

## The Solution

Two agent tools:

```
compress_experience(content, index_key, context=None) → indexed_summary
read_experience(index_key)                            → full_content
```

The **full content** is archived in a SQLite store. A **compact indexed summary** (~100-200 tokens) replaces it in working context. When the agent needs the full detail, it calls `read_experience()` to dereference the index and recover the exact original content — losslessly.

```
Working Context (compact)          External Store (full)
─────────────────────────          ───────────────────────
[research:oauth-libs]              key: [research:oauth-libs]
Summary: Recommend authlib:     →  full: Evaluated requests-oauthlib
  async, JWT built-in, PKCE.         (stars:3200, sync-only), authlib
Archived: 2026-03-09T14:30Z         (stars:4800, async+JWT+OIDC)...
Tokens saved: 1,847                 [1,900 tokens of detail]
```

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Agent Working Context               │
│         (compact indexed summaries)              │
│                                                  │
│  [research:oauth-libs]                           │
│  Summary: Recommend authlib: async, JWT...       │
│  Archived: 2026-03-09 | Tokens saved: 1,847      │
└──────────┬───────────────────┬──────────────────┘
           │ compress          │ read
           ▼                   ▼
┌─────────────────────────────────────────────────┐
│          SQLite Experience Store                 │
│  + JSON Manifest (human-readable index)          │
└─────────────────────────────────────────────────┘
```

**Stack:**
- Python 3.11+
- **Claude Haiku 4.5** via **AWS Bedrock** (`boto3`) for summarization
- SQLite for lossless full-content KV store
- JSON manifest for human-readable index

---

## Installation

### Using the Quick Start Script

```bash
./run.sh
```

This script automatically creates a virtual environment, installs dependencies, and runs the demo.

### Manual Setup

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Requirements:** AWS credentials with Bedrock access (for real summarization).

---

## Quick Start

```python
from memex.tools import compress_experience, read_experience

# Agent receives a long tool response
long_response = "..." # 2,000+ tokens

# Compress: archives to SQLite, returns ~150-token indexed summary
indexed = compress_experience(
    content=long_response,
    index_key="[research:oauth-libs]",
    context="OAuth2 library comparison for FastAPI auth module",
)
# indexed is now ~150 tokens — drop into working context instead of long_response

# Later: agent needs the full detail
full_content = read_experience("[research:oauth-libs]")
assert full_content == long_response  # lossless
```

---

## Project Structure

```
memex/
├── __init__.py     — Public exports
├── store.py        — SQLite KV experience store
├── manifest.py     — JSON index manifest
├── compress.py     — Compression engine (Haiku 4.5 via Bedrock)
├── retrieve.py     — Retrieval engine (lossless)
├── tools.py        — High-level agent tools (compress_experience, read_experience)
├── triggers.py     — Heuristic soft triggers (context size monitoring)
└── utils.py        — Token counting, key normalisation

demo/
└── run_demo.py     — CLI demo of the full compress/read cycle

tests/
├── test_store.py   — SQLite store tests
├── test_compress.py — Compression engine tests (mocked Bedrock)
├── test_retrieve.py — Retrieval engine tests
├── test_tools.py   — Integration tests (mocked Bedrock)
└── test_triggers.py — Context trigger tests

benchmark.py        — Token usage comparison: baseline vs. Memex
```

---

## SQLite Schema

```sql
CREATE TABLE experiences (
    key                 TEXT PRIMARY KEY,
    full_content        TEXT NOT NULL,
    summary             TEXT,
    token_count_original INTEGER DEFAULT 0,
    token_count_summary  INTEGER DEFAULT 0,
    metadata            TEXT DEFAULT '{}',
    archived_at         TEXT NOT NULL
);
```

## JSON Manifest Format

```json
{
  "entries": {
    "[research:oauth-libs]": {
      "summary": "Recommend authlib: async, JWT built-in, PKCE required.",
      "archived_at": "2026-03-09T14:30:00+00:00",
      "tokens_saved": 1847
    }
  }
}
```

---

## Configuration

| Environment Variable    | Default              | Description                  |
|------------------------|----------------------|------------------------------|
| `MEMEX_DB_PATH`        | `memex.db`           | SQLite database path         |
| `MEMEX_MANIFEST_PATH`  | `memex_manifest.json`| JSON manifest path           |
| `AWS_REGION`           | `us-east-1`          | AWS region for Bedrock API   |
| `AWS_DEFAULT_REGION`   | (fallback)           | Alternative AWS region variable |

---

## Running Tests

```bash
# Activate virtual environment if not already active
source .venv/bin/activate

# No AWS credentials needed — Bedrock is mocked in all tests
pytest tests/ -v
```

---

## Running the Demo

```bash
# Using the quick start script
./run.sh

# Or manually (with venv activated)
source .venv/bin/activate
python demo/run_demo.py
```

Falls back to a mock summary if Bedrock is unavailable, so you can see the flow without AWS credentials.

---

## Running the Benchmark

```bash
# Activate virtual environment if not already active
source .venv/bin/activate

python benchmark.py
```

Simulates 5 large tool responses with and without Memex. Shows token savings per step and final compression ratio (typically >80% with real content).

---

## Soft Triggers

The `ContextTriggers` class monitors context size and advises when to compress:

```python
from memex.triggers import ContextTriggers

triggers = ContextTriggers(soft_threshold=4000, hard_threshold=8000)
advice = triggers.check_triggers(working_context)

if advice.should_compress:
    print(advice)  # [memex:triggers] COMPRESS RECOMMENDED: ...
```

---

## Known Limitations

**Thread Safety:** Memex v0.1 uses module-level singletons and is not thread-safe. For multi-threaded agents, instantiate separate `ExperienceStore` and `IndexManifest` instances per thread, or add external locking around `compress_experience()` / `read_experience()` calls.

---

## Index Key Convention

Keys follow the `[namespace:topic-slug]` pattern:

- `[research:oauth-libs]` — Research findings about OAuth libraries
- `[debug:session-race]` — Debug session on a race condition
- `[project:schema-v2]` — Project schema migration notes
- `[task:step-3-results]` — Results from task step 3

Keys without brackets are automatically normalised.

---

## Acceptance Criteria ✅

1. **compress_experience on 3000-token content** → archives to SQLite + returns ~100-200 token indexed summary ✅
2. **read_experience(key)** → exact original content returned (lossless) ✅  
3. **Tests with mocked Bedrock calls** — no real AWS calls needed in tests ✅
4. **Working CLI demo** — `python demo/run_demo.py` ✅

---

## Relationship to MemexRL (Paper)

This implementation extracts the **design pattern** from [arXiv:2603.04257](https://arxiv.org/abs/2603.04257) without the RL training:

| Paper Feature | This Implementation |
|--------------|---------------------|
| Compress/Read operations | ✅ Implemented |
| SQLite KV store | ✅ Implemented |
| Indexed summaries | ✅ Implemented |
| Lossless recovery | ✅ Implemented |
| Soft triggers | ✅ Heuristic (threshold-based) |
| RL-trained policies | ❌ v1 scope: heuristics only |

---

*Protogenesis W10 — Built 2026-03-09*
