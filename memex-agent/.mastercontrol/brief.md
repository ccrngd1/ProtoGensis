# Brief: Memex — Indexed Experience Memory for Agents

## Source
Protogenesis W10 | Score: 4.2 | Request: `request-w10-memex.json`
Requirements: `~/.openclaw/shared/builder-pipeline/requirements/2026-03-09-memex-rl.md`
Research: `~/.openclaw/shared/builder-pipeline/research/2026-03-09-memex-rl.md`

## Summary
An indexed experience memory system for agents. Agents accumulate verbose tool responses in context — Memex lets them compress those to compact indexed summaries, then expand them back on demand.

Two agent tools:
- `compress_experience` — archive full content to SQLite KV, replace with indexed summary in context
- `read_experience(index)` — dereference an index key and return full archived content

## Stack
- Python 3.11+
- Haiku 4.5 (summarization/compression)
- Sonnet 4.6 (complex retrieval decisions)
- SQLite (KV experience store)
- JSON manifest (human-readable index)

## Key Constraints
- Agent-controlled compression (explicit tool calls, not automatic)
- Lossless retrieval (full-fidelity recovery)
- No RL training (heuristic triggers only for v1)
- Single-agent for v1 (no concurrent access)
- Index namespace: `[project:topic-slug]`

## Acceptance Criteria (abbreviated)
1. compress_experience: 3000-token content → archived + ~100-200 token summary returned
2. read_experience: exact original content returned (lossless)
3. 10 compressions → working context ≥60% smaller than baseline
4. Multi-step task quality equivalent to uncompressed execution

## Blog Angle
"Teaching My AI Agent to Remember Its Mistakes — Experience Replay for LLM Agents"

## Reference
Paper: https://arxiv.org/abs/2603.04257
