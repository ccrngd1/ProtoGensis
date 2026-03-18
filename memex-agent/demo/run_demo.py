#!/usr/bin/env python3
"""
demo/run_demo.py — CLI demo of the Memex compress/read cycle.

Usage:
    python demo/run_demo.py

Shows:
    1. A "long tool response" being compressed to an indexed summary
    2. The summary displayed as it would appear in working context
    3. read_experience() recovering the exact original content
    4. Token savings stats
"""

import os
import sys
import tempfile
import textwrap

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LONG_CONTENT = """
## OAuth2 Library Research Results — March 2026

I evaluated three Python OAuth2 libraries for the authentication module:

### 1. requests-oauthlib
- Stars: 3,200 | Last release: Jan 2026
- Pros: Tight requests integration, clean API, well-documented, OAuth1 + OAuth2
- Cons: No async support, depends on requests (adds ~400KB)
- Token refresh: Automatic via TokenUpdated exception hook
- Sample:
    from requests_oauthlib import OAuth2Session
    oauth = OAuth2Session(client_id, redirect_uri=redirect_uri)
    auth_url, state = oauth.authorization_url(authorization_base_url)
    token = oauth.fetch_token(token_url, client_secret=client_secret, code=code)

### 2. authlib
- Stars: 4,800 | Last release: Dec 2025
- Pros: Async (httpx/aiohttp), OpenID Connect built-in, JWT support
- Cons: Larger API surface, steeper learning curve
- Token refresh: Native async refresh support
- Sample:
    from authlib.integrations.httpx_client import AsyncOAuth2Client
    async with AsyncOAuth2Client(client_id=client_id) as client:
        token = await client.fetch_token(token_url, code=code)

### 3. python-social-auth
- Stars: 2,900 | Last release: Nov 2025
- Pros: Django/Flask integration, pre-built providers (Google, GitHub, etc.)
- Cons: Framework-coupled, overkill for standalone use
- Token refresh: Framework-dependent

### Recommendation
**Use authlib.** Our auth module is async (FastAPI), and authlib's native async support
plus built-in JWT handling aligns with our stack. The larger API is manageable;
the async story is non-negotiable. requests-oauthlib would require adding trio or
running in a thread pool — not worth it.

### Next Steps
1. Add authlib to requirements.txt
2. Implement AuthManager class wrapping AsyncOAuth2Client
3. Store tokens in Redis with TTL matching expires_in
4. Implement refresh hook: on 401, attempt token refresh; retry once

### Security Notes
- Never log token values
- Use PKCE extension for all flows (mitigates auth code interception)
- Rotate client_secret quarterly (ops ticket: OPS-441)
- Validate state param to prevent CSRF

### Performance Benchmarks (tokens/sec, local MacBook M3 Pro)
requests-oauthlib auth flow: avg 142ms
authlib auth flow: avg 156ms (async overhead negligible at this scale)
python-social-auth auth flow: avg 201ms (framework overhead)

### References
- authlib docs: https://docs.authlib.org/en/latest/
- OAuth2 RFC 6749: https://www.rfc-editor.org/rfc/rfc6749
- PKCE RFC 7636: https://www.rfc-editor.org/rfc/rfc7636
- Our existing auth PR: github.com/acme/api/pull/213
""".strip()

INDEX_KEY = "[project:oauth-library-research]"
CONTEXT_HINT = "OAuth2 library evaluation for FastAPI auth module"


def divider(title: str = ""):
    width = 72
    if title:
        pad = (width - len(title) - 2) // 2
        print(f"\n{'─' * pad} {title} {'─' * (width - pad - len(title) - 2)}\n")
    else:
        print("─" * width)


