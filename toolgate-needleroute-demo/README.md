# ToolGate × NeedleRoute — Combined Pipeline Demo

A self-contained demonstration of **ToolGate** and **NeedleRoute** working together as a unified MCP tool selection pipeline.

## What This Shows

The demo simulates a realistic scenario: an AI agent has access to **50 MCP tools** across 10 categories. Each query runs through three approaches for comparison:

| Approach | How it works | Token cost |
|----------|-------------|------------|
| **No filtering** (baseline) | All 50 tools sent to LLM every call | 100% |
| **ToolGate only** | Semantic search → top-10 relevant tools | ~80% reduction |
| **ToolGate + NeedleRoute** | Semantic filter → Needle model picks final tool → escalate if unsure | ~90%+ reduction |

## Pipeline Architecture

```
User Query
    │
    ▼
┌─────────────────────────────────────┐
│ Stage 1: ToolGate                   │
│ • Sentence-transformer embeddings   │
│ • FAISS cosine similarity           │
│ • 50 tools → top-10                 │
│ • Latency: ~5-15ms                  │
└─────────────────────────────────────┘
    │ top-10 tools
    ▼
┌─────────────────────────────────────┐
│ Stage 2: NeedleRoute                │
│ • 26M-param Needle model            │
│ • Contrastive head scoring          │
│ • Confidence = top-1 vs top-2 gap   │
│ • Latency: ~2-8ms                   │
└─────────────────────────────────────┘
    │
    ├── High confidence → ✓ Selected tool
    │
    └── Low confidence → Escalation
                          ┌────────────────────────┐
                          │ Frontier model          │
                          │ (Claude Haiku 4.5)      │
                          │ Only over 10 tools!     │
                          └────────────────────────┘
```

## Running

```bash
python demo.py
```

No external dependencies required. The demo uses mock models that simulate the behavior of:
- **sentence-transformers/all-MiniLM-L6-v2** (embedding model)
- **Cactus-Compute/needle** (26M-param tool selection model)
- **Claude Haiku 4.5** (frontier model for escalation)

The mocks produce deterministic, semantically-meaningful results by encoding category awareness and keyword matching into the embedding space.

## Output

The demo produces a rich terminal output with:
- **Architecture diagram** — visual pipeline explanation
- **Query-by-query results** — each test case with selections and scores
- **Comparison table** — tokens, accuracy, latency across approaches
- **Cost analysis** — projected savings at 10k requests/day
- **Escalation analysis** — when and why the frontier model is needed
- **Key insights** — distilled takeaways

## Projects Used

- **[ToolGate](../toolgate/)** — MCP proxy that uses semantic search (sentence-transformers + FAISS) to filter tools by relevance
- **[NeedleRoute](../needleroute/)** — MCP routing proxy that uses a 26M-parameter Needle model for tool selection with confidence-based escalation

## Key Results (typical run)

- **~80% token reduction** from ToolGate filtering alone
- **~90%+ token reduction** with full pipeline
- **<1ms overhead** per query (mock models; real models add ~20-50ms total)
- **~85-95% accuracy** without any frontier model calls
- **Only ~15-25% of queries** escalated to expensive model
- Escalation uses **10 tools** context instead of 50 → cheaper even when escalating

---

*Part of the [ProtoGenesis](https://github.com/protogenesis) project family.*
