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
2. **Consolidate** — Background agent with intelligent scheduling:
   - **Startup consolidation**: Runs at startup if unconsolidated memories exist
   - **Threshold-based**: Triggers when 5+ unconsolidated memories accumulate (configurable)
   - **Daily consolidation**: Forces consolidation every 24 hours if any unconsolidated memories exist (configurable)
   - Batches up to 50 memories per cycle, finds connections, generates insights, marks them as consolidated
3. **Query** — agent reads recent memories + consolidation insights in one LLM call (default: 50 most recent memories). No vector search needed — at ~300 tokens per memory, Haiku's 200K context holds ~650 memories max. We use 50 by default for a safe margin.
4. **File Watcher** (optional) — automatically ingests files dropped in a watch directory, detects modifications via content hashing, and re-ingests changed files.

---

## Database Schema

The system uses a single SQLite file (`memory.db`) with four tables:

### `memories` Table

Stores individual memory records with extracted metadata.

```sql
CREATE TABLE memories (
    id          TEXT PRIMARY KEY,      -- UUID v4
    summary     TEXT NOT NULL,         -- 1-3 sentence distillation
    entities    TEXT NOT NULL DEFAULT '[]',  -- JSON array of extracted entities
    topics      TEXT NOT NULL DEFAULT '[]',  -- JSON array of topics
    importance  REAL NOT NULL DEFAULT 0.5,   -- Float 0.0-1.0
    source      TEXT NOT NULL DEFAULT '',    -- Origin (filename, "notes", etc.)
    timestamp   TEXT NOT NULL,         -- ISO 8601 format
    consolidated INTEGER NOT NULL DEFAULT 0  -- Boolean: 0=unconsolidated, 1=consolidated
);
```

**Field descriptions:**
- **id**: Unique identifier (UUID v4) generated at creation
- **summary**: LLM-extracted 1-3 sentence summary of the content
- **entities**: JSON array of people, places, organizations, concepts (e.g., `["Alice", "Q3 budget", "GPT-4o"]`)
- **topics**: JSON array of broad thematic categories (e.g., `["finance", "AI models", "metacognition"]`)
- **importance**: LLM-assigned significance score from 0.0 (trivial) to 1.0 (critical)
- **source**: Origin identifier (filename for files, custom label for API ingestion)
- **timestamp**: ISO 8601 timestamp with timezone (e.g., `2026-03-27T13:43:11.022223+00:00`)
- **consolidated**: Flag indicating if this memory has been processed by ConsolidateAgent

**Example record:**
```json
{
  "id": "5702a75e-4033-456d-9723-18f3e458f1c0",
  "summary": "Research paper presents causal evidence that LLMs use internal confidence signals to drive abstention behavior.",
  "entities": ["Dharshan Kumaran", "Google DeepMind", "GPT-4o", "confidence signals"],
  "topics": ["artificial intelligence", "metacognition", "confidence estimation"],
  "importance": 0.92,
  "source": "2603.22161v1.pdf",
  "timestamp": "2026-03-27T13:43:11.022223+00:00",
  "consolidated": 0
}
```

### `consolidations` Table

Stores synthesized insights generated by the ConsolidateAgent across batches of memories.

```sql
CREATE TABLE consolidations (
    id          TEXT PRIMARY KEY,      -- UUID v4
    memory_ids  TEXT NOT NULL DEFAULT '[]',  -- JSON array of memory UUIDs
    connections TEXT NOT NULL DEFAULT '',    -- Cross-cutting patterns
    insights    TEXT NOT NULL DEFAULT '',    -- Generated insights/implications
    timestamp   TEXT NOT NULL          -- ISO 8601 format
);
```

**Field descriptions:**
- **id**: Unique identifier for this consolidation
- **memory_ids**: JSON array of memory UUIDs that were consolidated together (e.g., `["abc123", "def456", "ghi789"]`)
- **connections**: LLM-generated description of how the memories relate to each other
- **insights**: LLM-generated deeper understanding, implications, or patterns across the memory batch
- **timestamp**: When the consolidation was created

**Example record:**
```json
{
  "id": "3c765a26-1c36-48a9-b616-b2d75e28cb9e",
  "memory_ids": ["f4584b3b...", "452a33d9...", "5702a75e...", "fe8ccee5...", "4208353a..."],
  "connections": "Memories cluster around two research areas: (1) LLM metacognition with overlapping authorship from Google DeepMind, (2) Claude Haiku 4.5's vision capabilities.",
  "insights": "The research demonstrates biological-AI parallels in confidence-based metacognition. This has AI safety implications: manipulating confidence signals could improve safety, or misaligned calibration could cause unpredictability. The mechanism's consistency across diverse architectures suggests it's a convergent property of large-scale LLMs.",
  "timestamp": "2026-03-27T13:53:13.080358+00:00"
}
```

