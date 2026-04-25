# I Added 50 Tools to My AI Agent and It Got Dumber. Here's the Fix.

**TL;DR**: I built ToolGate, an MCP proxy that uses semantic search to filter AI agent tools. It reduces context bloat by 60%+ while maintaining 85%+ precision on synthetic benchmarks. Open source and ready to try.

---

## The Problem: When More Tools = Less Intelligence

I run CABAL, a distributed multi-agent system with 9 specialized orchestrators (Main, REHOBOAM, LEGION, PreCog, DAEDALUS, TheMatrix, MasterControl, TACITUS, HAL9000). Each agent has access to different tool sets through MCP servers. Like many AI developers, I kept adding MCP servers to give the system more capabilities:

- Filesystem operations (read, write, search)
- Git management (status, commit, diff, log)
- HTTP requests
- Database queries
- Text processing utilities
- Date/time functions

By the time I hit 6+ MCP servers with 50+ tools, something strange happened: **my agents got worse**.

Tasks that used to work smoothly started failing. Claude would:
- Use the wrong tools for simple tasks
- Miss obvious tools that were right in front of it
- Take longer to respond
- Sometimes just... give up

What was going on?

## The Root Cause: Context Window Bloat

Every time Claude sees a `tools/list` request, it receives the full catalog of available tools. With 50 tools, that's:

- 50 tool names
- 50 descriptions (averaging 100-200 chars)
- 50 JSON schemas (with parameters, types, requirements)

Let me show you what a **single tool** looks like in Claude's context:

```json
{
  "name": "read_file",
  "description": "Read the contents of a file from the filesystem. Supports text and binary files. Can read specific line ranges or entire file.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Path to the file"
      },
      "encoding": {
        "type": "string",
        "description": "File encoding (default: utf-8)"
      }
    },
    "required": ["path"]
  }
}
```

That's **~350 tokens** for ONE tool. Multiply by 50 tools = **~17,500 tokens** just for the tool catalog.

On every single request.

And it gets worse:
- 90% of those tools aren't relevant to the current task
- The more tools you add, the harder it is for Claude to pick the right one
- You're burning tokens that could be used for actual work

## The Research Backing

I'm not the only one who noticed this. A recent paper by Sadani and Kumar, "Tool Attention: Optimizing LLM Tool Usage through Attention Score Analysis" (arXiv:2604.21816), directly motivated this build. Their key finding: LLM attention scores over the tool catalog are heavily skewed. Relevant tools capture disproportionate attention, while irrelevant tools create noise that degrades selection accuracy. As catalog size grows, that noise compounds. The practical implication they surface is that retrieval-augmented tool selection, filtering the catalog before it hits the context window, should recover much of that lost precision.

That finding is the direct motivation for ToolGate: apply the same retrieval logic to tools that RAG applies to documents.

More broadly, research on tool-using language models shows:
- **Tool interference**: LLMs struggle with tool selection accuracy as catalog size increases
- **Context dilution**: Irrelevant tools in the context reduce task completion rates
- **Retrieval augmentation**: Semantic search over tools significantly improves performance

The insight is simple: just like RAG for documents, we need RAG for tools.

## The Solution: ToolGate

ToolGate is an MCP proxy that sits between your AI agent and your MCP servers. It:

1. **Indexes all tools** using semantic embeddings (sentence-transformers)
2. **Filters on every request** using FAISS similarity search
3. **Returns only relevant tools** (top-K based on query)
4. **Applies smart rules** (always-include, session continuity, etc.)

### Architecture

```
┌─────────────┐
│  AI Agent   │
│  (Claude)   │
└──────┬──────┘
       │ MCP stdio
       ▼
┌─────────────────────────────────────┐
│          ToolGate Proxy             │
│                                     │
│  ┌───────────────────────────────┐  │
│  │   Semantic Search             │  │
│  │   • sentence-transformers     │  │
│  │   • FAISS cosine index        │  │
│  │   • Real-time embedding       │  │
│  └───────────────────────────────┘  │
│                                     │
│  ┌───────────────────────────────┐  │
│  │   Gating Rules                │  │
│  │   • Pattern include/exclude   │  │
│  │   • Session boost (+15%)      │  │
│  │   • Top-K selection           │  │
│  └───────────────────────────────┘  │
│                                     │
│  ┌───────────────────────────────┐  │
│  │   Lazy Schema Loading         │  │
│  │   • Phase 1: Names only       │  │
│  │   • Phase 2: JIT schemas      │  │
│  └───────────────────────────────┘  │
└──────┬──────────────────┬───────────┘
       │                  │
       ▼                  ▼
┌─────────────┐    ┌─────────────┐
│ Filesystem  │    │     Git     │
│ MCP Server  │    │  MCP Server │
└─────────────┘    └─────────────┘
        ... + 4 more servers
```

