# Memory Agent Bedrock

> **TL;DR:** A persistent memory system for AI agents that works with just SQLite and an API key — no vector databases, no embedding pipelines, no infrastructure to manage.

## Why This Exists

Giving an AI agent persistent memory usually means setting up vector databases, running embedding models, and managing a whole stack of infrastructure just to remember what was said last week. That's a lot of complexity for what should be a simple problem.

## What It Does

This system stores memories as structured records in a plain SQLite file. When you ask a question, it loads recent memories directly into Claude Haiku's massive 200K context window and lets the model reason over them — no vector search needed. A background "consolidation" agent periodically reads through memories and connects the dots, like a brain doing overnight processing.

## Why It Matters

You get persistent, intelligent AI memory with zero infrastructure beyond a database file and a Bedrock API key.

---

> **Based on:** [GoogleCloudPlatform/always-on-memory-agent](https://github.com/GoogleCloudPlatform/generative-ai/tree/main/gemini/agents/always-on-memory-agent) (originally by [Shubhamsaboo](https://github.com/Shubhamsaboo/always-on-memory-agent), MIT License)

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

1. **Ingest** — send text, images, or PDFs. Haiku extracts `summary`, `entities`, `topics`, and `importance` (0-1).
   - **Text**: Direct processing
   - **Images**: Claude Haiku vision analyzes visual content
   - **PDFs**: Text extraction via PyPDF2
2. **Consolidate** — timer fires (default: every 5 min); agent batches up to 50 unconsolidated memories, finds connections, generates insights, marks them as consolidated.
3. **Query** — agent reads recent memories + consolidation insights in one LLM call (default: 50 most recent memories). No vector search needed — at ~300 tokens per memory, Haiku's 200K context holds ~650 memories max. We use 50 by default for a safe margin.

---

## Stack

| Component | Choice | Why |
|-----------|--------|-----|
| LLM | Claude Haiku 4.5 via Bedrock | ~$0.80/M input, 200K context, vision support |
| Storage | SQLite (`memory.db`) | Zero infrastructure |
| API | FastAPI + uvicorn | Standard, fast |
| SDK | boto3 bedrock-runtime | No anthropic SDK needed |
| Multimodal | Images, PDFs, Text | Native vision + PyPDF2 |

---

## Quickstart

### 1. Configure AWS credentials

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1
```

### 2. Run the server

**Option A: Basic API server**
```bash
./scripts/run.sh
```

**Option B: With file watcher (for automatic ingestion)**
```bash
./scripts/run-with-watcher.sh
```

**Option C: Manual setup**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

### 3. Run the demo (optional)

In another terminal:
```bash
./scripts/demo.sh
```

This will test text ingestion, image upload, and querying.

### 4. Ingest some text

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"text": "Meeting with Alice today. She mentioned the Q3 budget is approved.", "source": "notes"}'
```

### 5. Upload files (images, PDFs)

```bash
# Upload an image
curl -X POST http://localhost:8000/ingest/file \
  -F "file=@screenshot.png"

# Upload a PDF
curl -X POST http://localhost:8000/ingest/file \
  -F "file=@document.pdf"
```

### 6. Query your memories

```bash
curl "http://localhost:8000/query?q=What+did+Alice+say+about+the+budget"
```

### 7. Check status

```bash
curl http://localhost:8000/status
```

### 8. Use file watcher for automatic ingestion (optional)

Start server with watcher, then drop files in `./inbox`:

```bash
# Terminal 1: Start with file watcher
./scripts/run-with-watcher.sh

# Terminal 2: Drop files
mkdir -p inbox
cp image.png inbox/      # Auto-ingested!
cp notes.txt inbox/      # Auto-ingested!
cp report.pdf inbox/     # Auto-ingested!
```

Supported file types:
- **Text**: `.txt`, `.md`, `.json`, `.csv`, `.log`, `.yaml`, `.yml`
- **Images**: `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp` (Claude vision)
- **Documents**: `.pdf` (PyPDF2 text extraction)

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

### `POST /ingest/file`

Upload a file (text, image, or PDF) for ingestion.

Request: `multipart/form-data` with file field

Supported file types:
- Text: `.txt`, `.md`, `.json`, `.csv`, `.log`, `.yaml`, `.yml`
- Images: `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp` (uses Claude vision)
- Documents: `.pdf` (text extraction via PyPDF2)

Response: Same as `/ingest`

Example:
```bash
curl -X POST http://localhost:8000/ingest/file \
  -F "file=@screenshot.png"
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
| `ENABLE_FILE_WATCHER` | `false` | Enable automatic file ingestion from watch directory |
| `WATCH_DIR` | `./inbox` | Directory to watch for new files |
| `WATCH_POLL_INTERVAL` | `5` | Seconds between directory scans |

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use mocked boto3 — no real AWS calls needed.

---

## Troubleshooting

### PyPDF2 not installed
```bash
pip install PyPDF2
```

### AWS credentials not configured
```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=us-east-1
```

### Server not responding
Check if it's running:
```bash
curl http://localhost:8000/status
```

### File watcher not detecting files
Ensure environment variable is set:
```bash
export ENABLE_FILE_WATCHER=true
# or use:
./scripts/run-with-watcher.sh
```

### PDF extraction returns empty text
PyPDF2 only works with text-based PDFs. For scanned documents (images), you'd need OCR (e.g., AWS Textract).

---

## Project Structure

```
memory-agent-bedrock/
├── agents/
│   ├── bedrock_client.py   # boto3 bedrock-runtime helper (multimodal)
│   ├── ingest.py           # Ingest Agent: text, images, PDFs
│   ├── consolidate.py      # Consolidation Agent: timer-driven
│   ├── query.py            # Query Agent: synthesize answers
│   ├── orchestrator.py     # Coordinates agents
│   ├── watcher.py          # File watcher for automatic ingestion
│   └── utils.py            # Shared utilities (JSON parsing)
├── memory/
│   ├── store.py            # SQLite CRUD layer
│   ├── schema.py           # DB schema init
│   └── models.py           # Pydantic models
├── api/
│   ├── main.py             # FastAPI app factory
│   └── routes.py           # /ingest, /ingest/file, /query, /status
├── tests/
│   ├── test_store.py
│   ├── test_agents.py
│   └── test_api.py
├── examples/
│   ├── multimodal_demo.py  # Python demo script
│   └── create_test_image.py # Create test images
├── scripts/
│   ├── run.sh              # Quick start script
│   ├── run-with-watcher.sh # Start with file watcher enabled
│   └── demo.sh             # Automated demo
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
