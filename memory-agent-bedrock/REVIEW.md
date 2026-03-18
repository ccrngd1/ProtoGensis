# Code Review: memory-agent-bedrock

Reviewed: 2026-03-13 | Reviewer: subagent (senior engineer perspective)

---

## Summary

Clean, well-scoped implementation of a Google-inspired always-on memory agent adapted for AWS Bedrock. The architecture is sound, the code is readable, and all 20 tests pass. However, there are two critical runtime bugs that will cause immediate failures on a real AWS deployment — the default Bedrock model ID is invalid, and the README's context window math is wrong in a way that will cause silent failures at scale. A handful of moderate issues around async correctness, atomicity, and error handling are also worth fixing before this goes anywhere near production.

---

## What It Does

Three-agent memory system backed by SQLite (no vector DB):

1. **IngestAgent** — sends raw text to Claude Haiku via Bedrock, gets back structured JSON (`summary`, `entities`, `topics`, `importance 0-1`), persists to `memories` table.
2. **ConsolidateAgent** — runs on a background timer (default 5 min). When 5+ unconsolidated memories exist, calls Haiku to find cross-cutting connections and generate insights. Results go to `consolidations` table; processed memories are marked `consolidated=True`.
3. **QueryAgent** — reads *all* memories + consolidations into a single Haiku prompt, returns a synthesized answer with `[memory:ID]` citations.

Exposed via FastAPI (`/ingest`, `/query`, `/status`, `/consolidate`) and a CLI (`cli.py`). The pitch is that Haiku's 200K context window replaces vector retrieval for personal-scale memory stores.

---

## Run Results

**Tests:** 20/20 pass, no failures.

```
pytest tests/ -v
========================= 20 passed, 12 warnings in 1.61s =========================
```

**Warnings:** 12 `DeprecationWarning` from `on_event('startup')` usage in `test_api.py`. FastAPI deprecated `on_event` in favor of lifespan handlers. Not breaking, but noisy.

**Dependency state:**
- `boto3` installed: `1.26.27` — required `>=1.34.0`. The `bedrock-runtime` service wasn't available until `~1.28`. Tests pass only because boto3 is mocked entirely. Running against real AWS with the installed version would fail at import/client-creation time.
- `httpx` installed: `0.23.3` — required `>=0.27.0`. Tests pass because the internal version used by FastAPI's TestClient is compatible enough, but this is a stated-vs-actual mismatch.
- `pytest-asyncio` listed in requirements but not used anywhere — no async tests exist.

**Runtime (no real AWS):** The FastAPI app imports and initializes cleanly. The CLI works for local DB operations. Nothing was tested against real Bedrock due to no AWS credentials in environment.

---

## Architecture

Generally good. The layering is clean and the separation of concerns is appropriate for the project scope:

```
API / CLI → Orchestrator → [IngestAgent, ConsolidateAgent, QueryAgent]
                                          ↓
                                   MemoryStore (SQLite)
                                          ↓
                               bedrock_client (boto3 singleton)
```

**What works well:**
- Background consolidation timer is implemented properly: daemon thread, `threading.Event` for clean shutdown, `stop_background_consolidation()` hooked into FastAPI's lifespan cleanup.
- Pydantic v2 models with proper field constraints and serializers.
- `MemoryStore` is a clean CRUD layer. All SQL uses parameterized queries — no injection surface.
- Fallback behavior in `IngestAgent.ingest()` when the LLM returns malformed JSON: falls back to raw text as summary rather than crashing.
- README is honest about the tradeoffs and the scalability ceiling. That section is genuinely good.

**Structural concerns:**
- There's no `pyproject.toml`, no `setup.py`, no packaging at all. Fine for a demo/internal tool but worth noting if this is meant to be redistributed.
- No `conftest.py` — shared fixtures are duplicated across test files (`_make_store` appears in both `test_agents.py` and is reimplemented as a pytest fixture in `test_store.py`).

---

## Code Quality

**Good:**
- Consistent style throughout. `from __future__ import annotations` used everywhere for forward references.
- Logging is used properly (module-level `getLogger(__name__)`) rather than `print()`.
- `mark_consolidated` correctly builds `?`-parameterized placeholders for `IN` clauses rather than string-formatting IDs.
- `_parse_json` in both `ingest.py` and `consolidate.py` defensively strips markdown fences before parsing. Duplicated logic — should be a shared utility in a `utils.py` — but at least it's correct in both places.
- CLI is straightforward and covers all agent operations.

