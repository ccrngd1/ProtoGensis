# I Replaced Vector DBs with Google's Memory Agent Pattern — Here's What Happened

*Persistent AI memory without embeddings, Pinecone, or a PhD in similarity search.*

---

## The Setup

Every time I start building a personal AI assistant, I hit the same wall: memory.

Conversations end. Context resets. The agent forgets everything. You ask it about a meeting from last week and it shrugs.

The obvious fix is a vector database. Embed the memories. Store the vectors. Do similarity search at query time. It works. But it also means a Redis stack, or a Pinecone account, or a locally-running Chroma instance, plus an embedding API, plus pipeline code to stitch it all together. For a personal tool, that's a lot.

Then I found Google's [always-on-memory-agent](https://github.com/GoogleCloudPlatform/generative-ai/tree/main/gemini/agents/always-on-memory-agent). The idea is deceptively simple: don't do similarity search at all. Just give the LLM your recent memories directly and let it reason over them.

I wanted to know if that held up on AWS Bedrock with Claude Haiku 4.5. So I built it.

---

## The Insight That Changes the Math

Here's the thing about vector search that doesn't get said enough: it's a workaround for context limits.

Older models topped out at 4K or 8K tokens. You couldn't fit more than a few documents in a prompt. Embeddings let you retrieve the *relevant* documents without loading everything. That was genuinely necessary.

Haiku 4.5 has a 200K context window.

A structured memory — summary, entities, topics, importance score — runs about 300 tokens. Do the math: 200,000 / 300 = roughly 666 memories before you hit the limit. For a personal assistant that tracks meetings, notes, and conversations, that's months of context.

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

**ConsolidateAgent** runs on a background timer (every 5 minutes by default). When 5 or more unconsolidated memories accumulate, it batches them and asks Haiku to find cross-cutting connections and generate insights. Think of it as the sleeping brain — processing during idle time, forming associations. Results land in a `consolidations` table.

**QueryAgent** reads recent memories plus consolidation insights into a single prompt and returns a synthesized answer with citation IDs.

The stack is Python, FastAPI, boto3, and SQLite. Zero infrastructure beyond an AWS account.

---

## Seeing It in Action

Start the server:

```bash
./run.sh
# Sets up venv, installs deps, launches on :8000
```

Ingest some text:

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"text": "Met with Alice today. Q3 budget is approved — $2.4M.", "source": "notes"}'
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

This is the part I find most interesting.

Most memory systems are purely retrieval: store, search, return. The consolidation agent does something different. It reads a batch of unconsolidated memories and asks: what connects these? What patterns emerge? What insights follow from them together?

Those insights get written as a separate `consolidations` record. When you query, you get both the raw memories *and* the synthesized insights. The agent isn't just recalling — it's reasoning.

The sleeping brain analogy from the original Google implementation is apt. During idle time, the system is processing rather than just waiting.

For a personal tool, this matters. "You've had three meetings with Alice this month and all of them mentioned budget concerns" is more useful than three individual recall hits.

---

## The Honest Part: Two Critical Bugs

The code review caught two issues that would bite you immediately on a real AWS deployment. Documenting them here because if you clone this, you need to know.

**Bug 1: Invalid default model ID**

The default Bedrock model ID in `bedrock_client.py` uses a `global.` prefix:

```python
MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID",
    "amazon-bedrock/global.anthropic.claude-haiku-4-5-20251001-v1:0",
)
_RAW_MODEL_ID = MODEL_ID.removeprefix("amazon-bedrock/")
# Sends: "global.anthropic.claude-haiku-4-5-20251001-v1:0" to Bedrock
```

Bedrock doesn't recognize `global.` as a valid prefix. Your first real API call fails. The tests all mock boto3, so this never surfaced in the test suite.

The fix is straightforward: use `us.anthropic.claude-haiku-4-5-20251001-v1:0` (a valid cross-region inference profile) or the direct model ID. Set `BEDROCK_MODEL_ID` in your environment and don't rely on the default.

**Bug 2: The context window math was wrong**

The README originally claimed the system could handle "~5,000 memories × 100 tokens each." Neither number held up under scrutiny.

A real memory entry — with UUID, summary, entities, topics, and importance score — runs closer to 300 tokens. At 300 tokens per memory, Haiku's 200K context holds about 666 memories max before you hit the limit. The `QueryAgent` was using a `limit=2000` by default, which would blow past the context window by 3x once any serious memory accumulation happened.

The fix: cap the query limit at around 50 memories for normal use (fast, cheap, reliable) with a hard ceiling around 600 for power users. The README now reflects the corrected math. The architecture still works. The original claim just needed honest numbers.

Both bugs are now fixed. But they're a good reminder that mocked test suites can't catch "will this API accept this argument."

---

## The Real Scalability Ceiling

Here's the honest version of the scalability picture:

For a personal assistant, 600 memories covers a lot of ground. That's months of notes, conversations, and context at normal usage rates.

For something heavier, the consolidation agent provides a path forward. Insights are a compressed representation of batches of memories. The query context can lean on consolidations for older material while using raw memories for recent ones. You're not throwing away history — you're summarizing it.

The ceiling isn't as high as the original README implied. But for the use case (personal, persistent, conversational memory), it's high enough.

---

## Why No Vector DB

There's a simpler answer to the question of whether you need embeddings for personal memory: it depends entirely on your corpus size.

Vector search is genuinely necessary when you have millions of documents and can't fit the relevant ones in context. It's a retrieval optimization for large-scale problems.

At personal scale — hundreds of memories, not millions — it's overhead. You're running an embedding pipeline, paying for the API calls, managing the index, and implementing similarity search to solve a problem that a 200K context window already solves.

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

## What's Next

The system works as a standalone API. A few natural extensions:

**Importance-weighted query filtering.** Right now the query agent reads the N most recent memories. Filtering by importance score before building the context window would let higher-signal memories stay in play longer.

**Delete and update endpoints.** The store is currently append-only. Personal data stores need a way to correct or remove memories. `DELETE /memory/{id}` is an obvious gap.

**HTTP/SSE transport for consolidation.** The background thread works but isn't observable. Streaming consolidation events would make the "sleeping brain" behavior visible and debuggable.

**MCP integration.** Wrapping this as an MCP server would let any Claude-compatible client use it as persistent memory. That's the natural endpoint for a tool like this.

---

## Try It

The project is up on GitHub as part of the [Protogenesis series](https://github.com). It's Python with no exotic dependencies — just boto3, FastAPI, and SQLite.

```bash
git clone <repo>
cd memory-agent-bedrock
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0  # don't use the default
./run.sh
```

20 tests pass. Three agents cooperate. No vector database anywhere.

If you're building personal AI tooling and stalling on the memory problem, this pattern is worth understanding. The insight that context windows obsolete embedding retrieval at small scale isn't obvious. But once you see it, it's hard to unsee.

---

*Built during Protogenesis. Memory Agent Bedrock is based on [Google's always-on-memory-agent](https://github.com/GoogleCloudPlatform/generative-ai/tree/main/gemini/agents/always-on-memory-agent), adapted for AWS Bedrock and Claude Haiku 4.5.*
