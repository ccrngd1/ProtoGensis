# Status: xmemory

## Current State: ✅ COMPLETE (v1.1 — fixes applied)

## Timeline
- 2026-03-09 21:15 UTC — Dispatched
- 2026-03-09 21:26 UTC — Initial build complete (~11 min), 45/45 tests passing
- 2026-03-14 01:46 UTC — Fix request received (request-xmemory-fixes.json)
- 2026-03-14 01:47 UTC — All fixes applied, 50/50 tests passing (5 new)

## Fixes Applied (2026-03-14)
### Critical/High
- `semantics.py` + `store.py` — Added `update_semantic()` to MemoryStore; dedup now persists source_episode_ids updates (data loss bug fixed)
- `semantics.py` — `is_duplicate()` now returns `(bool, matching_fact)` tuple; uses LLM verdict to drive merge, not exact string match
- `retrieval.py` — Fallback cascade added: themes → episodes → messages when hierarchy partially built (no more silent empty results)
- `retrieval.py` — `match_themes()` now distinguishes LLM "no relevant themes" (returns []) from parse failure (falls back to top_k)

### Notable
- `_llm.py` — `_call_with_retry()` wrapper with exponential backoff for ThrottlingException / transient errors
- `store.py` — N individual commit() calls in add_messages() consolidated into single batched transaction
- `models.py` — `datetime.utcnow()` → `datetime.now(timezone.utc)` throughout

### Documentation + Infrastructure
- `README.md` — Benchmark caveat added: baseline uses recency not semantic similarity
- `README.md` — venv-based installation instructions; global pip refs removed
- `run.sh` (NEW) — Executable venv setup + benchmark runner

## Test Results
- **50/50 passing** (was 45; +5 new tests covering each bug fix)

## Blockers
None

---
*Updated: 2026-03-14 01:47 UTC*