### `processed_files` Table

Tracks ingested files to prevent duplicate processing and enable change detection.

```sql
CREATE TABLE processed_files (
    path            TEXT PRIMARY KEY,      -- Absolute file path
    last_modified   TEXT NOT NULL,         -- File mtime at ingestion
    last_processed  TEXT NOT NULL,         -- When we processed it
    content_hash    TEXT NOT NULL,         -- SHA256 hash of file contents
    memory_ids      TEXT NOT NULL DEFAULT '[]'  -- JSON array of memory UUIDs created from this file
);
```

**Field descriptions:**
- **path**: Absolute file path (e.g., `/home/user/notes/meeting.md`)
- **last_modified**: Timestamp when file was last modified
- **last_processed**: Timestamp when we last ingested this file
- **content_hash**: SHA256 hash of file contents for change detection
- **memory_ids**: JSON array of memory UUIDs created from this file (used when re-ingesting to delete old memories)

**Example record:**
```json
{
  "path": "/home/user/ObsidianVault/Projects/AI Research.md",
  "last_modified": "2026-03-27T14:30:00.000000+00:00",
  "last_processed": "2026-03-27T14:30:15.123456+00:00",
  "content_hash": "a3f9d8e7c2b1...",
  "memory_ids": ["5702a75e-4033-456d-9723-18f3e458f1c0"]
}
```

### `metadata` Table

Stores system-level metadata and state information.

```sql
CREATE TABLE metadata (
    key   TEXT PRIMARY KEY,      -- Metadata key
    value TEXT NOT NULL          -- Metadata value
);
```

**Field descriptions:**
- **key**: Identifier for the metadata (e.g., `"last_consolidation"`)
- **value**: String value (timestamps stored as ISO 8601)

**Current keys:**
- `last_consolidation`: ISO 8601 timestamp of the most recent consolidation run (used for daily consolidation scheduling)

### How Consolidation Works

The consolidation system uses intelligent scheduling with three trigger modes:

1. **Startup consolidation** (if `ENABLE_STARTUP_CONSOLIDATION=true`):
   - Runs immediately when the server starts
   - Bypasses the memory threshold if any unconsolidated memories exist
   - Ensures fresh consolidations after restarts

2. **Threshold-based consolidation**:
   - Background check every 5 minutes (configurable via `CONSOLIDATION_INTERVAL`)
   - Triggers when ≥5 unconsolidated memories exist (configurable via `MIN_MEMORIES_CONSOLIDATE`)
   - Default behavior for normal operation

3. **Daily forced consolidation** (if `ENABLE_DAILY_CONSOLIDATION=true`):
   - Runs every 24 hours (configurable via `DAILY_CONSOLIDATION_INTERVAL`)
   - Bypasses the memory threshold if any unconsolidated memories exist
   - Tracks last run via `metadata.last_consolidation`
   - Ensures regular consolidation even with low memory accumulation

**Consolidation process:**
1. **Batches memories**: Takes up to 50 unconsolidated memories to avoid context overflow
2. **LLM reasoning**: Asks Claude Haiku to find patterns, connections, and insights across the batch
3. **Stores result**: Creates a consolidation record linking to the source memory IDs
4. **Marks consolidated**: Updates `consolidated=1` on all processed memories
5. **Updates metadata**: Records timestamp in `metadata.last_consolidation`

### How Change Detection Works

When a file is modified and the file watcher detects the change:

1. **Calculate hash**: Compute SHA256 of current file contents
2. **Compare**: Check against stored hash in `processed_files` table
3. **If changed**:
   - Delete old memories (using `memory_ids` from `processed_files`)
   - Delete any consolidations that reference those memories
   - Re-ingest the file to create new memories
   - Update `processed_files` with new hash and memory IDs

This ensures the memory system always reflects the current state of your files without creating duplicates.

### Query Behavior

When you query the system, the `QueryAgent`:
1. Loads the 50 most recent memories (configurable via `max_memories`)
2. Loads all consolidation insights
3. Builds a single prompt with both memories and consolidations
4. Returns synthesized answer with citations (e.g., `[memory:abc123]`, `[consolidation:def456]`)

This allows the system to reason over both raw memories and higher-level insights simultaneously.

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

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure settings

Copy the example environment file and customize it:

```bash
cp .env.example .env
```

Edit `.env` to configure AWS credentials and other settings:

