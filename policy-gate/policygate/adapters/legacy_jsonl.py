"""Legacy JSONL archive reader (spike 1 parity). DETERMINISTIC.

Reads agents/*/session-sqlite-import-archive/*.jsonl.imported-* (excluding
trajectory files, as the spike does). Reproduces spike 1's traversal exactly:
role handling, text_of, toolCall parts. Principal is always heuristic.
"""

import glob
import json
import os

from .. import principal as principal_mod


def text_of(m):
    c = m.get("content")
    if isinstance(c, str):
        return c
    return " ".join(p.get("text", "") for p in (c or []) if isinstance(p, dict) and p.get("type") == "text")


def iter_files(agents_dir):
    pattern = os.path.join(agents_dir, "*", "session-sqlite-import-archive", "*.jsonl.imported-*")
    return [f for f in sorted(glob.glob(pattern)) if "trajectory" not in f]


def read_file(path, agents_dir):
    """Yield Events from one archive file, carrying agent + heuristic principals.

    The emitted turn events carry the raw text so replay can recover cc_text and
    the preceding assistant message (spike semantics)."""
    agent = os.path.relpath(path, agents_dir).split(os.sep)[0]
    last_assistant_text = ""
    with open(path, errors="ignore") as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            m = d.get("message") or {}
            role = m.get("role")
            ts = d.get("timestamp", "")
            if role == "user":
                txt = text_of(m)
                p, prov, cc_text = principal_mod.classify_legacy(txt)
                yield {"type": "turn", "role": "user", "text": txt, "principal": p,
                       "provenance_source": prov, "cc_text": cc_text,
                       "prev_assistant": last_assistant_text, "ts": ts, "agent": agent}
                continue
            if role != "assistant":
                continue
            at = text_of(m)
            if at.strip():
                last_assistant_text = at
            for part in m.get("content") or []:
                if not isinstance(part, dict) or part.get("type") != "toolCall":
                    continue
                name = part.get("name")
                args = part.get("arguments") or {}
                yield {"type": "call", "tool": name, "args": args, "ts": ts, "agent": agent}


def read_archive(agents_dir):
    """Yield (file_count info via iter_files) all events across all files."""
    for path in iter_files(agents_dir):
        yield from read_file(path, agents_dir)
