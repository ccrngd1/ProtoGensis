# Comparison: memory-agent-bedrock vs Google Cloud always-on-memory-agent

## Overview

Both implementations follow the same core architecture pattern: a persistent memory system with three specialist agents (Ingest, Consolidate, Query) that share a SQLite database. The key difference is **Google's uses Gemini + ADK** while **this uses Claude + Bedrock**.

> **Update (2026-03-24):** The Bedrock version now has multimodal support (images, PDFs) and file watcher capabilities, achieving feature parity with Google's version for the most common use cases.

---

## Architecture Comparison

### Core Pattern (Shared)
```
┌──────────────┐
│ Orchestrator │
└──────┬───────┘
       │
  ┌────┼────┐
  ▼    ▼    ▼
Ingest Consolidate Query
  │    │    │
  └────┴────┘
     SQLite
```

Both implementations:
- Store memories as structured records (summary, entities, topics, importance)
- Use consolidation agent to find connections and generate insights
- Query by loading recent memories into LLM context (no vector search)
- Rely on large context windows (200K+) to avoid embedding pipelines

---

## Recent Updates (2026-03-24)

The Bedrock version has been enhanced with multimodal capabilities, achieving near feature parity with Google's version:

**✅ What's New:**
1. **Image Processing** - Claude Haiku 4.5 vision integration
   - Supports: `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`
   - Base64 encoding with multimodal API calls
   - Extracts entities, topics, and descriptions from visual content

2. **PDF Support** - PyPDF2 text extraction
   - Processes first 20 pages
   - Extracts text for structured memory creation
   - Works with text-based PDFs (not scanned documents)

3. **File Watcher** - Automatic ingestion
   - Background thread monitors `./inbox` directory
   - Configurable via `ENABLE_FILE_WATCHER`, `WATCH_DIR`, `WATCH_POLL_INTERVAL`
   - Processes new files within seconds

4. **File Upload API** - `POST /ingest/file`
   - Upload images, PDFs, or text files via HTTP
   - Multipart form data support
   - Returns structured memory records

**Implementation:**
- ~300 lines of new code across 8 files
- Added `agents/watcher.py` for file monitoring
- Enhanced `agents/bedrock_client.py` with `invoke_multimodal()`
- Extended `agents/ingest.py` with `ingest_file()`, `_ingest_image()`, `_ingest_pdf()`
- New dependencies: `PyPDF2`, `python-multipart`

---

## Key Differences

| Aspect | Google Cloud (original) | memory-agent-bedrock (this repo) |
|--------|-------------------------|----------------------------------|
| **LLM** | Gemini 3.1 Flash-Lite | Claude Haiku 4.5 |
| **Framework** | Google ADK | Custom orchestrator |
| **API** | aiohttp | FastAPI |
| **SDK** | google-genai + google-adk | boto3 bedrock-runtime |
| **Input** | Multimodal (27 types: text, images, audio, video, PDFs) | Multimodal (text, images, PDFs) ✅ |
| **File watcher** | Yes (`./inbox` folder) | Yes (`./inbox` folder) ✅ |
| **Dashboard** | Streamlit | No (API only) |
| **CLI** | Basic (via args) | Rich CLI with commands |
| **Structure** | Single file (~677 lines) | Modular (~20 files) |
| **Consolidation timer** | Built-in async task | Background thread (FastAPI startup) |
| **Async** | Full asyncio | FastAPI async + sync agents |
| **Testing** | Not included | pytest with mocks |

---

## Architecture Deep Dive

### Google Cloud Version

**Single-file monolith** (`agent.py` ~677 lines):
```python
# agent.py contains:
- Database schema setup
- ADK tools (store_memory, read_all_memories, etc.)
- MemoryAgent class using Google ADK agents
- File watcher (watches ./inbox for 27 file types)
- Consolidation timer loop
- aiohttp HTTP API
- Main async event loop
```

**Key features:**
- **Google ADK** handles agent orchestration with tool binding
- **Multimodal ingestion**: Supports 27 file types (text, images, audio, video, PDFs)
- **File watcher**: Drop files in `./inbox`, agent auto-ingests
- **Streamlit dashboard**: Separate `dashboard.py` for UI
- **Fully async**: Uses asyncio for file watching, consolidation, and HTTP

**Agent implementation:**
```python
IngestAgent = Agent(
    model=MODEL,
    tools=[store_memory],
    system_instruction="Extract structured memory...",
)
```

Tools are decorated functions that ADK automatically binds to the agent.

---

### memory-agent-bedrock (this repo)

**Modular structure** (20 files across `agents/`, `memory/`, `api/`, `tests/`):