```bash
# AWS Credentials (optional - will use IAM role or default credentials if not set)
AWS_ACCESS_KEY_ID=your_key_here
AWS_SECRET_ACCESS_KEY=your_secret_here
AWS_REGION=us-east-1

# Enable file watcher for automatic ingestion
ENABLE_FILE_WATCHER=true
WATCH_DIR=./inbox

# Other settings (see .env for all options)
```

**Note:** The `.env` file is automatically loaded at startup. All settings have sensible defaults, so you can start with minimal configuration.

### 3. Run the server

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

### 4. Run the demo (optional)

In another terminal:
```bash
./scripts/demo-inbox.sh
```

This will test text ingestion, image upload, and querying.

### 5. Ingest some text

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"text": "Meeting with Alice today. She mentioned the Q3 budget is approved.", "source": "notes"}'
```

### 6. Upload files (images, PDFs)

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

### 9. Index an Obsidian vault (or any note directory)

The file watcher supports **recursive scanning** and **change detection**, making it ideal for indexing note-taking systems like Obsidian:

```bash
# Point to your Obsidian vault
export WATCH_DIR="/path/to/your/ObsidianVault"
export WATCH_RECURSIVE=true              # Scan all subdirectories
export WATCH_TRACK_CHANGES=true          # Re-ingest modified files
export WATCH_IGNORE_DIRS=".obsidian,.git" # Skip metadata directories

# Start the server
./scripts/run-with-watcher.sh
```

**How it works:**
1. **Initial scan**: On startup, recursively scans all files and ingests them
2. **File tracking**: Each file's content hash is stored in the `processed_files` table
3. **Two-tier monitoring**:
   - **Quick scans** (every 1 min by default): Check for new files without hash calculation
   - **Change detection** (every 30 min by default): Calculate hashes and detect modifications
4. **Smart re-ingestion**: When a file changes, the system:
   - Deletes old memories from that file
   - Deletes any consolidations that referenced those memories
   - Re-ingests the new version
   - Updates the tracking record

**Why this is useful:**
- **No file movement**: Your notes stay in place, never moved or deleted
- **Persistent across restarts**: Tracked files won't be re-ingested unless they change
- **Query your knowledge base**: Ask questions like "What did I learn about LLMs this month?"
- **Automatic updates**: Edit a note, save it, and the memory system automatically updates

**Performance considerations:**
- **Quick scans** (default 1 min) only check the database for new files — very fast
- **Change detection** (default 30 min) calculates SHA256 hashes — slower but thorough
- For large vaults (1000+ files), consider:
  - Increasing `WATCH_CHANGE_DETECTION_INTERVAL` to 60+ min for less frequent hash calculations
  - Decreasing `WATCH_POLL_INTERVAL` to 30 sec if you need faster new-file detection
- Hash calculation is done in chunks (8KB), so even large files are handled efficiently

**Ignored directories:**
By default, skips: `.obsidian`, `.git`, `node_modules`, `.venv`, `__pycache__`

Configure custom ignore list via `WATCH_IGNORE_DIRS` (comma-separated).

**Configuration examples for different use cases:**

**Small inbox folder (default):**
```bash
export WATCH_DIR="./inbox"
export WATCH_RECURSIVE=false
export WATCH_POLL_INTERVAL=60           # Check for new files every 1 min
export WATCH_CHANGE_DETECTION_INTERVAL=1800  # Check for changes every 30 min
```

**Medium Obsidian vault (100-500 files):**
```bash
export WATCH_DIR="/path/to/ObsidianVault"
export WATCH_RECURSIVE=true
export WATCH_POLL_INTERVAL=60           # Check for new files every 1 min
export WATCH_CHANGE_DETECTION_INTERVAL=1800  # Check for changes every 30 min
```

**Large vault (1000+ files):**
```bash
export WATCH_DIR="/path/to/large/vault"
export WATCH_RECURSIVE=true
export WATCH_POLL_INTERVAL=120          # Check for new files every 2 min
export WATCH_CHANGE_DETECTION_INTERVAL=3600  # Check for changes hourly
```

**Fast response for active note-taking:**
```bash
export WATCH_DIR="/path/to/active/notes"
export WATCH_RECURSIVE=true
export WATCH_POLL_INTERVAL=30           # Check for new files every 30 sec
export WATCH_CHANGE_DETECTION_INTERVAL=300   # Check for changes every 5 min
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

Returns system status including memory counts, consolidation state, and file tracking information.

```json
{
  "memory_count": 42,
  "consolidation_count": 3,
  "unconsolidated_count": 7,
  "background_consolidation_running": true,
  "last_consolidation": "2026-03-30T17:04:18.529286+00:00",
  "processed_files": {
    "total_count": 3,
    "files": [
      {
        "filename": "meeting-notes.md",
        "path": "/full/path/to/meeting-notes.md",
        "last_modified": "2026-03-30T17:00:46.564217",
        "last_processed": "2026-03-30T17:00:46.564217",
        "content_hash": "ead7083de97650a2...",
        "memory_ids": ["29c70909-35cf-43b8-9442-5fd7212a828c"],
        "memory_count": 1
      }
    ]
  }
}
```

