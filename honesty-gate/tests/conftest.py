"""Shared builders: synthesize a recorded session as BOTH a Claude Code
transcript JSONL and an equivalent honesty-gate hook session log, so the
two capture paths can be cross-checked on identical events (AC3)."""

from __future__ import annotations

import json

import pytest

ROOT = "/work/demo"
FILES = [f"{ROOT}/src/file{i}.py" for i in range(1, 6)]


def make_transcript(path, reads, session_id="sess-fixture", failed_reads=(),
                    final_text="", bash_commands=()):
    """Write a minimal Claude Code transcript JSONL.

    reads: paths successfully Read; failed_reads: Read calls that errored;
    bash_commands: Bash tool calls (should never count as coverage).
    """
    records = []
    tid = 0

    def tool_turn(name, tool_input, is_error=False):
        nonlocal tid
        tid += 1
        use_id = f"toolu_{tid:04d}"
        records.append({
            "type": "assistant", "sessionId": session_id, "cwd": ROOT,
            "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": use_id, "name": name, "input": tool_input},
            ]},
        })
        records.append({
            "type": "user", "sessionId": session_id, "cwd": ROOT,
            "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": use_id,
                 "is_error": is_error, "content": "err" if is_error else "ok"},
            ]},
        })

    records.append({"type": "user", "sessionId": session_id, "cwd": ROOT,
                    "message": {"role": "user", "content": "review these files"}})
    for p in reads:
        tool_turn("Read", {"file_path": p})
    for p in failed_reads:
        tool_turn("Read", {"file_path": p}, is_error=True)
    for cmd in bash_commands:
        tool_turn("Bash", {"command": cmd})
    if final_text:
        records.append({
            "type": "assistant", "sessionId": session_id, "cwd": ROOT,
            "message": {"role": "assistant",
                        "content": [{"type": "text", "text": final_text}]},
        })
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return path


def make_hook_log(path, reads, session_id="sess-fixture", failed_reads=(),
                  bash_commands=()):
    """Write the hook session log for the SAME event stream as
    make_transcript: Pre+Post for successful calls, Pre only for failed
    ones (PostToolUse does not fire on failure), then Stop."""
    records = []

    def pre(name, tool_input):
        records.append({"event": "PreToolUse", "session_id": session_id,
                        "cwd": ROOT, "tool_name": name,
                        "tool_input": tool_input, "tool_response": None})

    def post(name, tool_input):
        records.append({"event": "PostToolUse", "session_id": session_id,
                        "cwd": ROOT, "tool_name": name,
                        "tool_input": tool_input,
                        "tool_response": {"present": True}})

    for p in reads:
        pre("Read", {"file_path": p})
        post("Read", {"file_path": p})
    for p in failed_reads:
        pre("Read", {"file_path": p})  # no PostToolUse: the call failed
    for cmd in bash_commands:
        pre("Bash", {"command": cmd})
        post("Bash", {"command": cmd})
    records.append({"event": "Stop", "session_id": session_id, "cwd": ROOT,
                    "tool_name": None, "tool_input": None, "tool_response": None})
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return path


@pytest.fixture
def asked_file(tmp_path):
    p = tmp_path / "asked.txt"
    p.write_text("\n".join(FILES) + "\n", encoding="utf-8")
    return p
