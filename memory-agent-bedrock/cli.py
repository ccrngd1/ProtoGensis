#!/usr/bin/env python3
"""CLI interface for local testing of the memory agent."""
from __future__ import annotations

import argparse
import json
import logging
import sys

from agents.orchestrator import Orchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s"
)


def _get_orc(args) -> Orchestrator:
    return Orchestrator(
        db_path=getattr(args, "db", "memory.db"),
        consolidation_interval=300,
    )


def cmd_ingest(args) -> None:
    orc = _get_orc(args)
    text = args.text or sys.stdin.read()
    memory = orc.ingest(text, source=args.source)
    print(json.dumps({
        "id": memory.id,
        "summary": memory.summary,
        "entities": memory.entities,
        "topics": memory.topics,
        "importance": memory.importance,
    }, indent=2))


def cmd_query(args) -> None:
    orc = _get_orc(args)
    answer = orc.query(args.question)
    print(answer)


def cmd_consolidate(args) -> None:
    orc = _get_orc(args)
    result = orc.consolidate()
    if result is None:
        print("Not enough unconsolidated memories.")
    else:
        print(f"Consolidation complete: {result.id}")
        print(f"  Memories processed: {len(result.memory_ids)}")
        connections_preview = result.connections[:200] + ("..." if len(result.connections) > 200 else "")
        insights_preview = result.insights[:200] + ("..." if len(result.insights) > 200 else "")
        print(f"  Connections: {connections_preview}")
        print(f"  Insights: {insights_preview}")


def cmd_status(args) -> None:
    orc = _get_orc(args)
    s = orc.status()
    print(json.dumps(s, indent=2))


def cmd_list(args) -> None:
    orc = _get_orc(args)
    memories = orc.store.list_memories(limit=args.limit)
    for m in memories:
        print(f"[{m.id[:8]}] ({m.importance:.2f}) {m.summary[:100]}")


def main():
    parser = argparse.ArgumentParser(description="Memory Agent CLI")
    parser.add_argument("--db", default="memory.db", help="Path to SQLite database")

    sub = parser.add_subparsers(dest="command", required=True)

    # ingest
    p_ingest = sub.add_parser("ingest", help="Ingest text into memory")
    p_ingest.add_argument("text", nargs="?", help="Text to ingest (or pipe via stdin)")
    p_ingest.add_argument("--source", default="", help="Source label")
    p_ingest.set_defaults(func=cmd_ingest)

    # query
    p_query = sub.add_parser("query", help="Query stored memories")
    p_query.add_argument("question", help="Question to ask")
    p_query.set_defaults(func=cmd_query)

    # consolidate
    p_cons = sub.add_parser("consolidate", help="Run consolidation cycle")
    p_cons.set_defaults(func=cmd_consolidate)

    # status
    p_status = sub.add_parser("status", help="Show agent status")
    p_status.set_defaults(func=cmd_status)

    # list
    p_list = sub.add_parser("list", help="List stored memories")
    p_list.add_argument("--limit", type=int, default=20, help="Max memories to show")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
