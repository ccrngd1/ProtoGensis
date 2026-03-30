# I Replaced Vector DBs with Google's Memory Agent Pattern. Here's What Happened

*Persistent AI memory without embeddings, Pinecone, or a PhD in similarity search.*

---

**What this project is:** A persistent memory system for AI assistants that stores and retrieves memories using SQLite and direct LLM reasoning. No vector databases required.
**The problem it solves:** Every time a conversation ends, the agent forgets everything, and the standard fix (vector databases + embeddings) is overkill for a personal tool.
**The key insight:** Vector search exists to work around small context windows. With 200K token windows, you can just load your memories directly and let the model reason over them.

---

## The Setup

I take detailed notes, both in my personal life and at work. I used to scrawl into notebooks that would get misplaced, or stuck on a shelf and never referenced again. A few years ago, I moved to Obsidian for everything, and it has been fantastic. In the last year, I've started hooking up genAI to my notes. Today I run both Claude Code (for my personal notes) and Kiro-CLI (for my work notes). I can ask questions, get them to do roll ups for leadership, track my goals, write my reports. But it's always had one big Achilles' heel: memory. When I ask about a meeting, it uses an Obsidian MCP to search my vault. It's time consuming, error prone, and I need it to be better.

The obvious fix is a vector database. Embed the memories. Store the vectors. Do similarity search at query time. It works. But it also means a Redis stack, or a Pinecone account, or a locally-running Chroma instance, plus an embedding API, plus pipeline code to stitch it all together. For a personal tool, that's a lot, and there is a real risk that it won't work exactly like I need it to. I need to ask, what happened on 'Feb 1 2026' or 'recap the last meeting I had with this person', things that embeddings and RAG aren't great with.

Then I found Google's [always-on-memory-agent](https://github.com/GoogleCloudPlatform/generative-ai/tree/main/gemini/agents/always-on-memory-agent). The idea is deceptively simple: don't do similarity search at all. Just give the LLM your recent memories directly and let it reason over them.

I wanted to know if that held up on AWS Bedrock with Claude Haiku 4.5. So I built it (along with Claude Code of course).

---

## The Insight That Changes the Math

Here's the thing about vector search that doesn't get said enough: it's a workaround for context limits.

Older models topped out at 4K or 8K tokens. You couldn't fit more than a few documents in a prompt. Embeddings let you retrieve the *relevant* documents without loading everything. That was genuinely necessary.

Haiku 4.5 has a 200K context window.

A structured memory (summary, entities, topics, importance score) runs about 300 tokens. Do the math: 200,000 / 300 = roughly 666 memories before you hit the limit. For a personal assistant that tracks meetings, notes, and conversations, that's months of context.

No embeddings. No vector index. No cosine similarity. Just: here are your memories, what do you know about this?

The LLM reasons over semantics directly. It's actually *better* at that than cosine similarity.

---

## The Architecture

Three specialist sub-agents share a single SQLite database. That's the whole thing.

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
   └─────────────────────────────────────────────────┘
