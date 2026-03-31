# I Replaced Vector DBs with Google's Memory Agent Pattern. Here's What Happened

*Persistent AI memory without embeddings, Pinecone, or a PhD in similarity search.*

---

This started because my AI assistants kept getting amnesia. I didn't want to stand up Pinecone or Redis just so Claude could remember that Alice approved the Q3 budget last week. Turns out, with 200K+ context windows, you might not need any of that.

What follows is a persistent memory system built on SQLite and direct LLM reasoning. No vector databases, no embedding pipeline. Vector search is a workaround for small context windows and to keep contexts clean. With modern context sizes, you can skip the workaround and let the model reason over your memories directly.

---

## The Setup

I take detailed notes, both in my personal life and at work. I used to scrawl into notebooks that would get misplaced, or stuck on a shelf and never referenced again. A few years ago, I moved to Obsidian for everything, and it has been fantastic. In the last year, I've started hooking up genAI to my notes. Today I run both Claude Code (for my personal notes) and Kiro-CLI (for my work notes). I can ask questions, get them to do roll ups for leadership, track my goals, write my reports. But it's always had one big Achilles' heel: memory. When I ask about a meeting, it uses an Obsidian MCP to search my vault. It's time consuming, error prone, and I need it to be better.

The obvious fix is a vector database. Embed the memories. Store the vectors. Do similarity search at query time. It works. But it also means a Redis stack, or a Pinecone account, or a locally-running Chroma instance, plus an embedding API, plus pipeline code to stitch it all together. For a personal tool, that's a lot, and there is a real risk that it won't work exactly like I need it to. I need to ask, what happened on 'Feb 1 2026' or 'recap the last meeting I had with this person', things that embeddings and RAG aren't great with.

Then I found Google's [always-on-memory-agent](https://github.com/GoogleCloudPlatform/generative-ai/tree/main/gemini/agents/always-on-memory-agent). The idea is pretty simple: don't do similarity search at all. Just give the LLM your recent memories directly and let it reason over them.

I wanted to know if that held up on AWS Bedrock with Claude Haiku 4.5. So I built it (along with Claude Code of course).

---

## The Insight That Changes the Math

Older models topped out at 4K or 8K tokens. You couldn't fit more than a few documents in a prompt. Embeddings let you retrieve the *relevant* documents without loading everything. That was genuinely necessary.