**Bad:**
- `datetime.utcnow()` is deprecated in Python 3.12 and will emit `DeprecationWarning`. Should be `datetime.now(timezone.utc)`. Fine on 3.11 but this will become a warning wall when 3.12 is adopted.
- `list` is used as a type annotation in `IngestResponse` and `QueryResponse` (bare `list` without type param). Minor, but these Pydantic models are exposed on the API boundary — they should be `list[str]`.
- `cmd_consolidate` in `cli.py` calls `result.connections[:200] + "..."` unconditionally — this crashes if `connections` is an empty string (which is possible when the LLM returns `{}`).

---

## Issues Found

### Critical

**1. Default Bedrock model ID is invalid**

`bedrock_client.py`:
```python
MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID",
    "amazon-bedrock/global.anthropic.claude-haiku-4-5-20251001-v1:0",
)
_RAW_MODEL_ID = MODEL_ID.removeprefix("amazon-bedrock/")
# Result: "global.anthropic.claude-haiku-4-5-20251001-v1:0"
```

`global.` is not a valid Bedrock model ID prefix. Valid options are:
- Direct: `anthropic.claude-haiku-4-5-20251001-v1:0`
- Cross-region inference profile: `us.anthropic.claude-haiku-4-5-20251001-v1:0`

Any user running this with the default env var will get an immediate Bedrock API error on their first real call. The tests all mock boto3 so this never surfaces.

**Fix:** Change the default to `us.anthropic.claude-haiku-4-5-20251001-v1:0` and update the README's env var table.

---

**2. Context window claim in README is wrong; query limit is dangerous**

README states: *"~5,000 memories × 100 tokens each fits in Haiku's 200K context window"*

This is incorrect on both counts. Each memory in the query prompt includes the UUID (36 chars), summary (typically 50-200 words), entities list, topics list, and importance score. Realistically ~200-400 tokens per memory. At 300 tokens/memory: **200K / 300 ≈ 666 memories max** before hitting the context limit.

The `QueryAgent` uses `list_memories(limit=2000)`. At 300 tokens/memory, 2000 memories = ~600K tokens — 3× the model's context window. The API call will fail with a "prompt too long" error once a user accumulates a few hundred memories.

Consolidation also sends **all** unconsolidated memories in a single call with no batching. A first-time user who imports 200+ memories will hit this immediately.

**Fix:** 
- Correct the README math.
- Add a configurable hard cap in `QueryAgent` (~600 memories is a safer default).
- Add chunked batching in `ConsolidateAgent` (process N memories per cycle, not all of them).

---

### Moderate

**3. Blocking I/O in async route handlers**

All three routes (`/ingest`, `/query`, `/consolidate`) are `async def` but call synchronous boto3 network I/O via `orc.ingest()`, `orc.query()`, and `orc.consolidate()`. boto3 is entirely synchronous. This blocks the FastAPI event loop for the full round-trip duration of each Bedrock API call (typically 1-10 seconds for Claude).

Under any meaningful load, this will stall all other in-flight requests.

**Fix:**
```python
import asyncio

@router.post("/ingest", ...)
async def ingest(body: IngestRequest, request: Request) -> IngestResponse:
    orc = _get_orc(request)
    memory = await asyncio.to_thread(orc.ingest, body.text, source=body.source)
    ...
```

---

**4. Consolidation is not atomic**

In `consolidate.py`:
```python
self.store.add_consolidation(consolidation)   # commits
self.store.mark_consolidated([m.id for m in memories])  # separate commit
```

If the process crashes, gets OOM-killed, or the SQLite connection drops between these two commits, you end up with a `consolidations` record pointing to memories that are still marked `consolidated=False`. The next consolidation run will re-process those memories and produce a duplicate consolidation. This is a data consistency bug.

**Fix:** Wrap both operations in a single SQLite transaction:
```python
with self.store.conn:  # transaction context
    self.store.add_consolidation(consolidation)
    self.store.mark_consolidated([m.id for m in memories])
```