```

**IngestAgent** takes raw text and calls Haiku to extract structured metadata: a summary, entities (names, places, things), topics, and an importance score from 0 to 1. That package goes into the `memories` table.

**ConsolidateAgent** runs with intelligent scheduling: at startup if any memories exist, on a threshold (5+ memories by default), and daily as a forced pass. When triggered, it batches unconsolidated memories and asks Haiku to find cross-cutting connections and generate insights. Think of it as the sleeping brain, processing during idle time, forming associations. Results land in a `consolidations` table. The system tracks the last consolidation timestamp to ensure regular processing even with low memory accumulation.

**QueryAgent** reads recent memories plus consolidation insights into a single prompt and returns a synthesized answer with citation IDs.

The stack is Python, FastAPI, boto3, and SQLite. Zero infrastructure beyond an AWS account.

---

## What Actually Gets Stored

When you ingest text like "Met with Alice today. Q3 budget is approved, $2.4M," the system doesn't just dump that raw string into a database row.

Instead, the IngestAgent sends it to Haiku and asks: what's important here? The LLM extracts structured metadata:

```json
{
  "id": "a3f1c9d2-...",
  "summary": "Alice confirmed Q3 budget approval of $2.4M",
  "entities": ["Alice", "Q3 budget"],
  "topics": ["finance", "meetings"],
  "importance": 0.82,
  "source": "notes",
  "timestamp": "2026-03-27T14:23:15.123456+00:00",
  "consolidated": 0
}
```

That's it. No embeddings. No vectors. Just a UUID, a timestamp, LLM-extracted semantics, and a flag for whether it's been consolidated yet.

The **`memories`** table holds these individual records. At ~300 tokens per memory when formatted into a prompt (including the metadata), you can fit roughly 650 memories in Haiku's 200K context window before hitting the ceiling. The system defaults to loading 50 at query time for speed and cost efficiency.

The **`consolidations`** table is where things get interesting. When the ConsolidateAgent runs, it doesn't just summarize memories. It reasons over them. It finds patterns, draws connections, and generates insights about what the memories mean together. Those insights get stored as separate records:

```json
{
  "id": "3c765a26-...",
  "memory_ids": ["a3f1c9d2-...", "b7e4f8a1-...", "c9d2e5b3-..."],
  "connections": "All three meetings with Alice mentioned budget concerns...",
  "insights": "Budget oversight appears to be a recurring priority...",
  "timestamp": "2026-03-27T14:28:00.000000+00:00"
}
```

When you query, the system loads both the raw memories *and* the consolidation insights into the same prompt. The LLM reasons over both layers at once: recent facts plus synthesized patterns. That's how you get answers like "Alice has raised budget concerns in three separate meetings [memory:a3f1c9d2, memory:b7e4f8a1] and the pattern suggests this is a high priority [consolidation:3c765a26]."

This two-table design is the entire persistence layer. A single SQLite file. No Redis. No Pinecone. No embedding pipeline. Just structured records that an LLM can reason over directly.

---

## Seeing It in Action

Configuration is handled via a `.env` file with sensible defaults. Copy the example and customize:

```bash
cp .env.example .env
# Edit AWS credentials and other settings
```

Start the server:

```bash
./scripts/run-with-watcher.sh
# Sets up venv, installs deps, launches with file watcher enabled
```

Ingest some text:

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"text": "Met with Alice today. Q3 budget is approved, $2.4M.", "source": "notes"}'
```

Response:

```json
{
  "id": "a3f1c9d2-...",
  "summary": "Alice confirmed Q3 budget approval of $2.4M.",
  "entities": ["Alice", "Q3 budget"],
  "topics": ["finance", "meetings"],
  "importance": 0.82,
  "source": "notes"
}
```

Query it later:

```bash
curl "http://localhost:8000/query?q=What+did+Alice+say+about+the+budget"
```

```json
{
  "answer": "Alice confirmed the Q3 budget is approved at $2.4M [memory:a3f1c9d2]. ..."
}
```

Or use the CLI:

```bash
python cli.py ingest "Paris is the capital of France." --source wikipedia
python cli.py query "What do you know about France?"
python cli.py consolidate  # trigger manually
python cli.py status       # see memory count, consolidation state
```

---

## What the Consolidation Agent Actually Does

Most memory systems are purely retrieval: store, search, return. The consolidation agent does something different. It reads a batch of unconsolidated memories and asks: what connects these? What patterns emerge? What insights follow from them together?

Those insights get written as a separate `consolidations` record. When you query, you get both the raw memories *and* the synthesized insights. The agent isn't just recalling. It's reasoning.

The sleeping brain analogy from the original Google implementation is apt. During idle time, the system is processing rather than just waiting.

For a personal tool, this matters. "You've had three meetings with Alice this month and all of them mentioned budget concerns" is more useful than three individual recall hits.

---

## Enhanced Consolidation: Beyond the Timer

The original design ran consolidation on a simple threshold: wait for 5 memories, then consolidate. That works, but it left gaps.

If you're only ingesting sporadically, a note here, an image there, you might wait days before hitting the threshold. Meanwhile, those memories sit unconsolidated, meaning queries don't benefit from the pattern recognition the consolidation agent provides.

The fix was to add two more triggers. When the server starts, it checks for unconsolidated memories from the previous session and processes them immediately. No waiting. And on a daily timer (configurable), it forces a consolidation pass regardless of count, so even a single note per week still gets consolidated within 24 hours.

