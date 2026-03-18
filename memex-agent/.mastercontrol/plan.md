# Plan: Memex

## Phases (from requirements)

### Phase 1: SQLite KV Store + Index Manifest
- Schema design: `experiences` table (key, full_content, metadata JSON, created_at)
- CRUD layer: store, retrieve, delete, list
- JSON manifest: maps index keys → store location + summary + token_count + archived_at

### Phase 2: Compression Engine
- Input: verbose content string + index key + optional context
- Haiku 4.5 call: produce ~100-200 token summary
- Store original in SQLite
- Update JSON manifest
- Return: formatted index entry for agent context

### Phase 3: Retrieval Engine
- Input: index key string
- Manifest lookup → SQLite fetch
- Return full original content (lossless)

### Phase 4: Agent Tools
- `compress_experience(content, index_key, context=None)` — clean schema/docstring for LLM tool use
- `read_experience(index_key)` — clean schema/docstring for LLM tool use
- Tool registration pattern (works with Anthropic tool-use API)

### Phase 5: Soft Triggers
- Context size tracking (token counter utility)
- Threshold alert mechanism (agent-visible context size stats)

### Phase 6: CLI Demo + Benchmarking
- Multi-step research task demo (with and without Memex)
- Token usage comparison table
- Quality comparison (pass/fail on key facts)

### Phase 7: README
- Architecture diagram (reproduce from requirements)
- Installation / usage
- Benchmark results from Phase 6

## Order of Execution
Dispatch all phases to Claude Code in a single session with full requirements doc.
Claude Code to read requirements, flag ambiguities in README, then build.
