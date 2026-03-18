# Brief: Google Always-On Memory Agent (Bedrock Edition)

## Source
Protogenesis W10 | Score: 4.7 | Request: `request-w10-memory-agent.json`
Requirements: `~/.openclaw/shared/builder-pipeline/requirements/2026-03-09-google-memory-agent.md`
Research: `~/.openclaw/shared/builder-pipeline/research/2026-03-09-google-memory-agent.md`

## Summary
Persistent memory agent: three specialist sub-agents (Ingest, Consolidate, Query) sharing a SQLite store. No vector DB — LLM reads memories directly. Consolidation runs on a timer like a "sleeping brain."

## Stack
- Python 3.11+
- Haiku 4.5 via Bedrock (all operations)
- SQLite (memory.db)
- FastAPI (HTTP API)

## Reference Repos
- https://github.com/GoogleCloudPlatform/generative-ai/tree/main/gemini/agents/always-on-memory-agent
- https://github.com/Shubhamsaboo/always-on-memory-agent

## Key Constraints
- No vector DB, no embeddings
- Single-user, text-only for v1
- Consolidation timer-driven (not event-driven)
- boto3 bedrock-runtime (NOT anthropic SDK)

## Acceptance Criteria
1. Ingest text → extract memory (summary, entities, topics, importance)
2. Consolidation on 5+ unconsolidated memories → connections + insights
3. Query → synthesized answer with source citations
4. Cross-session topics surface consolidation insights in query results
