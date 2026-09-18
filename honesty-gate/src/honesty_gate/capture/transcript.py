"""Transcript-replay capture path.

Replays a Claude Code session transcript (the ~/.claude/projects/**/*.jsonl
files) and derives the same actual_accessed set the hooks path produces —
same tool rules (capture.extract), same success requirement.

Transcript shape (verified against real session files on this host):
- one JSON object per line
- assistant turns: {"type": "assistant", "message": {"content": [
      {"type": "tool_use", "id": ..., "name": ..., "input": {...}}, ...]}}
- tool results come back inside subsequent user turns:
  {"type": "user", "message": {"content": [
      {"type": "tool_result", "tool_use_id": ..., "is_error": bool}, ...]}}

A tool_use counts as an access only when its paired tool_result exists and
is not an error — mirroring the hooks path, where PostToolUse only fires
after a successful call.
"""

from __future__ import annotations

import json
import os

from .extract import access_path


def iter_records(transcript_path: str | os.PathLike):
    with open(transcript_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue  # tolerate a truncated trailing line


def collect_accessed(transcript_path: str | os.PathLike, root: str | None = None) -> set[str]:
    """Replay a transcript into the actual_accessed set."""
    # First pass: index tool_use blocks and result outcomes by tool_use_id.
    pending: dict[str, tuple[str, dict, str | None]] = {}  # id -> (name, input, cwd)
    outcome: dict[str, bool] = {}  # id -> success?
    for rec in iter_records(transcript_path):
        msg = rec.get("message")
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "tool_use" and rec.get("type") == "assistant":
                tid = block.get("id")
                if tid:
                    pending[tid] = (block.get("name"), block.get("input"), rec.get("cwd"))
            elif btype == "tool_result":
                tid = block.get("tool_use_id")
                if tid:
                    outcome[tid] = not bool(block.get("is_error"))

    accessed: set[str] = set()
    for tid, (name, tool_input, cwd) in pending.items():
        if not outcome.get(tid, False):
            continue
        rec_root = root if root is not None else cwd
        p = access_path(name, tool_input, rec_root)
        if p:
            accessed.add(p)
    return accessed


def final_response(transcript_path: str | os.PathLike) -> str:
    """Extract the agent's final text response (input to the claim parser).

    Concatenates the text blocks of the last assistant message that
    contains any text — trailing pure-tool-call turns are skipped.
    """
    last_text = ""
    for rec in iter_records(transcript_path):
        if rec.get("type") != "assistant":
            continue
        msg = rec.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            if content.strip():
                last_text = content
            continue
        if not isinstance(content, list):
            continue
        texts = [b.get("text", "") for b in content
                 if isinstance(b, dict) and b.get("type") == "text"]
        joined = "\n".join(t for t in texts if t.strip())
        if joined.strip():
            last_text = joined
    return last_text
