# Brief: xMemory — Beyond RAG for Agent Memory

## Source
Protogenesis W10 | Score: 4.0 | Request: `request-w10-xmemory.json`
Requirements: `~/.openclaw/shared/builder-pipeline/requirements/2026-03-09-beyond-rag-memory.md`
Research: `~/.openclaw/shared/builder-pipeline/research/2026-03-09-beyond-rag-memory.md`

## Summary
Hierarchical memory retrieval: organizes conversation history into 4 levels (messages → episodes → semantics → themes). Top-down retrieval instead of flat vector similarity. Solves redundancy collapse where RAG returns near-duplicate results from coherent conversation streams.

## Stack
- Python 3.11+
- Haiku 4.5 (amazon-bedrock/global.anthropic.claude-haiku-4-5-20251001-v1:0) — hierarchy construction
- Sonnet 4.6 (amazon-bedrock/global.anthropic.claude-sonnet-4-6) — retrieval/reranking
- SQLite — 4-level hierarchy storage
- boto3 bedrock-runtime (NOT anthropic SDK)
- No vector DB

## Key Constraints
- Incremental updates (no full rebuild on new messages)
- Episode boundaries by conversation session
- LLM reranking over submodular optimization (simpler for v1)
- Simpler Haiku clustering for themes

## Acceptance Criteria
1. 50+ messages → grouped episodes → deduplicated semantics → coherent themes
2. Query returns diverse, non-redundant context; ≥40% fewer tokens than naive top-k
3. Incremental update processes only new messages into existing hierarchy
4. Multi-fact query spans multiple themes (no collapse into one neighborhood)

## Paper
https://arxiv.org/abs/2602.02007 (ICML 2026)
