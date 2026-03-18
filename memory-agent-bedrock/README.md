# Memory Agent Bedrock

A persistent memory agent powered by **Claude Haiku 4.5** on AWS Bedrock — with **no vector database**.

Three specialist sub-agents share a SQLite store. The consolidation agent runs periodically like a "sleeping brain," finding connections across memories and generating insights.

> **Blog angle:** *"I Replaced Vector DBs with Google's Memory Agent Pattern — Here's What Happened"*

---

## Architecture

```
                    ┌──────────────┐
                    │ Orchestrator │
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
  ┌──────────────┐  ┌────────────────┐  ┌──────────────┐
  │ Ingest Agent │  │Consolidate     │  │ Query Agent  │
  │              │  │Agent (timer)   │  │              │
  └──────┬───────┘  └───────┬────────┘  └──────┬───────┘
         │                  │                   │
         ▼                  ▼                   ▼
   ┌─────────────────────────────────────────────────┐
   │                memory.db (SQLite)                │
   │                                                  │
   │  memories:  id, summary, entities, topics,       │
   │             importance, source, timestamp,        │
   │             consolidated (bool)                   │
   │                                                  │
   │  consolidations: id, memory_ids, connections,    │
   │                  insights, timestamp              │
   └─────────────────────────────────────────────────┘
```

### How it works

1. **Ingest** — send text, Haiku extracts `summary`, `entities`, `topics`, and `importance` (0-1).
2. **Consolidate** — timer fires (default: every 5 min); agent batches up to 50 unconsolidated memories, finds connections, generates insights, marks them as consolidated.
3. **Query** — agent reads recent memories + consolidation insights in one LLM call (default: 50 most recent memories). No vector search needed — at ~300 tokens per memory, Haiku's 200K context holds ~650 memories max. We use 50 by default for a safe margin.

---

## Stack

| Component | Choice | Why |
|-----------|--------|-----|
| LLM | Claude Haiku 4.5 via Bedrock | ~$0.80/M input, 200K context |
| Storage | SQLite (`memory.db`) | Zero infrastructure |
| API | FastAPI + uvicorn | Standard, fast |
| SDK | boto3 bedrock-runtime | No anthropic SDK needed |

---

## Quickstart

### 1. Set up virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Or use the provided `run.sh` script for one-command setup and launch:

```bash
./run.sh
```

### 2. Configure AWS credentials

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1
```

### 3. Run the API server

```bash
uvicorn api.main:app --reload --port 8000
```

### 4. Ingest some text

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"text": "Meeting with Alice today. She mentioned the Q3 budget is approved.", "source": "notes"}'
```

### 5. Query your memories

```bash
curl "http://localhost:8000/query?q=What+did+Alice+say+about+the+budget"
```

### 6. Check status

```bash
curl http://localhost:8000/status
```

---

## CLI Usage

```bash
# Ingest text
python cli.py ingest "Paris is the capital of France." --source wikipedia

# Query
python cli.py query "What do you know about France?"

# Run consolidation manually
python cli.py consolidate

# Status
python cli.py status

# List memories
python cli.py list --limit 10

# Use a different database
python cli.py --db /path/to/my.db status
```

---

## API Reference

### `POST /ingest`

```json
{
  "text": "string (required)",
  "source": "string (optional)"
}
```

Response:
```json
{
  "id": "uuid",
  "summary": "...",
  "entities": ["Alice", "budget"],
  "topics": ["finance", "meetings"],
  "importance": 0.75,
  "source": "notes"
}
```

### `GET /query?q=<question>`

Response:
```json
{
  "answer": "Alice mentioned the Q3 budget is approved [memory:abc123]. ..."
}
```

### `GET /status`

```json
{
  "memory_count": 42,
  "consolidation_count": 3,
  "unconsolidated_count": 7,
  "background_consolidation_running": true
}
```

### `POST /consolidate`

Manually trigger a consolidation cycle.

---

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `MEMORY_DB_PATH` | `memory.db` | SQLite file path |
| `CONSOLIDATION_INTERVAL` | `300` | Seconds between background consolidations |
| `MIN_MEMORIES_CONSOLIDATE` | `5` | Minimum unconsolidated memories to trigger consolidation |
| `BEDROCK_MODEL_ID` | `amazon-bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0` | Bedrock model (cross-region inference profile) |
| `AWS_REGION` | `us-east-1` | AWS region |

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use mocked boto3 — no real AWS calls needed.

---

## Project Structure

```
memory-agent-bedrock/
├── agents/
│   ├── bedrock_client.py   # boto3 bedrock-runtime helper
│   ├── ingest.py           # Ingest Agent: text → structured memory
│   ├── consolidate.py      # Consolidation Agent: timer-driven
│   ├── query.py            # Query Agent: synthesize answers
│   ├── orchestrator.py     # Coordinates agents
│   └── utils.py            # Shared utilities (JSON parsing)
├── memory/
│   ├── store.py            # SQLite CRUD layer
│   ├── schema.py           # DB schema init
│   └── models.py           # Pydantic models
├── api/
│   ├── main.py             # FastAPI app factory
│   └── routes.py           # /ingest, /query, /status, /consolidate
├── tests/
│   ├── test_store.py
│   ├── test_agents.py
│   └── test_api.py
├── cli.py                  # CLI interface
├── requirements.txt
└── README.md
```

---

## Why No Vector DB?

The key insight: for a personal agent's memory store, the total corpus is **small enough** that you can read recent memories directly. At ~300 tokens per memory (including summary, entities, topics, importance), Haiku's 200K context window holds ~650 memories max. We default to 50 memories per query for fast response times and cost efficiency.

This approach is:
- **Simpler** — no embedding pipeline, no vector DB infrastructure
- **Cheaper** — no embedding API calls
- **More accurate** — LLM reasons over semantics, not cosine similarity
- **Scalable** — for 1,000+ memories, consolidation insights provide a compressed "memory index"

The ceiling is ~500-650 memories in a single query before hitting context limits, but the consolidation agent helps scale beyond that by generating insights across batches.

---

*Inspired by [Google's Always-On Memory Agent](https://github.com/GoogleCloudPlatform/generative-ai/tree/main/gemini/agents/always-on-memory-agent). Adapted for AWS Bedrock + Claude Haiku 4.5.*
