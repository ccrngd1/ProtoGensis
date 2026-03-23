# Teaching My AI Agent to Remember Its Mistakes

*How a research paper from Accenture gave me a simple pattern for giving agents long-term memory without blowing up their context window.*

---

## The Agent That Forgot Everything

I was running a long-horizon coding agent. Its job: research OAuth2 libraries, pick one, write the integration, debug it.

It did great on step one. It found five libraries, compared them, picked `authlib`. Smart choice.

Then it started writing code. A few tool calls later, the OAuth research was gone. Scrolled off the context window. The agent was flying blind, occasionally rediscovering facts it had already found 15 minutes earlier.

This is the failure mode nobody talks about when they demo agents doing impressive things. The demos are short. Production tasks are not. Eventually, your agent forgets.

I'd seen two standard solutions to this problem. Truncation: just cut the old stuff. Running summaries: compress as you go. Both are lossy. Once the evidence is gone, it's gone. The agent can't verify its reasoning. It can't revisit a discarded approach. It just... forgets.

There had to be a better way.

## A Paper With a Good Idea

I found it in a March 2026 paper from Accenture: [arXiv:2603.04257](https://arxiv.org/abs/2603.04257), "Scaling Long-Horizon LLM Agents via Indexed Experience Memory."

The paper introduces MemexRL, a system where agents learn to use two operations: `compress` and `read`. When a tool response is too long to keep in context, the agent compresses it into a compact indexed summary and archives the full content. When it needs the full detail later, it reads it back. Losslessly.

The RL part is about training the agent to know *when* to compress and *when* to read back. That's interesting research. But the underlying pattern is what grabbed me: an indexed external memory that the agent can write to and read from, with lossless recovery on demand.

You don't need RL-trained policies to use that pattern. You just need the plumbing.

So I built the plumbing.

## What Memex Does

Two agent tools. That's it.

```python
compress_experience(content, index_key, context=None) → indexed_summary
read_experience(index_key)                            → full_content
```

When a tool returns 2,000 tokens of research findings, the agent calls `compress_experience`. Memex sends the content to Claude Haiku 4.5 via AWS Bedrock, gets back a 100-200 token summary, archives the full content in SQLite, and returns a compact indexed block that fits in working context:

```
[research:oauth-libs]
Summary: Recommend authlib: async, JWT built-in, PKCE required.
Archived: 2026-03-09T14:30Z | Tokens saved: 1,847
```

The agent keeps this tiny block in context instead of the original 1,900 tokens. When it needs the full detail later, it calls `read_experience("[research:oauth-libs]")` and gets back the exact original content. Not a summary of a summary. The real thing.

The key insight is that the summary serves two purposes simultaneously. It's a reminder: "I have this information, here's the gist." And it's a pointer: "If I need the real thing, here's how to get it."

Most memory systems give you one or the other. Memex gives you both.

## The Architecture

The stack is deliberately simple.

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

**SQLite** stores the full content. It's zero-config, ACID-compliant, handles megabytes without complaint, and runs embedded in the process. For a single-agent use case, it's exactly the right tool. No Postgres setup. No Redis. Just a file.

**Claude Haiku 4.5** does the summarization via AWS Bedrock. It's fast (200-500ms per call), cheap ($0.25 per million tokens), and surprisingly good at distilling technical content into decision-relevant summaries. The prompt asks for 100-200 tokens and it mostly delivers.

**A JSON manifest** sits alongside the SQLite store. It's the human-readable index: a list of what's archived, when, and how much was saved. Useful for debugging and for giving the agent a quick overview of its memory.

The codebase is about 750 lines across six modules. No deep magic anywhere.

## Index Keys and Why They Matter

One design decision I care about: the index key format.

Keys follow the `[namespace:topic-slug]` pattern:

```
[research:oauth-libs]
[debug:session-race]
[project:schema-v2]
[task:step-3-results]
```

This matters because the key appears in the working context summary. The agent reads it directly. A key like `[debug:session-race]` tells the agent: "I have a debug session about a race condition. I can get the full trace if I need it."

That's different from an opaque UUID or an auto-incremented integer. The agent can reason about what it has archived. It can decide whether `read_experience("[debug:session-race]")` is worth the tool call.

Namespacing also keeps memories organized as tasks grow complex. Research findings, debug sessions, project notes, and task results stay cleanly separated.

## The Numbers

I ran a benchmark simulating five large tool responses accumulated over a long task:

| Step | Baseline Tokens | Memex Tokens | Reduction |
|------|----------------|--------------|-----------|
| 1    | 2,660          | 109          | 96%       |
| 2    | 5,132          | 199          | 96%       |
| 3    | 8,138          | 284          | 97%       |
| 4    | 10,943         | 363          | 97%       |
| 5    | 13,502         | 454          | 97%       |

Final context: 13,502 tokens (baseline) vs. 454 tokens with Memex. 97% reduction.

The compression ratio holds constant as context grows. Each new piece of content compresses independently, so there's no degradation over time. The context overhead for Memex's own indexed summaries stays roughly linear: about 90-100 tokens per archived experience.

And because recovery is lossless, the agent doesn't lose anything. It just doesn't have to hold everything in its head at once.

## Show Me the Code

Here's the full usage pattern, the way an agent would use it:

```python
from memex.tools import compress_experience, read_experience

# Agent receives a verbose tool response
oauth_research = """
Evaluated OAuth2 libraries for FastAPI integration:

requests-oauthlib v1.3.1 (3,200 stars)
  - Synchronous only, no async support
  - Basic OAuth1 and OAuth2 flows
  - No built-in PKCE support
  - Last updated: 2023

authlib v1.3.0 (4,800 stars)
  - Full async support with httpx
  - JWT, JWK, JWE built in
  - PKCE required by spec, fully supported
  - Actively maintained, updated 2024

Recommendation: authlib. The async support and JWT integration
are essential for our FastAPI stack. requests-oauthlib is
synchronous and missing PKCE.
"""  # ~350 tokens

# Compress: archives to SQLite, returns ~100-token summary
indexed = compress_experience(
    content=oauth_research,
    index_key="[research:oauth-libs]",
    context="OAuth2 library comparison for FastAPI auth module",
)
# indexed is now ~100 tokens — use this in working context

print(indexed)
# [research:oauth-libs]
# Summary: Recommend authlib: async, JWT built-in, PKCE required.
#          requests-oauthlib rejected (sync-only, no PKCE).
# Archived: 2026-03-09T14:30:00Z | Tokens saved: 287

# ... many tool calls later ...

# Agent needs to verify the recommendation before writing code
full_research = read_experience("[research:oauth-libs]")
assert full_research == oauth_research  # lossless
```

The SQLite schema is straightforward:

```sql
CREATE TABLE experiences (
    key                  TEXT PRIMARY KEY,
    full_content         TEXT NOT NULL,
    summary              TEXT,
    token_count_original INTEGER DEFAULT 0,
    token_count_summary  INTEGER DEFAULT 0,
    metadata             TEXT DEFAULT '{}',
    archived_at          TEXT NOT NULL
);
```

One table. Seven columns. The `key` column is the primary key, so lookups are O(log n). The `full_content` column stores the exact original. Lossless recovery is just `SELECT full_content WHERE key = ?`.

## The Soft Trigger System

Memex also ships a `ContextTriggers` class that monitors context size and advises when to compress:

```python
from memex.triggers import ContextTriggers

triggers = ContextTriggers(soft_threshold=4000, hard_threshold=8000)
advice = triggers.check_triggers(working_context)

if advice.should_compress:
    print(advice)
    # [memex:triggers] COMPRESS RECOMMENDED:
    # Context at 4,247 tokens (soft threshold: 4,000)
    # 3 segments exceed 500 tokens
```

I'll be honest: this is half-finished. The trigger logic works, but it's not integrated into `compress_experience` itself. You have to call it manually and act on the advice. A future version should wire this up automatically, with an `auto_compress=True` option for agents that want hands-off memory management.

The heuristics are also simpler than the paper's RL-trained policies. The paper trains the agent to know exactly when compression is worth the cost. The trigger system here just watches thresholds. It's less optimal. It works.

## What Works, What Doesn't

**What works well:**

The core compress/read loop is solid. 32/32 tests pass. The lossless roundtrip is verified for unicode, special characters, and large content. The compression ratios are real and consistent. The graceful fallback to mock summaries when Bedrock is unavailable means demos run without AWS credentials.

The code quality is genuinely clean. Clear separation of concerns, type hints throughout, sensible error handling. The code reviewer scored it A (Excellent), zero critical bugs.

**Where it needs work:**

Thread safety is the big one. Memex uses module-level singletons. Multiple threads calling `compress_experience()` concurrently will race on initialization. For single-agent use, this is fine. For multi-threaded agents, instantiate separate `ExperienceStore` instances per thread or add external locking. This limitation is documented now, but it's a real gap.

Token counting is rough. The heuristic is `len(text) // 4` characters per token. That's accurate for English prose, but it can be off by 20-40% for code or CJK text. The reported compression ratios in the stats and benchmark use this estimate. They're approximately right. Adding `tiktoken` as an optional dependency would fix this.

The triggers module has no tests. 111 lines of threshold logic, zero tests. That's the most notable gap in an otherwise well-covered codebase. It's on the list.

And the hard-coded AWS region (`us-east-1`) in the Bedrock client is a simple thing to fix. If you're deploying in another region, set `AWS_REGION` in your environment and it works. The code was updated to read that env var.

## Configuration

```
MEMEX_DB_PATH         memex.db              SQLite database path
MEMEX_MANIFEST_PATH   memex_manifest.json   JSON manifest path
AWS_REGION            us-east-1             AWS region for Bedrock
```

Three environment variables. That's the full configuration surface for a default deployment.

## The Broader Pattern

What I like about this project is that it's a small, composable piece of infrastructure. Memex doesn't try to be a complete agent framework. It's a memory primitive.

Two tools. One SQLite file. A clean key convention.

An agent that uses Memex can work on tasks that would normally overflow its context window. It archives findings as it goes. It reads them back when it needs them. The context stays compact. The history stays complete.

That's the core insight from the paper: the right abstraction for long-horizon agents isn't a bigger context window. It's a way to move information between working memory and external memory on demand, with lossless recovery. The RL-trained version optimizes the decision-making. The heuristic version gets you 80% of the benefit with 5% of the complexity.

## What's Next

A few things on the roadmap:

**Trigger integration.** Wire `ContextTriggers` into the tools API so agents can set `auto_compress=True` and not think about it.

**Tiktoken support.** Optional dependency for accurate token counting. Keeps the default install lightweight.

**A CLI for inspection.** `memex list`, `memex read [key]`, `memex stats`. Right now, debugging requires writing Python. That's annoying.

**Semantic search.** `search_experiences("OAuth authentication")` without knowing the exact key. Store embeddings in the manifest, add a vector similarity search. Useful for long-running agents with many archived experiences.

**Schema migrations.** The v0.1 schema is good. V0.2 will probably add columns. There's no migration system yet. Before this ships as a library, that needs to exist.

## Try It

The project is part of the Protogenesis series. If you're building long-horizon agents and hitting context limits, the pattern is worth understanding even if you build your own implementation.

```bash
git clone <repo>
cd memex-agent
./run.sh
```

Falls back to mock summaries if Bedrock is unavailable. You can see the full compress/read cycle without AWS credentials.

```bash
python benchmark.py
```

Runs the token comparison benchmark. Baseline vs. Memex across five accumulated tool responses.

The core idea is simple enough to implement from scratch in an afternoon. Two tools, one SQLite table, a summarization call. If you're using a different LLM or a different storage backend, the pattern adapts easily.

Long-horizon agents need memory. Not truncation, not running summaries — actual memory, with lossless recall. This is a solid starting point for building that.

---

*Built during Protogenesis Week 10. Memex is named after Vannevar Bush's 1945 vision of a memory extension device for humans. Turns out the same idea is useful for AI agents, 80 years later.*
