"""
Benchmark runner: compare xMemory top-down retrieval vs. flat top-k on same queries.

Usage:
    python -m benchmarks.runner --db /tmp/xmemory_bench.db

The runner:
1. Generates 100+ synthetic messages and ingests them
2. Builds the full hierarchy via MemoryUpdater
3. For each benchmark query, runs both retrieval strategies
4. Collects token counts and diversity scores
5. Outputs results to benchmarks/report.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# Allow running as a script from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.data import generate_messages, get_benchmark_queries
from xmemory.models import Message, RetrievalResult
from xmemory.retrieval import MemoryRetriever
from xmemory.schema import init_db
from xmemory.store import MemoryStore
from xmemory.updater import MemoryUpdater


@dataclass
class BenchmarkRow:
    query: str
    xmemory_tokens: int
    flat_tokens: int
    xmemory_level: str
    xmemory_semantic_count: int
    flat_message_count: int
    token_reduction_pct: float


def flat_topk_retrieve(
    store: MemoryStore,
    query: str,
    k: int = 10,
) -> RetrievalResult:
    """
    Naive flat top-k retrieval: return the k most recent messages.

    This simulates standard RAG behaviour over a coherent conversation stream
    where all messages are retrieved by recency (a common baseline).
    In a real RAG system this would use vector similarity; we use recency
    as a proxy since we have no embeddings in this benchmark.
    """
    # Get all messages, sort by recency, take top-k
    conn = store.conn
    rows = conn.execute(
        "SELECT id FROM messages ORDER BY timestamp DESC LIMIT ?", (k,)
    ).fetchall()
    ids = [r["id"] for r in rows]
    messages = store.get_messages_by_ids(ids)

    result = RetrievalResult(
        query=query,
        messages=messages,
        retrieval_level="message",
    )
    result.total_tokens = result.token_estimate()
    return result


def run_benchmark(
    db_path: str = ":memory:",
    n_sessions: int = 7,
    construction_client=None,
    retrieval_client=None,
    verbose: bool = True,
) -> List[BenchmarkRow]:
    """
    Full benchmark run.

    Args:
        db_path:             Path to SQLite DB (use ':memory:' for ephemeral).
        n_sessions:          Number of synthetic sessions to generate.
        construction_client: Optional boto3 mock for Haiku.
        retrieval_client:    Optional boto3 mock for Sonnet.
        verbose:             Print progress to stdout.

    Returns:
        List of BenchmarkRow, one per query.
    """
    conn = init_db(db_path)
    store = MemoryStore(conn)

    # --- Ingest messages ---
    messages = generate_messages(n_sessions=n_sessions)
    if verbose:
        print(f"Generated {len(messages)} messages across {n_sessions} sessions.")

    for msg in messages:
        store.add_message(msg)

    if verbose:
        print("Ingested messages. Building hierarchy...")

    # --- Build hierarchy ---
    updater = MemoryUpdater(store, client=construction_client)
    update_result = updater.run()

    if verbose:
        print(update_result.summary)
        stats = store.stats()
        print(f"Hierarchy stats: {stats}")

    # --- Run retrieval comparison ---
    retriever = MemoryRetriever(
        store,
        client=retrieval_client,
        expand_on_uncertainty=True,
    )
    queries = get_benchmark_queries()
    rows: List[BenchmarkRow] = []

    for query in queries:
        xmemory_result = retriever.retrieve(query)
        flat_result = flat_topk_retrieve(store, query, k=10)

        xmem_tokens = xmemory_result.token_estimate()
        flat_tokens = flat_result.token_estimate()

        if flat_tokens > 0:
            reduction = (flat_tokens - xmem_tokens) / flat_tokens * 100
        else:
            reduction = 0.0

        row = BenchmarkRow(
            query=query,
            xmemory_tokens=xmem_tokens,
            flat_tokens=flat_tokens,
            xmemory_level=xmemory_result.retrieval_level,
            xmemory_semantic_count=len(xmemory_result.semantics),
            flat_message_count=len(flat_result.messages),
            token_reduction_pct=reduction,
        )
        rows.append(row)

        if verbose:
            print(
                f"  [{row.xmemory_level}] '{query[:50]}' "
                f"xmem={xmem_tokens}tok flat={flat_tokens}tok "
                f"reduction={reduction:.1f}%"
            )

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run xMemory benchmark")
    parser.add_argument("--db", default=":memory:", help="SQLite DB path")
    parser.add_argument("--sessions", type=int, default=7, help="Number of sessions")
    args = parser.parse_args()

    rows = run_benchmark(db_path=args.db, n_sessions=args.sessions)

    # Print summary
    from benchmarks.report import print_report
    print_report(rows)


if __name__ == "__main__":
    main()