def main():
    # Use a temp dir so the demo doesn't leave files in the project root
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "demo_memex.db")
        manifest_path = os.path.join(tmpdir, "demo_manifest.json")

        from memex.tools import compress_experience, read_experience, get_memex_stats

        print("\n🧠  Memex — Indexed Experience Memory for Agents")
        print("    Demo: compress_experience + read_experience\n")

        # ── Step 1: Show the "full" content ──────────────────────────────
        divider("ORIGINAL CONTENT (in working context)")
        original_tokens = len(LONG_CONTENT) // 4
        print(f"Content: {len(LONG_CONTENT)} chars ≈ {original_tokens} tokens\n")
        print(textwrap.indent(LONG_CONTENT[:600] + "\n... [truncated for display]", "  "))

        # ── Step 2: Compress ─────────────────────────────────────────────
        divider("CALLING compress_experience()")
        print(f"  index_key: {INDEX_KEY}")
        print(f"  context:   {CONTEXT_HINT}")
        print(f"\n  Calling Haiku 4.5 via Bedrock for summarization...")

        try:
            indexed_summary = compress_experience(
                content=LONG_CONTENT,
                index_key=INDEX_KEY,
                context=CONTEXT_HINT,
                db_path=db_path,
                manifest_path=manifest_path,
            )
            compressed = True
        except Exception as e:
            print(f"\n  ⚠️  Bedrock call failed ({e})")
            print("  Using mock summary for demo purposes.\n")
            # Fall back to a plausible summary
            from memex.store import ExperienceStore
            from memex.manifest import IndexManifest
            from memex.compress import CompressionEngine
            from memex.utils import estimate_tokens, build_indexed_summary
            from datetime import datetime, timezone

            mock_summary = (
                "Evaluated requests-oauthlib, authlib, python-social-auth. "
                "Recommend authlib: native async (FastAPI compat), built-in JWT+OIDC. "
                "Perf: 156ms vs 142ms (negligible). Use PKCE, store tokens in Redis "
                "with TTL. Next: add to requirements, implement AuthManager, refresh hook."
            )
            store = ExperienceStore(db_path)
            manifest = IndexManifest(manifest_path)
            archived_at = datetime.now(timezone.utc).isoformat()
            tokens_orig = estimate_tokens(LONG_CONTENT)
            tokens_sum = estimate_tokens(mock_summary)
            store.archive(
                key=INDEX_KEY,
                full_content=LONG_CONTENT,
                summary=mock_summary,
                token_count_original=tokens_orig,
                token_count_summary=tokens_sum,
                metadata={"context": CONTEXT_HINT},
            )
            manifest.add_entry(INDEX_KEY, mock_summary, tokens_orig - tokens_sum, archived_at)
            indexed_summary = build_indexed_summary(INDEX_KEY, mock_summary, archived_at, tokens_orig - tokens_sum)
            compressed = True

        # ── Step 3: Show the indexed summary ─────────────────────────────
        divider("INDEXED SUMMARY (replaces original in working context)")
        summary_tokens = len(indexed_summary) // 4
        print(f"Summary: {len(indexed_summary)} chars ≈ {summary_tokens} tokens\n")
        print(textwrap.indent(indexed_summary, "  "))

        # ── Step 4: read_experience ───────────────────────────────────────
        divider("CALLING read_experience()")
        print(f"  index_key: {INDEX_KEY}\n")
        recovered = read_experience(INDEX_KEY, db_path=db_path, manifest_path=manifest_path)
        match = recovered == LONG_CONTENT
        print(f"  Lossless recovery: {'✅ PASS' if match else '❌ FAIL'}")
        print(f"  Recovered {len(recovered)} chars (original: {len(LONG_CONTENT)} chars)")

        # ── Step 5: Stats ─────────────────────────────────────────────────
        divider("STATS")
        stats = get_memex_stats(db_path=db_path, manifest_path=manifest_path)
        print(f"  Entries archived:     {stats.get('count', 0)}")
        print(f"  Original tokens:      {stats.get('total_original_tokens', 0):,}")
        print(f"  Summary tokens:       {stats.get('total_summary_tokens', 0):,}")
        print(f"  Tokens saved:         {stats.get('total_tokens_saved', 0):,}")
        if stats.get('total_original_tokens', 0) > 0:
            ratio = 1 - (stats.get('total_summary_tokens', 0) / stats['total_original_tokens'])
            print(f"  Compression ratio:    {ratio:.0%}")

        divider()
        print("✅  Demo complete.\n")


if __name__ == "__main__":
    main()