Haiku 4.5 has a [200K token context window](https://docs.anthropic.com/en/docs/about-claude/models).

A structured memory (summary, entities, topics, importance score) runs about 300 tokens. Do the math: 200,000 / 300 ≈ 650 memories before you hit the ceiling. In practice it's a bit less since the system prompt and query also consume tokens, but for a personal assistant that tracks meetings, notes, and conversations, that's months of context.

No embeddings. No vector index. No cosine similarity.

The LLM reasons over semantics directly and it's *better* at that than cosine similarity.

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

The orchestrator isn't a separate service. It's a Python class inside the FastAPI process that coordinates the three agents.

The **IngestAgent**'s job is simple: take raw text and ask Haiku what's worth remembering. It extracts a summary, entities (names, places, things), topics, and an importance score from 0 to 1. That package goes into the `memories` table.

The **ConsolidateAgent** is the interesting one. It runs with intelligent scheduling: at startup if any memories exist, on a threshold (5+ memories by default), and daily as a forced pass. When triggered, it batches unconsolidated memories and asks Haiku to find cross-cutting connections and generate insights. Think of it as the sleeping brain, processing during idle time, forming associations. Results land in a `consolidations` table. The system tracks the last consolidation timestamp to ensure regular processing even with low memory accumulation.

The **QueryAgent** reads recent memories plus consolidation insights into a single prompt and returns a synthesized answer with citation IDs. That's the whole query path.

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

The **`memories`** table holds these individual records. At ~300 tokens per memory when formatted into a prompt (including the metadata), the theoretical ceiling is around 650 memories in Haiku's 200K context window. The system defaults to loading 50 at query time for speed and cost efficiency, so you're nowhere near that limit in normal use.

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

When you query, the system loads both the raw memories *and* the consolidation insights into the same prompt. The LLM reasons over both layers at once, including recent facts plus synthesized patterns. That's how you get answers like "Alice has raised budget concerns in three separate meetings [memory:a3f1c9d2, memory:b7e4f8a1] and the pattern suggests this is a high priority [consolidation:3c765a26]."

This two-table design is the entire persistence layer. A single SQLite file. No Redis. No Pinecone. No embedding pipeline. Just structured records that an LLM can reason over directly.

---

## Seeing It in Action

Here's what using it actually looks like. Configuration is handled via a `.env` file with sensible defaults:

```bash
cp .env.example .env
# Edit AWS credentials and other settings
```

Start the server:

```bash
./scripts/run-with-watcher.sh
# Sets up venv, installs deps, launches using settings from your .env
# File watcher is enabled by default in .env.example
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

Most memory systems are purely retrieval: store, search, return. The consolidation agent does something different. It reads a batch of unconsolidated memories and asks "what connects these?", "What patterns emerge?", "What insights follow from them together?".

Those insights get written as a separate `consolidations` record. When you query, you get both the raw memories *and* the synthesized insights. The agent isn't just recalling. It's reasoning.

The sleeping brain analogy from the original Google implementation is apt. During idle time, the system is processing rather than just waiting.

For a personal tool, this matters. "You've had three meetings with Alice this month and all of them mentioned budget concerns" is more useful than three individual recall hits.

The original design ran consolidation on a simple threshold: it waits for 5 memories, then consolidates. That works for active use. But if you're only ingesting sporadically, a note here, an image there, you might wait days before hitting the threshold. Meanwhile, those memories sit unprocessed, and queries don't benefit from the pattern recognition the consolidation agent provides.

The fix was to add two more triggers. When the server starts, it checks for unconsolidated memories from the previous session and processes them immediately. No waiting. And on a daily timer (configurable), it forces a consolidation pass if anything is waiting, regardless of whether the 5-memory threshold has been met. So even a single note per week still gets consolidated within 24 hours.

The original threshold-based mode still runs for active use. But now there's a safety net underneath it. If you're actively ingesting, the threshold catches it. If you're not, the daily pass does. And on restart, nothing falls through the cracks.

---

## File Watching and Change Detection

The API works great for programmatic ingestion. But for personal use, you want to point the system at a notes directory and let it watch.

I have an Obsidian vault with hundreds of notes. I don't want to manually ingest each one. I want to point the watcher at the vault, add `.obsidian` to the ignore list, and let it handle the rest. That's what this does.

On startup, the watcher scans the directory and ingests everything it hasn't seen before. After that, it runs two modes in the background. A quick scan every 60 seconds checks for new files (fast, no hash calculation, just "is this path in the database?"). A full scan every 30 minutes calculates SHA256 hashes and compares them to stored values. If a file changed, the system deletes the old memories, cleans up any consolidations that referenced them, re-ingests the new version, and updates the tracking record. No duplicates. No stale data.

For personal note workflows, the watcher covers what you'd expect:
- Text files (.txt, .md, .json, .csv, .log, .yaml, .yml)
- Images (.png, .jpg, .jpeg, .gif, .webp), analyzed via Claude Haiku's vision capabilities
- PDFs (.pdf), text extracted via PyPDF2

Recursive scanning and directory exclusions are configurable. Edit a note in Obsidian, and within 30 minutes the agent's memory reflects the change.

---

## Why No Vector DB

Whether you need embeddings for your personal notes comes down to two major criteria, the size of your corpus and how you want to search your notes.

Vector search is genuinely necessary when you have millions of documents and can't fit the relevant ones in context. It's a retrieval optimization for large-scale problems.

At personal scale, hundreds of memories, not millions, it's overhead. You're running an embedding pipeline, paying for the API calls, managing the index, and implementing similarity search to solve a problem that a 200K context window already solves.

Here's how I think about the tradeoffs:

**Complexity.** I didn't want to maintain a Redis stack or a Chroma instance on my homelab just to remember 300 notes. SQLite is a single file. It gets backed up with everything else. Done.

**Cost.** Bedrock inference is already the main expense. Adding an embedding API on top, plus whatever hosting the vector DB needs, felt like paying twice for the same job.

**Accuracy.** This is the one that surprised me. Cosine similarity finds documents that are *near* your query in embedding space. An LLM reading the actual text reasons about what the words *mean*. For "recap my last meeting with Alice," semantic reasoning beats vector proximity. It's not even close.

**Scale.** If you have 10,000 memories, you probably do want a vector DB. I'm nowhere near that. At normal usage, 650 memories is months of context.

**Setup.** Minutes, not hours. Copy a `.env` file, run a script. No infrastructure to provision.

For personal use, this wins on every axis except scale. And for the scale question, you'd need to seriously outpace normal usage before hitting the ceiling.

---

## Making It Useful Beyond `curl`

`curl` works, but you're not going to curl your memory system at 2am when you have an idea. The project ships with two integration paths.

**Claude Code / Kiro-CLI skill.** A native skill that auto-activates when relevant. Say "remember that Alice approved the Q3 budget" and it stores it without you needing to invoke anything. Ask "what did Alice say about the budget?" next week and it checks memory before answering. It handles ingestion, queries, file uploads, and status checks through natural conversation.

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

The system works and I'm using it, but here are a few additions it could benefit from.

**Importance-weighted query filtering.** Right now the query agent reads the N most recent memories. That means old but important memories can get pushed out by recent noise. I want to filter by importance score before building the context, but I'm not sure yet how aggressive to be. I don't want a high-importance memory from two months ago to disappear just because I ingested a bunch of meeting notes this week.

**Metadata filtering.** Similarly, since each memory has metadata associated with it, I could use this to reduce memories that will obviously be wrong. If I'm asking questions about Alice, I don't need any memories that only involve Bob or Charlie. For my use case, this could be based on my note hierarchy, since I keep notes aligned to my customers and to specific projects.

**Delete and update endpoints.** The store is append-only right now. That's fine until you ingest something wrong and need to fix it. `DELETE /memory/{id}` is an obvious gap. I just haven't needed it badly enough yet to build it.

**MCP integration.** Wrapping this as an MCP server would let any Claude-compatible client use it as persistent memory. That's probably the highest-leverage thing on this list, but it's also the most work.

**HTTP/SSE transport for consolidation.** The background thread works but you can't observe it from the API. Streaming consolidation events would make the "sleeping brain" behavior visible and debuggable. This is a nice-to-have, not urgent.

The core system is already in place: file watching with automatic ingestion for text, images, and PDFs; change detection via content hashing so edits update rather than duplicate; startup and daily consolidation so nothing sits unprocessed; a status endpoint, `.env` configuration, a CLI, and a Claude Code / Kiro-CLI skill that auto-activates when relevant.

---

## Try It

The project is up on GitHub as part of the [Protogenesis series](https://github.com). It's Python with no exotic dependencies, just boto3, FastAPI, and SQLite. The default model is `us.anthropic.claude-haiku-4-5-20251001-v1:0` (Bedrock cross-region inference profile), configurable via `.env`.

```bash
git clone <repo>
cd memory-agent-bedrock

# Configure via .env file (preferred -- keeps credentials out of shell history)
cp .env.example .env
# Edit .env with your AWS credentials

# Or export directly (for quick testing only)
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1

./scripts/run-with-watcher.sh
```

A note on security: the server has no authentication by default. It's designed for localhost use. If you expose it on a network, add auth before you do. The SQLite database will contain everything you've ever ingested, so treat it accordingly (`chmod 600 memory.db` is a good start).

20 tests pass. Three agents cooperate. No vector database anywhere.

If you're building personal AI tooling and stalling on the memory problem, this pattern is worth understanding. The insight that context windows obsolete embedding retrieval at small scale isn't obvious. But once you see it, it's hard to unsee.

---

*Built during Protogenesis Week 10. Named for Google's always-on-memory-agent pattern, ported to AWS Bedrock with Claude Haiku 4.5. Stack: Python 3.11, FastAPI, SQLite, boto3.*