```
agents/
├── bedrock_client.py   # boto3 wrapper for Claude Haiku (with multimodal support)
├── ingest.py           # IngestAgent class (text, images, PDFs)
├── consolidate.py      # ConsolidateAgent class
├── query.py            # QueryAgent class
├── orchestrator.py     # Coordinates agents
├── watcher.py          # File watcher for automatic ingestion
└── utils.py            # JSON parsing helpers

memory/
├── store.py            # SQLite CRUD layer
├── schema.py           # DB schema initialization
└── models.py           # Pydantic models

api/
├── main.py             # FastAPI app factory (with file watcher support)
└── routes.py           # /ingest, /ingest/file, /query, /status, /consolidate

tests/
├── test_store.py
├── test_agents.py
└── test_api.py
```

**Key features:**
- **boto3 bedrock-runtime**: Direct AWS SDK usage (no anthropic SDK)
- **Multimodal support**: Images (Claude vision), PDFs (PyPDF2), text files
- **File watcher**: Background thread monitors directory for automatic ingestion
- **FastAPI**: Standard HTTP API with uvicorn + automatic OpenAPI docs
- **Rich CLI**: `python cli.py ingest/query/consolidate/status/list`
- **Testing**: pytest with mocked boto3 responses
- **Separation of concerns**: Each agent is a separate class with clear interfaces

**Agent implementation:**
```python
class IngestAgent:
    def __init__(self, store: MemoryStore):
        self.store = store

    def ingest(self, text: str, source: str = "") -> Memory:
        prompt = f"Extract structured memory from: {text}"
        raw = invoke(prompt, system=SYSTEM, max_tokens=1024)
        data = parse_json(raw)
        memory = Memory(...)
        return self.store.add_memory(memory)
```

Manual orchestration via `Orchestrator` class that manages agent lifecycles.

---

## Database Schema Comparison

### Google Cloud
```sql
memories (
    id, source, raw_text, summary, entities, topics,
    connections, importance, created_at, consolidated
)
consolidations (
    id, source_ids, summary, insight, created_at
)
processed_files (
    path, processed_at  -- tracks ingested files
)
```

### memory-agent-bedrock
```sql
memories (
    id, summary, entities, topics, importance,
    source, timestamp, consolidated
)
consolidations (
    id, memory_ids, connections, insights, timestamp
)
```

**Differences:**
- Google stores `raw_text` + `connections` field in memories (not used consistently)
- Google tracks `processed_files` for file watcher
- This repo uses `timestamp` instead of `created_at`
- This repo separates `connections` + `insights` in consolidations

---

## API Comparison

### Google Cloud (aiohttp)
```
GET  /query?q=...          # Query memories
POST /ingest               # Ingest text
POST /consolidate          # Manual consolidation
GET  /status               # Memory stats
GET  /memories             # List all memories
POST /delete               # Delete memory by ID
POST /clear                # Delete all + clear inbox
```

### memory-agent-bedrock (FastAPI)
```
GET  /query?q=...          # Query memories
POST /ingest               # Ingest text
POST /ingest/file          # Upload files (text, images, PDFs)
POST /consolidate          # Manual consolidation
GET  /status               # Memory stats
```

**Differences:**
- Google has `/memories`, `/delete`, `/clear` endpoints
- Google's `/clear` also deletes files from inbox folder
- Bedrock has dedicated `/ingest/file` endpoint for uploads
- FastAPI provides automatic OpenAPI docs at `/docs`

---

## Consolidation Logic Comparison

### Google Cloud
```python
async def consolidation_loop(agent, interval_minutes=30):
    while True:
        await asyncio.sleep(interval_minutes * 60)
        count = db.execute("SELECT COUNT(*) FROM memories WHERE consolidated = 0")
        if count >= 2:  # Min threshold: 2 memories
            await agent.consolidate()
```

- Minimum threshold: **2 unconsolidated memories**
- Processes **all unconsolidated** in one batch
- Runs as async background task

### memory-agent-bedrock
```python
class ConsolidateAgent:
    def __init__(self, store, min_memories=5, max_batch_size=50):
        ...

    def run(self) -> Consolidation | None:
        all_unconsolidated = self.store.get_unconsolidated()
        if len(all_unconsolidated) < self.min_memories:
            return None

        # Batch to avoid exceeding context window
        memories = all_unconsolidated[:self.max_batch_size]
        ...
```

- Minimum threshold: **5 unconsolidated memories** (configurable)
- Processes **up to 50** per batch (prevents context overflow)
- Runs in background thread via FastAPI lifespan events

**Key difference:** This repo has **batch size limiting** to prevent hitting 200K context limits. Google's version processes all unconsolidated memories at once.

