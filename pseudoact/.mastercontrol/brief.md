# Brief: PseudoAct — Pseudocode Planning for LLM Agents

## Source
Protogenesis W10 | Score: 3.8 | Request: `request-w10-pseudoact.json`
Requirements: `~/.openclaw/shared/builder-pipeline/requirements/2026-03-09-pseudoact.md`
Research: `~/.openclaw/shared/builder-pipeline/research/2026-03-09-pseudoact.md`

## Summary
Two-phase agent framework: Phase 1 synthesizes a pseudocode plan (with loops, conditionals, parallel blocks, fallbacks) using Sonnet 4.6. Phase 2 executes plan step-by-step via control-flow executor using Haiku 4.5. Replaces reactive ReAct with structured, inspectable planning.

## Stack
- Python 3.11+
- Sonnet 4.6 (amazon-bedrock/global.anthropic.claude-sonnet-4-6) — plan synthesis
- Haiku 4.5 (amazon-bedrock/global.anthropic.claude-haiku-4-5-20251001-v1:0) — step execution
- Python AST / custom parser for pseudocode
- boto3 bedrock-runtime (NOT anthropic SDK)

## Key Constraints
- Bounded loops mandatory (max_iterations on every loop)
- Plans saved to disk for inspection
- No dynamic replanning for v1 (fail if plan fails)
- Parallel blocks serialized for v1
- ReAct baseline for comparison

## Acceptance Criteria
1. Plan synthesis produces control flow (conditional or loop) referencing only available tools
2. Executor runs plan in order, passes variables between steps, enforces loop bounds
3. PseudoAct uses ≥30% fewer tokens than ReAct on same 10 tasks
4. Loop max_iterations bound exits cleanly to fallback