### How It Works

**1. Index Build** (on startup):
- Connect to all upstream MCP servers
- Fetch complete tool catalog (50 tools)
- Embed each tool: `name + description` → 384-dim vector
- Build FAISS flat cosine index

**2. Query Processing** (on each listTools):
- Extract user query (last message)
- Embed query → 384-dim vector
- FAISS search → top-K similar tools (K=10)
- Apply gating rules:
  - Force-include patterns (`git_*` if querying about git)
  - Session boost (+0.15 similarity for recently used tools)
  - Force-exclude patterns (`dangerous_*`)

**3. Response** (two-phase lazy loading):
- **Phase 1** (listTools): Return name + truncated description (200 chars max)
- **Phase 2** (callTool): Fetch full schema JIT when tool is actually called

### Results from the Synthetic Benchmark

I built a synthetic benchmark with 50 realistic tools and 20 diverse queries. The catalog and queries are artificial, designed to stress-test semantic matching across tool categories. Here's what ToolGate achieves against that benchmark:

| Metric | Value | Status |
|--------|-------|--------|
| **Precision@10** | **85%+** | ✓ PASS |
| **Token Reduction** | **65%** | ✓ PASS |
| **Query Latency** | **<50ms** | ✓ PASS |

Let's break this down:

#### Token Reduction: 65% Savings

**Before ToolGate** (all 50 tools):
```
Total tokens: ~17,500
```

**After ToolGate** (top 10 relevant):
```
Total tokens: ~6,000
Token savings: ~11,500 (65%)
```

That's **11,500 tokens saved** on every single request. At Claude's pricing ($3/MTok input), that's:
- 1,000 requests = $34.50 → $12.00 (saving $22.50)
- 10,000 requests = $345 → $120 (saving $225)

But the real win isn't cost. It's accuracy.

#### Precision@10: Finding the Right Tools

Precision@10 measures: "Of the top 10 tools returned, how many are actually relevant?"

Test queries against the synthetic catalog:
- "Read a config file" → returns `read_file`, `parse_json`, `parse_yaml`
- "Show git status" → returns `git_status`, `git_log`, `git_diff`
- "Make HTTP request" → returns `http_get`, `http_post`, `parse_json`

**85%+ precision** means the right tools are consistently in the top 10, at least against these synthetic scenarios.

#### Latency: Fast Enough to Not Matter

- Index build: ~2 seconds (50 tools, cold start)
- Query embedding: ~10ms
- FAISS search: ~1ms
- Total overhead: **<50ms per request**

Negligible compared to Claude's response time (1-3 seconds).

## Implementation Deep Dive

### Semantic Embeddings

ToolGate uses `sentence-transformers/all-MiniLM-L6-v2`:
- **Size**: 22MB model
- **Speed**: 1000+ embeddings/second on CPU
- **Quality**: 384-dim embeddings, trained on semantic similarity

Each tool is embedded as:
```python
text = f"{tool.name}: {tool.description}"
embedding = model.encode(text)  # → [384] vector
```

Query embedding is identical:
```python
query = "read a file from disk"
query_embedding = model.encode(query)  # → [384] vector
```

### FAISS Similarity Search

FAISS (Facebook AI Similarity Search) provides fast vector search:

```python
# Build index (cosine similarity)
index = faiss.IndexFlatIP(384)  # Inner product
vectors = normalize(embeddings)  # L2 normalize for cosine
index.add(vectors)

# Search
query_vec = normalize(query_embedding)
distances, indices = index.search(query_vec, k=10)
# Returns top-10 most similar tools in <1ms
```

### Session Continuity

ToolGate tracks recently used tools (last 5 turns) and boosts their similarity score:

```python
if tool_name in recent_tools:
    score += 0.15  # 15% boost
```

This creates "sticky" tools. If you just used `git_commit`, it's more likely to appear again for related tasks.

### Gating Rules

You can override semantic search with patterns:

```yaml
gating:
  always_include:
    - "git_*"        # Always include git tools
    - "read_file"    # Critical tool
  always_exclude:
    - "delete_*"     # Dangerous operations
    - "drop_table"   # No thanks
```

This combines semantic search with explicit control.

## Using ToolGate

### Installation

```bash
pip install toolgate
```

### Configuration

Create `config.yaml`:

```yaml
upstream_servers:
  - name: filesystem
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/allowed/path"]

  - name: git
    command: npx
    args: ["-y", "@modelcontextprotocol/server-git", "--repository", "/repo"]

gating:
  top_k: 10
  session_boost: 0.15
  always_include: ["git_*"]

metrics:
  enabled: true
  db_path: "~/.toolgate/metrics.db"
```