---

## Input Handling

### Google Cloud: Multimodal (27 file types)
```python
MEDIA_EXTENSIONS = {
    # Images
    ".png": "image/png", ".jpg": "image/jpeg", ".gif": "image/gif",
    ".webp": "image/webp", ".bmp": "image/bmp", ".svg": "image/svg+xml",
    # Audio
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
    ".flac": "audio/flac", ".m4a": "audio/mp4", ".aac": "audio/aac",
    # Video
    ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
    ".avi": "video/x-msvideo", ".mkv": "video/x-matroska",
    # Documents
    ".pdf": "application/pdf",
}

async def ingest_file(self, file_path: Path):
    """Ingest multimodal file using Gemini."""
    mime_type = MEDIA_EXTENSIONS[file_path.suffix.lower()]
    file_data = types.Part.from_bytes(
        data=file_path.read_bytes(),
        mime_type=mime_type
    )
    result = await Runner(...).run(content=["Extract info from:", file_data])
```

**27 supported file types** across text, images, audio, video, and PDFs.

### memory-agent-bedrock: Multimodal (text, images, PDFs)
```python
SUPPORTED_EXTENSIONS = {
    # Text
    ".txt", ".md", ".json", ".csv", ".log", ".yaml", ".yml",
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    # Documents
    ".pdf",
}

def ingest_file(self, file_path: Path) -> Memory:
    """Extract structured memory from a file (text, image, or PDF)."""
    suffix = file_path.suffix.lower()

    if suffix in IMAGE_EXTENSIONS:
        return self._ingest_image(file_path)  # Claude vision
    elif suffix == ".pdf":
        return self._ingest_pdf(file_path)    # PyPDF2
    else:
        text = file_path.read_text()
        return self.ingest(text, source=file_path.name)

def _ingest_image(self, file_path: Path) -> Memory:
    """Extract structured memory from an image using Claude vision."""
    image_data, media_type = load_image_as_base64(file_path)
    content = [
        {"type": "text", "text": "Extract structured memory from this image..."},
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}}
    ]
    raw = invoke_multimodal(content, system=SYSTEM, max_tokens=1024)
    ...
```

**13 supported file types** for the most common use cases:
- **Text files** (7 types): Direct text processing
- **Images** (5 types): Claude Haiku 4.5 vision API
- **PDFs** (1 type): PyPDF2 text extraction

**Audio/video not implemented** (could add via AWS Transcribe or faster-whisper).

---

## Cost Comparison

### Google Cloud
- **Gemini 3.1 Flash-Lite**: ~$0.0005/1M input tokens (estimate)
- Designed for **24/7 operation** with negligible cost
- Fast, cheap, "smart enough" for background processing
- Multimodal inputs included in token pricing

### memory-agent-bedrock
- **Claude Haiku 4.5**: ~$0.80/1M input tokens
- **Images**: ~1,500 tokens per image (varies by size)
- ~1,600x more expensive than Flash-Lite for text
- But: More accurate reasoning and better instruction following
- **PDFs**: Free extraction (PyPDF2 local), only text sent to Claude

**Example costs:**
- 100 text memories (50K tokens): ~$0.04
- 100 images: ~$0.12 (150K image tokens)
- 100 PDFs (text extraction): ~$0.04 (for text processing only)

**Trade-off:** Google's version optimizes for cost and 24/7 operation. This version optimizes for accuracy using Claude's superior reasoning, with reasonable costs for multimodal inputs.

---

## Testing

### Google Cloud
No tests included in the repo.

### memory-agent-bedrock
```
tests/
├── test_store.py       # SQLite CRUD tests
├── test_agents.py      # Agent logic tests with mocked boto3
└── test_api.py         # FastAPI endpoint tests
```

Run with: `pytest tests/ -v`

All Bedrock calls are mocked — no real AWS credentials needed for testing.

---

## Deployment Considerations

### Google Cloud
**Pros:**
- Single file deployment
- Built-in file watcher for automatic ingestion
- Streamlit dashboard out of the box
- Optimized for low-cost 24/7 operation

**Cons:**
- Requires Google Cloud account + Gemini API access
- Monolithic structure harder to extend
- No testing framework

**Best for:**
- Personal use cases
- Background memory agent that runs continuously
- Multimodal input (images, audio, video)

### memory-agent-bedrock
**Pros:**
- Modular architecture, easy to extend
- Well-tested with pytest
- FastAPI = automatic OpenAPI docs + type validation
- CLI interface for manual operations
- Works with AWS Bedrock (enterprise-friendly)
- Multimodal support (images, PDFs, text)
- File watcher for automatic ingestion

