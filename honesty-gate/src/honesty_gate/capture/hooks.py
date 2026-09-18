"""Claude Code hook capture path.

Three pieces, all deterministic:

1. `handle_event(event_name, payload)` — invoked by Claude Code as a hook
   command (`honesty-gate capture-hooks handle <event>` with the hook JSON
   on stdin). Appends one JSONL record per event to a per-session log under
   HONESTY_GATE_LOG_DIR (default ~/.honesty_gate/sessions/<session_id>.jsonl).

2. `collect_accessed(log_path)` — folds a session log into the
   actual_accessed set using the shared rules in capture.extract.

3. `install()` / `status()` — register/inspect the hook commands in a
   Claude Code settings JSON file (default ~/.claude/settings.json).

Events logged: PreToolUse (tool_name + tool_input.file_path), PostToolUse
(same plus tool_response), Stop (session end marker). Only PostToolUse
records count toward coverage — PostToolUse fires after a tool completes
successfully, so a PreToolUse without a matching PostToolUse (denied or
failed call) never counts as an access.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .extract import access_path

HOOK_EVENTS = ("PreToolUse", "PostToolUse", "Stop")

DEFAULT_LOG_DIR = os.path.join("~", ".honesty_gate", "sessions")
DEFAULT_SETTINGS_PATH = os.path.join("~", ".claude", "settings.json")

# Matchers for the file tools we track plus a catch-all is unnecessary;
# hook on all tools ("*") and filter at collect time — keeps the installed
# settings simple and future-proof.
HOOK_MATCHER = "*"


def log_dir() -> Path:
    return Path(os.path.expanduser(os.environ.get("HONESTY_GATE_LOG_DIR", DEFAULT_LOG_DIR)))


def session_log_path(session_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in session_id) or "unknown"
    return log_dir() / f"{safe}.jsonl"


# ---------------------------------------------------------------- handler

def handle_event(event_name: str, payload: dict) -> Path:
    """Append one hook event to the session log. Returns the log path."""
    if event_name not in HOOK_EVENTS:
        raise ValueError(f"unknown hook event: {event_name!r}")
    session_id = payload.get("session_id") or "unknown"
    record = {
        "event": event_name,
        "session_id": session_id,
        "cwd": payload.get("cwd"),
        "tool_name": payload.get("tool_name"),
        "tool_input": _slim_tool_input(payload.get("tool_input")),
        "tool_response": _slim_tool_response(payload.get("tool_response")),
    }
    path = session_log_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return path


def _slim_tool_input(tool_input) -> dict | None:
    """Keep only the fields coverage needs; drop bulky content payloads."""
    if not isinstance(tool_input, dict):
        return None
    keep = {}
    for key in ("file_path", "notebook_path", "command", "pattern", "path"):
        if key in tool_input:
            keep[key] = tool_input[key]
    return keep or None


def _slim_tool_response(tool_response) -> dict | None:
    """Record only success/error signal, never file contents."""
    if tool_response is None:
        return None
    if isinstance(tool_response, dict):
        out = {}
        for key in ("success", "is_error", "interrupted"):
            if key in tool_response:
                out[key] = tool_response[key]
        out["present"] = True
        return out
    return {"present": True}


def run_handler(event_name: str, stdin=None) -> int:
    """CLI entry: read hook JSON from stdin, log it, always exit 0.

    A capture failure must never block the agent's tool call, so errors
    are reported on stderr but the exit code stays 0.
    """
    raw = (stdin or sys.stdin).read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
        handle_event(event_name, payload)
    except Exception as exc:  # never break the hooked session
        print(f"honesty-gate hook error ({event_name}): {exc}", file=sys.stderr)
    return 0


# ---------------------------------------------------------------- collect

def collect_accessed(log_path: str | os.PathLike, root: str | None = None) -> set[str]:
    """Fold a hook session log into the actual_accessed set.

    Only successful PostToolUse events on file tools count. A recorded
    tool_response carrying an explicit error marker is skipped.
    """
    accessed: set[str] = set()
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("event") != "PostToolUse":
                continue
            resp = rec.get("tool_response")
            if isinstance(resp, dict) and (
                resp.get("is_error") is True or resp.get("success") is False
            ):
                continue
            rec_root = root if root is not None else rec.get("cwd")
            p = access_path(rec.get("tool_name"), rec.get("tool_input"), rec_root)
            if p:
                accessed.add(p)
    return accessed


# ---------------------------------------------------------------- install

def _hook_command(event_name: str) -> str:
    return f"honesty-gate capture-hooks handle {event_name}"


def _settings_path(settings_path: str | None = None) -> Path:
    return Path(os.path.expanduser(settings_path or DEFAULT_SETTINGS_PATH))


def install(settings_path: str | None = None) -> dict:
    """Register the capture hooks in a Claude Code settings JSON file.

    Idempotent: re-running never duplicates entries. Existing unrelated
    hooks are preserved.
    """
    path = _settings_path(settings_path)
    settings = {}
    if path.exists():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            settings = json.loads(text)
    hooks = settings.setdefault("hooks", {})
    changed = []
    for event in HOOK_EVENTS:
        entries = hooks.setdefault(event, [])
        cmd = _hook_command(event)
        if _find_hook(entries, cmd) is None:
            block = {"hooks": [{"type": "command", "command": cmd}]}
            if event != "Stop":
                block["matcher"] = HOOK_MATCHER
            entries.append(block)
            changed.append(event)
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return {"settings_path": str(path), "installed": changed,
            "already_present": [e for e in HOOK_EVENTS if e not in changed]}


def _find_hook(entries: list, command: str):
    for block in entries:
        for h in block.get("hooks", []):
            if h.get("type") == "command" and h.get("command") == command:
                return h
    return None


def status(settings_path: str | None = None) -> dict:
    """Report which capture hooks are registered and where logs go."""
    path = _settings_path(settings_path)
    registered = {e: False for e in HOOK_EVENTS}
    if path.exists():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            hooks = json.loads(text).get("hooks", {})
            for event in HOOK_EVENTS:
                registered[event] = _find_hook(hooks.get(event, []), _hook_command(event)) is not None
    ldir = log_dir()
    sessions = sorted(p.name for p in ldir.glob("*.jsonl")) if ldir.is_dir() else []
    return {"settings_path": str(path), "registered": registered,
            "log_dir": str(ldir), "sessions": sessions}