**Response fields:**
- `memory_count`: Total number of memories in the system
- `consolidation_count`: Number of consolidation records created
- `unconsolidated_count`: Memories not yet consolidated
- `background_consolidation_running`: Whether the background consolidation thread is active
- `last_consolidation`: ISO 8601 timestamp of most recent consolidation (if any)
- `processed_files`: File watcher tracking information
  - `total_count`: Number of files tracked
  - `files`: Array of file records with ingestion timestamps, content hashes, and associated memory IDs

### `POST /consolidate`

Manually trigger a consolidation cycle.

---

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `MEMORY_DB_PATH` | `memory.db` | SQLite file path |
| `CONSOLIDATION_INTERVAL` | `300` | Seconds between background consolidation checks (5 min) |
| `MIN_MEMORIES_CONSOLIDATE` | `5` | Minimum unconsolidated memories to trigger consolidation |
| `DAILY_CONSOLIDATION_INTERVAL` | `86400` | Force consolidation after N seconds if unconsolidated memories exist (24 hours) |
| `ENABLE_STARTUP_CONSOLIDATION` | `true` | Run consolidation at startup if unconsolidated memories exist |
| `ENABLE_DAILY_CONSOLIDATION` | `true` | Enable daily forced consolidation regardless of memory count threshold |
| `BEDROCK_MODEL_ID` | `amazon-bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0` | Bedrock model (cross-region inference profile) |
| `AWS_REGION` | `us-east-1` | AWS region |
| `ENABLE_FILE_WATCHER` | `false` | Enable automatic file ingestion from watch directory |
| `WATCH_DIR` | `./inbox` | Directory to watch for new files |
| `WATCH_POLL_INTERVAL` | `60` | Seconds between quick scans for new files (1 min default) |
| `WATCH_CHANGE_DETECTION_INTERVAL` | `1800` | Seconds between full scans with hash calculation for change detection (30 min default) |
| `WATCH_RECURSIVE` | `false` | If true, scan subdirectories recursively |
| `WATCH_TRACK_CHANGES` | `true` | If true, detect and re-ingest modified files using content hash |
| `WATCH_IGNORE_DIRS` | `.obsidian,.git,node_modules,.venv,__pycache__` | Comma-separated list of directory names to ignore |

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
├── integrations/
│   ├── README.md           # Integration guides
│   ├── kiro-cli-skill.md   # Kiro-CLI/Claude Code skill
│   ├── EXAMPLE_USAGE.md    # Example interactions
│   └── test-skill.sh       # Skill test suite
├── scripts/
│   ├── run.sh              # Quick start script
│   ├── run-with-watcher.sh # Start with file watcher enabled
│   └── demo.sh             # Automated demo
├── cli.py                  # CLI interface
├── requirements.txt
├── .env.example            # Configuration template
└── README.md
```

---

## Integrations

### Claude Code Skill

Native skill for Claude Code that provides persistent memory across sessions.

**Installation:**
```bash
cd integrations/claude-code-skill
./install.sh
```

**Features:**
- Automatic activation when you ask to remember something
- Query knowledge from any previous session
- Upload and analyze documents
- Cross-session project continuity
- Proactive memory suggestions

**Usage:**
The skill activates automatically in Claude Code:
```
"Remember that the Q3 budget was approved at $2.4M"
"What do you know about the Q3 budget?"
"Show me memory system status"
```

See [`integrations/claude-code-skill/README.md`](integrations/claude-code-skill/README.md) for complete documentation.

### Kiro-CLI Skill

The memory agent can also be accessed from Kiro-CLI (legacy Claude Code CLI) via explicit commands.

**Installation:**
```bash
cp integrations/kiro-cli-skill/memory.md ~/.config/kiro-cli/skills/memory.md
```

**Usage:**
```bash
/memory ingest "Met with Alice today - Q3 budget approved at $2.4M"
/memory query "What did Alice say about the budget?"
/memory status
```

See [`integrations/kiro-cli-skill/README.md`](integrations/kiro-cli-skill/README.md) for detailed documentation, examples, and comparison with Claude Code skill.

### API Integration

Any tool can integrate with the memory agent via its REST API:

```bash
# Ingest
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"text":"your text here","source":"your-app"}'

# Query
curl "http://localhost:8000/query?q=your+question"

# Status
curl http://localhost:8000/status
```

See [API Reference](#api-reference) for full endpoint documentation.

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