The original threshold-based mode still runs for active use. But now there's a safety net underneath it. If you're actively ingesting, the threshold catches it. If you're not, the daily pass does. And on restart, nothing falls through the cracks.

All three modes are configurable. Want aggressive consolidation? Set `DAILY_CONSOLIDATION_INTERVAL=3600`. Want startup-only? Disable the daily mode. The system adapts to how you actually use it.

---

## File Watching and Change Detection

The API works great for programmatic ingestion. But for personal use, you want to point the system at a notes directory and let it watch.

I have an Obsidian vault with hundreds of notes. I don't want to manually ingest each one. I want to point the watcher at the vault, add `.obsidian` to the ignore list, and let it handle the rest. That's what this does.

On startup, the watcher scans the directory and ingests everything it hasn't seen before. After that, it runs two modes in the background. A quick scan every 60 seconds checks for new files (fast, no hash calculation, just "is this path in the database?"). A full scan every 30 minutes calculates SHA256 hashes and compares them to stored values. If a file changed, the system deletes the old memories, cleans up any consolidations that referenced them, re-ingests the new version, and updates the tracking record. No duplicates. No stale data.

The file watcher supports:
- Text files (.txt, .md, .json, .csv, .log, .yaml, .yml)
- Images (.png, .jpg, .jpeg, .gif, .webp), analyzed via Claude Haiku's vision capabilities
- PDFs (.pdf), text extracted via PyPDF2

Recursive scanning and directory exclusions are configurable. Edit a note in Obsidian, and within 30 minutes the agent's memory reflects the change.

---

## Configuration: .env by Default

Rather than exporting a dozen environment variables or passing flags, the system now loads a `.env` file at startup.

```bash
cp .env.example .env
# Edit AWS credentials, consolidation intervals, file watcher settings
./scripts/run-with-watcher.sh
```

All settings have sensible defaults. You can run it with zero configuration (beyond AWS credentials) and it works. Or tweak every interval and threshold if you want. The `.env.example` file documents every option with comments explaining what it does.

This matters more than it sounds like it should. The difference between "export 12 variables and hope you got them all right" and "copy a file and edit the 2 lines you care about" is the difference between a project you use once and a project you actually run.

---

## The Honest Part: Two Critical Bugs

The code review caught two issues that would bite you immediately on a real AWS deployment. Documenting them here because if you clone this, you need to know.

**Bug 1: Invalid default model ID**

The original default Bedrock model ID in `bedrock_client.py` used a `global.` prefix:

```python
# Original (broken):
MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID",
    "amazon-bedrock/global.anthropic.claude-haiku-4-5-20251001-v1:0",
)
```

Bedrock doesn't recognize `global.` as a valid prefix. The first real API call would fail. The tests all mock boto3, so this never surfaced in the test suite.

The fix: swap to `us.anthropic.claude-haiku-4-5-20251001-v1:0` (a valid cross-region inference profile). The default is now correct in the codebase, but the lesson stands. Mocked tests won't catch invalid model IDs.

**Bug 2: The context window math was wrong**

The README originally claimed the system could handle "~5,000 memories × 100 tokens each." Neither number held up under scrutiny.

A real memory entry, with UUID, summary, entities, topics, and importance score, runs closer to 300 tokens. At 300 tokens per memory, Haiku's 200K context holds about 666 memories max before you hit the limit. The `QueryAgent` was using a `limit=2000` by default, which would blow past the context window by 3x once any serious memory accumulation happened.

The fix: cap the query limit at around 50 memories for normal use (fast, cheap, reliable) with a hard ceiling around 600 for power users. The README now reflects the corrected math. The architecture still works. The original claim just needed honest numbers.

Both bugs are now fixed. But they're a good reminder that mocked test suites can't catch "will this API accept this argument."

---

## The Real Scalability Ceiling

Here's the honest version of the scalability picture:

For a personal assistant, 600 memories covers a lot of ground. That's months of notes, conversations, and context at normal usage rates.

For something heavier, the consolidation agent provides a path forward. Insights are a compressed representation of batches of memories. The query context can lean on consolidations for older material while using raw memories for recent ones. You're not throwing away history. You're summarizing it.