---

**5. `Memory()` construction is outside the LLM try/except**

In `ingest.py`:
```python
try:
    raw = invoke(prompt, ...)
    data = _parse_json(raw)
except Exception as exc:
    logger.warning("LLM extraction failed; using fallback.")
    data = {}

memory = Memory(  # ← OUTSIDE try/except
    importance=float(data.get("importance", 0.5)),  # if LLM returns 1.5 or "high"...
    ...
)
```

If the LLM returns `importance: 1.5`, `float()` succeeds but `Memory()` raises a `ValidationError` (Pydantic enforces `le=1.0`). This propagates unhandled → 500 from the `/ingest` route. Same issue if LLM returns a non-numeric string for importance.

**Fix:** Clamp the value before construction:
```python
importance = max(0.0, min(1.0, float(data.get("importance", 0.5))))
```
Or move the `Memory()` construction inside the try/except.

---

**6. Global boto3 client has a thread-safety race condition**

```python
_client: Optional[Any] = None

def get_client() -> Any:
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=region)
    return _client
```

The check-then-set is not atomic. If the consolidation background thread and a request handler thread both call `get_client()` simultaneously before it's initialized, you could create two clients. boto3 clients are generally safe to use concurrently but creating two at startup is wasteful and technically a race. Use `threading.Lock()` for initialization.

---

### Minor

**7. `on_event('startup')` deprecated in test_api.py**

The test fixture uses `@app.on_event("startup")` to inject the mock orchestrator. FastAPI deprecated this API in 0.93 in favor of lifespan handlers. The 12 deprecation warnings in the test output come from here. The fix is to use `app.state.orchestrator = mock_orchestrator` directly via the TestClient's `app` reference (which the fixture already does on the next line — the `on_event` registration is actually redundant).

**8. No input length validation**

`IngestRequest.text` has no `max_length` constraint. A caller could POST 10MB of text which would be sent verbatim to Bedrock — expensive and likely to exceed the model's prompt limit. Add `Field(max_length=50_000)` or similar.

**9. No delete or update in `MemoryStore`**

The store is fully append-only. There's no way to correct a wrong memory, remove sensitive content, or prune old memories. For a personal data store, this matters — users will expect some ability to manage what's been ingested. Not a bug, but a notable gap.

**10. Logging never configured**

All agents use `logging.getLogger(__name__)` but neither `api/main.py` nor `cli.py` calls `logging.basicConfig()` or sets up any handler. In the API server, consolidation errors logged to the background thread's logger will silently vanish. The CLI will never show any log output.

**11. `pytest-asyncio` is an unused dependency**

No tests use `@pytest.mark.asyncio` or `async def test_*`. Remove it from `requirements.txt`.

**12. Duplicate `_parse_json` function**

Identical function exists in both `agents/ingest.py` and `agents/consolidate.py`. Extract to `agents/utils.py`.

---

## Recommendations

**Must fix before real AWS use:**
1. Fix the default model ID (`global.` → `us.`).
2. Cap `QueryAgent`'s memory limit to ~600 and add batching to `ConsolidateAgent`. The "5,000 memories" claim needs to be corrected in the README or the architecture needs to match it (e.g., filter by relevance/importance before stuffing the context window).

**Should fix:**
3. Wrap consolidation's two-step write in a single transaction (atomicity).
4. Move `Memory()` construction inside the try/except or clamp `importance`.
5. Wrap boto3 calls with `asyncio.to_thread()` in async routes.

**Worth doing:**
6. Add a threading lock around the `get_client()` singleton.
7. Add `logging.basicConfig()` at startup in both `api/main.py` and `cli.py`.
8. Replace `datetime.utcnow()` with `datetime.now(timezone.utc)`.
9. Fix the deprecated `on_event` in test fixtures.
10. Add `max_length` to `IngestRequest.text`.
11. Add delete/update endpoints — at minimum `DELETE /memory/{id}`.
12. Extract `_parse_json` to a shared utility.

**Not urgent but notable:**
- The README is good but the scalability section needs an honest correction: the ceiling is ~600-700 memories for reliable query performance with the current approach, not 5,000. The fix (filtering by importance or recency before building the query prompt) would actually make the architecture more interesting to write about.