**Cons:**
- No dashboard UI (API only)
- No audio/video support (vs Google's 27 file types)
- Higher LLM cost (~$0.80/M vs ~$0.0005/M)

**Best for:**
- Production deployments requiring modularity
- AWS-native environments
- Cases where Claude's reasoning is worth the cost
- Teams that need testing and maintainability
- Common multimodal use cases (text, images, PDFs)

---

## Why No Vector DB? (Both Implementations)

The core insight is the same:

> For a personal agent's memory store, the total corpus is small enough that you can read recent memories directly into the LLM's context window.

**Math:**
- ~300 tokens per memory (summary + entities + topics + importance)
- 200K context window ÷ 300 tokens/memory = **~650 memories max**
- Both implementations default to **50 memories** per query for speed and cost

**Consolidation as compression:**
- Consolidation insights act as a "memory index"
- As memories grow beyond 650, consolidations provide compressed summaries
- Scales to 1,000+ memories with multi-level consolidation

**This approach is:**
- Simpler (no embedding pipeline, no vector DB)
- Cheaper (no embedding API calls)
- More accurate (LLM reasons over semantics, not cosine similarity)

---

## Migration Path

### ✅ Recently Implemented in Bedrock Version

1. **Multimodal input:** ✅ **DONE**
   - ✅ Claude vision API for images (.png, .jpg, .jpeg, .gif, .webp)
   - ✅ PyPDF2 for PDF text extraction
   - ⬜ Audio transcription (could add via AWS Transcribe or faster-whisper)
   - ⬜ Video processing (could add frame extraction + transcription)

2. **File watcher:** ✅ **DONE**
   - ✅ Background thread monitors directory
   - ✅ Environment variable configuration
   - ✅ Tracks processed files to avoid duplicates

3. **Dashboard:** ⬜ Still TODO
   ```python
   # Add streamlit
   # Connect to FastAPI endpoints
   ```

### To migrate Google Cloud to modular structure:
1. Extract agent classes from single file
2. Add FastAPI instead of aiohttp
3. Add pytest tests
4. Split into `agents/`, `memory/`, `api/` folders

---

## Recommendation

**Use Google Cloud version if:**
- You need audio/video support (the full 27 file types)
- You want 24/7 background operation with minimal cost
- You prefer a simpler, single-file deployment
- You're building a personal memory assistant
- You want the included Streamlit dashboard

**Use memory-agent-bedrock if:**
- You need modularity and testability for production
- You're in an AWS-native environment
- You value Claude's superior reasoning over cost
- You need a CLI interface and OpenAPI docs
- Text, images, and PDFs cover your use cases (most common scenarios)
- You want automatic file watching with configurable monitoring

---

## Future Enhancements

### For memory-agent-bedrock:
- [x] ~~Add multimodal support (Claude vision, Bedrock transcription)~~ ✅ **DONE** (images, PDFs)
- [x] ~~Add file watcher for automatic ingestion~~ ✅ **DONE**
- [ ] Add Streamlit dashboard
- [ ] Add audio support (AWS Transcribe or faster-whisper)
- [ ] Add video support (frame extraction + transcription)
- [ ] Add memory search/filtering by entities/topics
- [ ] Add memory expiration/archival
- [ ] Add multi-level consolidation for 1,000+ memories

### For Google Cloud version:
- [ ] Add modular structure for maintainability
- [ ] Add comprehensive testing
- [ ] Add CLI interface
- [ ] Add batch size limiting in consolidation
- [ ] Add FastAPI migration for better API docs

---

## Conclusion

Both implementations prove the core thesis: **you don't need a vector database for AI agent memory**. The choice between them comes down to:

1. **Cloud platform** (Google vs AWS)
2. **Cost vs accuracy** (Gemini Flash-Lite at $0.0005/M vs Claude Haiku at $0.80/M)
3. **Simplicity vs modularity** (single file vs multi-file)
4. **File type coverage** (27 types with audio/video vs 13 types without audio/video)

Both versions now support the most common multimodal use cases:
- ✅ Text ingestion
- ✅ Image analysis
- ✅ PDF processing
- ✅ Automatic file watching

The key remaining difference is **audio/video support**, which Google includes but represents a smaller percentage of typical use cases.

The Google Cloud version is a **proof of concept** optimized for maximum file type support and minimal cost. The Bedrock version is a **production implementation** optimized for maintainability, testing, and AWS deployment, with multimodal support for the most common scenarios.

Both follow the same pattern, both work well, and both demonstrate that persistent AI memory can be achieved with just SQLite and a large-context LLM—no vector database needed.