### Running

```bash
# Start the proxy
toolgate serve --config config.yaml
```

### Claude Desktop Integration

In your Claude Desktop config:

```json
{
  "mcpServers": {
    "toolgate": {
      "command": "toolgate",
      "args": ["serve", "--config", "/path/to/config.yaml"]
    }
  }
}
```

ToolGate replaces all your individual MCP servers with a single intelligent proxy.

## What the Benchmarks Suggest

I haven't run ToolGate in production long enough to have real numbers. These are design hypotheses grounded in the synthetic benchmark results and the Sadani/Kumar findings.

### What I Expect to Hold Up

**File operation clustering should work well in practice.** When you ask to "read config.yaml", the semantic search should return `read_file`, `parse_yaml`, `list_directory` as a cluster. The benchmark results suggest the embeddings have enough signal to group related tools correctly.

**Session continuity should reduce re-retrieval churn.** The 15% boost for recently used tools is deliberately small. If you `git_status`, then ask to "commit the changes", `git_commit` should naturally rank high anyway. The boost is a backstop, not the primary mechanism.

**The fail-safe fallback matters more than it sounds.** If embedding fails (network issue, OOM, etc.), ToolGate falls back to returning all tools. The agent degrades gracefully rather than breaking. That's a design priority, not an afterthought.

### Open Questions

The synthetic benchmark is a controlled environment. Real tool catalogs have messier descriptions, more semantic overlap between tools, and queries that aren't as cleanly scoped as "show git status." Here's what I actually need to find out:

1. **How does precision hold at K=10 with messier real catalogs?** 85% on synthetic is encouraging. Real-world catalogs may have more redundant descriptions that confuse the retrieval.

2. **Multi-intent queries.** Some tasks need tools from multiple categories ("read this file AND post the result to Slack"). Right now ToolGate embeds the query as a single vector. I expect this to be a weak spot.

3. **Description quality sensitivity.** The benchmark tools have clean, informative descriptions. Poorly described tools may not embed well and could get systematically missed.

The plan is to run this on CABAL for a few weeks and revisit these questions with real data.

### Future Work

1. **Multi-query embedding**: Query decomposition for multi-intent tasks.
2. **LLM-based query rewriting**: Expand "grab that config" to "read configuration file" before embedding.
3. **Tool usage analytics**: Track which tools actually get called to identify retrieval blind spots.
4. **Cross-server deduplication**: Multiple servers might provide `read_file`. ToolGate should handle that.

## The Bigger Picture

ToolGate is a small piece of a larger puzzle: making AI agents actually work at scale.

The Model Context Protocol is designed to be a universal interface for AI tools. But as the ecosystem grows (100+ MCP servers, 1000+ tools), we need **tool management infrastructure**:

- **Discovery**: Finding the right tools (ToolGate)
- **Composition**: Chaining tools together
- **Orchestration**: Multi-step tool workflows
- **Safety**: Preventing dangerous tool combinations
- **Monitoring**: Understanding what agents are doing

ToolGate addresses discovery. The rest is a separate problem.

## Try It Yourself

ToolGate is open source (MIT license) and lives as a module in the ProtoGensis monorepo:

```bash
# Clone
git clone https://github.com/ccrngd1/ProtoGensis

# Install
cd ProtoGensis
pip install -e ".[dev]"

# Run benchmark
pytest tests/ -v
python benchmark/run.py

# Expected results:
# Precision@10 >= 80%
# Token reduction >= 60%
# 40+ tests passing
```

The benchmark uses synthetic data (50 tools, 20 queries). You can also test with your real MCP servers:

```bash
toolgate serve --config your-config.yaml
```

## Conclusion

AI agents are only as good as their tools. But more tools does not equal a better agent.

ToolGate applies retrieval-augmented generation to tool selection. The synthetic benchmark results are solid. The theoretical motivation from Sadani and Kumar is sound. Whether it holds up in production is the next question.

The results so far:
- 65% token reduction on synthetic benchmarks
- 85%+ precision on synthetic benchmarks
- Under 50ms latency overhead
- Works today with any MCP server

If you're building with MCP, give it a try. I'd be curious whether the precision numbers hold on real-world tool catalogs.

---

**Links**:
- GitHub: [ccrngd1/ProtoGensis](https://github.com/ccrngd1/ProtoGensis)
- MCP: [modelcontextprotocol.io](https://modelcontextprotocol.io)
- Paper: Sadani & Kumar, "Tool Attention: Optimizing LLM Tool Usage through Attention Score Analysis" (arXiv:2604.21816)
- Benchmarks: Run `toolgate benchmark` to see for yourself

Built for the CABAL project.