The ceiling isn't as high as the original README implied. But for the use case (personal, persistent, conversational memory), it's high enough.

---

## Why No Vector DB

There's a simpler answer to the question of whether you need embeddings for personal memory: it depends entirely on your corpus size.

Vector search is genuinely necessary when you have millions of documents and can't fit the relevant ones in context. It's a retrieval optimization for large-scale problems.

At personal scale, hundreds of memories, not millions, it's overhead. You're running an embedding pipeline, paying for the API calls, managing the index, and implementing similarity search to solve a problem that a 200K context window already solves.

The tradeoffs:

| | Vector DB approach | This approach |
|---|---|---|
| Complexity | Embedding pipeline + DB infra | SQLite, nothing else |
| Cost | Embedding API calls + DB hosting | Just LLM inference |
| Accuracy | Cosine similarity | LLM semantic reasoning |
| Scale | Millions of docs | ~600 memories reliably |
| Setup time | Hours | Minutes |

For personal use, this wins on every axis except scale. And for the scale question, you'd need to seriously outpace normal usage before hitting the ceiling.

---

## Integrations: Making It Useful Beyond curl

curl works. But you're not going to curl your memory system at 2am when you have an idea. The project ships with two integration paths.

**Claude Code skill.** A native skill that auto-activates when relevant. Say "remember that Alice approved the Q3 budget" and it stores it without you needing to invoke anything. Ask "what did Alice say about the budget?" next week and it checks memory before answering. Installation is one script (`integrations/claude-code-skill/install.sh`). It handles ingestion, queries, file uploads, and status checks through natural conversation.

**CLI.** For terminal users or scripting:

```bash
python cli.py ingest "Paris is the capital of France." --source wikipedia
python cli.py query "What do you know about France?"
python cli.py consolidate
python cli.py status
python cli.py list --limit 10
```

The CLI talks to the same SQLite database, so you can mix API, CLI, and skill usage interchangeably. Ingest from a script, query from Claude Code, check status from the terminal. It all hits the same store.

---

## What's Next

The system works as a standalone API with intelligent consolidation, file watching, change detection, and tool integrations already built in. Natural extensions from here:

**Importance-weighted query filtering.** Right now the query agent reads the N most recent memories. Filtering by importance score before building the context window would let higher-signal memories stay in play longer.

**Delete and update endpoints.** The store is currently append-only. Personal data stores need a way to correct or remove memories. `DELETE /memory/{id}` is an obvious gap.

**HTTP/SSE transport for consolidation.** The background thread works but isn't observable via API. Streaming consolidation events would make the "sleeping brain" behavior visible and debuggable in real-time.

**MCP integration.** Wrapping this as an MCP server would let any Claude-compatible client use it as persistent memory. That's the natural endpoint for a tool like this.

**Already implemented:**
- ✅ File watcher for automatic ingestion (text, images, PDFs)
- ✅ Change detection via content hashing
- ✅ Startup and daily consolidation
- ✅ Status endpoint with file tracking
- ✅ .env configuration system
- ✅ Claude Code skill for seamless cross-session memory (auto-activates when relevant)
- ✅ CLI interface (`cli.py`) for terminal-based ingestion, queries, and management

---

## Try It

The project is up on GitHub as part of the [Protogenesis series](https://github.com). It's Python with no exotic dependencies: boto3, FastAPI, and SQLite.

```bash
git clone <repo>
cd memory-agent-bedrock

# Configure via .env file
cp .env.example .env
# Edit .env with your AWS credentials

# Or export directly
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1

./scripts/run-with-watcher.sh
```

20 tests pass. Three agents cooperate. No vector database anywhere.

If you're building personal AI tooling and stalling on the memory problem, this pattern is worth understanding. The insight that context windows obsolete embedding retrieval at small scale isn't obvious. But once you see it, it's hard to unsee.

---

*Built during Protogenesis. Memory Agent Bedrock is based on [Google's always-on-memory-agent](https://github.com/GoogleCloudPlatform/generative-ai/tree/main/gemini/agents/always-on-memory-agent), adapted for AWS Bedrock and Claude Haiku 4.5.*
