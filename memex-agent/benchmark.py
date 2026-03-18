#!/usr/bin/env python3
"""
benchmark.py — Compare token usage with and without Memex.

Simulates a multi-step research task where an agent accumulates tool
responses. Measures working context size at each step:
  - Baseline: all content stays in context
  - Memex:    large responses compressed to indexed summaries

Usage:
    python benchmark.py
"""

import os
import sys
import tempfile
from typing import Callable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memex.utils import estimate_tokens

# Simulated tool responses (long content that an agent might accumulate)
TOOL_RESPONSES = [
    (
        "[research:oauth-libs]",
        "OAuth library evaluation",
        """Evaluated requests-oauthlib (stars:3200, sync-only), authlib (stars:4800, async+JWT+OIDC),
python-social-auth (stars:2900, framework-coupled). Authlib selected: native async for FastAPI,
built-in JWT/OIDC, PKCE support. Benchmarks: authlib 156ms, requests-oauthlib 142ms, social-auth 201ms.
Implementation plan: add authlib, implement AuthManager, Redis token store with TTL=expires_in,
refresh hook on 401. Security: PKCE mandatory, log sanitisation, secret rotation OPS-441.
References: authlib docs, RFC 6749, RFC 7636, PR #213. """ * 20,
    ),
    (
        "[research:db-schema-v2]",
        "Database schema migration plan",
        """Schema v2 migration analysis. Current: 47 tables, 2.3M rows, avg query 420ms.
Target: normalise user_events (currently 1.2M rows, no FK constraints), add indices on
(user_id, created_at), (session_id), (event_type, created_at). Migration: blue-green,
3-phase: 1) add new columns, 2) backfill, 3) swap. Estimated downtime: 0 (online DDL).
Risk: backfill on 1.2M rows takes ~4h on prod RDS; schedule maintenance window. 
Rollback: revert migration file; old columns untouched. Query improvement expected: 60-80%.
Affected services: analytics-api (12 queries), dashboard (8 queries), export-worker (3 queries).
Timeline: 2 weeks. Owner: @db-team. Jira: DB-1842. """ * 15,
    ),
    (
        "[debug:race-condition-session]",
        "Session race condition root cause",
        """Root cause analysis: race condition in SessionManager.get_or_create(). 
Two concurrent requests for same user_id both read None → both INSERT → IntegrityError.
Fix: SELECT FOR UPDATE on user_id, or UPSERT with ON CONFLICT DO UPDATE.
Reproduction: ab -c 50 -n 500 /api/session — reliably triggers in ~200ms window.
Stack trace: session.py:142 → db.py:89 → psycopg2 IntegrityError: duplicate key user_id.
Mitigation deployed: application-level lock (threading.Lock) — works for single-instance.
Proper fix: DB-level UPSERT. PR #287. Estimated impact: affects ~0.3% requests under load.
Load test results before fix: 47 errors/500 requests. After: 0 errors/500 requests. """ * 18,
    ),
    (
        "[research:caching-strategy]",
        "Caching strategy recommendation",
        """Cache analysis for API endpoints. Current: no caching, all requests hit DB.
Profiling: top 5 endpoints by load — GET /users/{id} (34%), GET /products (28%),
GET /stats (18%), GET /search (12%), POST /events (8%). 
Recommendation: Redis cache for /users/{id} (TTL=5min, invalidate on update),
/products (TTL=1h, invalidate on write), /stats (TTL=15min, background refresh).
Search: ElasticSearch + Redis L2 cache (TTL=30s). Events: write-through, no cache.
Expected improvement: 70% reduction in DB queries, p99 latency 420ms → 45ms.
Implementation: cache-aside pattern, redis-py, serialise with msgpack (faster than JSON).
Estimated infra cost: +$80/mo for Redis t3.small. Payoff: immediate. PR #301. """ * 16,
    ),
    (
        "[research:api-rate-limiting]",
        "Rate limiting design",
        """Rate limiting design for public API. Tiers: Free (60/min), Pro (1000/min), Enterprise (unlimited).
Algorithm: sliding window with Redis ZADD/ZCOUNT. Alternative considered: token bucket (better burst
handling) but sliding window simpler and sufficient for our SLAs. Key: rate_limit:{user_id}:{minute}.
Headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset.
429 response includes Retry-After header. Bypass: internal service-to-service (HMAC auth).
DDoS: Cloudflare in front (handles volumetric), our rate limiter handles API abuse.
Implementation: FastAPI middleware, redis-py, ~80 lines. Test: locust with 200 concurrent users.
Edge case: clock skew between nodes — use Redis TIME command, not local time. PR #315. """ * 14,
    ),
]


def run_baseline(responses: list[tuple[str, str, str]]) -> list[int]:
    """Baseline: accumulate all content in working context."""
    context = ""
    sizes = []
    for _, _, content in responses:
        context += "\n\n" + content
        sizes.append(estimate_tokens(context))
    return sizes


def run_memex(
    responses: list[tuple[str, str, str]],
    db_path: str,
    manifest_path: str,
    mock_llm: Callable,
) -> list[int]:
    """Memex: compress each response before adding to context."""
    from memex.tools import compress_experience, reset_singletons
    reset_singletons()

    context = ""
    sizes = []
    for key, hint, content in responses:
        indexed = compress_experience(
            content=content,
            index_key=key,
            context=hint,
            db_path=db_path,
            manifest_path=manifest_path,
            _bedrock_caller=mock_llm,
        )
        context += "\n\n" + indexed
        sizes.append(estimate_tokens(context))
    return sizes


def mock_llm(content: str, context=None) -> str:
    """Mock LLM that produces a deterministic short summary."""
    words = content.split()[:30]
    return " ".join(words) + "... [compressed summary]"


def main():
    print("\n📊  Memex Benchmark — Token Usage: Baseline vs. Memex\n")
    print(f"  Simulated task: {len(TOOL_RESPONSES)} tool responses\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "bench_memex.db")
        manifest_path = os.path.join(tmpdir, "bench_manifest.json")

        baseline_sizes = run_baseline(TOOL_RESPONSES)
        memex_sizes = run_memex(TOOL_RESPONSES, db_path, manifest_path, mock_llm)

    # Print comparison table
    print(f"  {'Step':<6} {'Baseline':>12} {'Memex':>12} {'Savings':>10} {'Ratio':>8}")
    print(f"  {'────':<6} {'────────':>12} {'─────':>12} {'───────':>10} {'─────':>8}")
    for i, (b, m) in enumerate(zip(baseline_sizes, memex_sizes)):
        saved = b - m
        ratio = (1 - m / b) * 100 if b > 0 else 0
        print(f"  {i+1:<6} {b:>12,} {m:>12,} {saved:>10,} {ratio:>7.0f}%")

    final_b = baseline_sizes[-1]
    final_m = memex_sizes[-1]
    final_saved = final_b - final_m
    final_ratio = (1 - final_m / final_b) * 100 if final_b > 0 else 0

    print(f"\n  Final context: {final_b:,} tokens (baseline) → {final_m:,} tokens (Memex)")
    print(f"  Reduction: {final_ratio:.0f}% — {final_saved:,} tokens saved\n")

    if final_ratio >= 60:
        print("  ✅  PASS: >60% context reduction achieved\n")
    else:
        print(f"  ⚠️  Only {final_ratio:.0f}% reduction (target: 60%)\n")


if __name__ == "__main__":
    main()
