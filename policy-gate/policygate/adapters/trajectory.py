"""openclaw-trajectory v1 events.jsonl reader (AC #10). DETERMINISTIC.

Reads a bundle's events.jsonl (tool.call, tool.result, transcript
user/assistant events). The schema marker is checked; an unknown schemaVersion
raises TrajectorySchemaError (CLI exit 2). Tested only on committed synthetic
fixtures labeled "synthetic_shape": true; no real export is created (CC-D3).
"""

import json
import os

from .. import principal as principal_mod

SCHEMA = "openclaw-trajectory"
SCHEMA_VERSION = 1


class TrajectorySchemaError(Exception):
    pass


def _read_lines(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def read_bundle(bundle_dir):
    """Yield Events from events.jsonl in a trajectory bundle dir."""
    events_path = os.path.join(bundle_dir, "events.jsonl") if os.path.isdir(bundle_dir) else bundle_dir
    records = list(_read_lines(events_path))
    if not records:
        raise TrajectorySchemaError("empty trajectory bundle")
    header = records[0]
    schema = header.get("schema") or header.get("schemaVersion") and SCHEMA
    version = header.get("schemaVersion")
    if header.get("schema") == SCHEMA or schema == SCHEMA:
        if version not in (SCHEMA_VERSION, None):
            raise TrajectorySchemaError(f"unknown schemaVersion {version!r}")
    else:
        raise TrajectorySchemaError(f"missing or unknown schema marker: {header!r}")
    agent = header.get("agent") or "trajectory"
    last_assistant = ""
    for rec in records[1:]:
        et = rec.get("event") or rec.get("type")
        ts = rec.get("ts") or rec.get("timestamp", "")
        if et in ("transcript.user", "user"):
            p, prov, cc_text = principal_mod.classify_typed(rec)
            yield {"type": "turn", "role": "user", "text": rec.get("text", ""),
                   "principal": p, "provenance_source": prov, "cc_text": cc_text,
                   "prev_assistant": last_assistant, "ts": ts, "agent": agent}
        elif et in ("transcript.assistant", "assistant"):
            if rec.get("text", "").strip():
                last_assistant = rec["text"]
        elif et in ("tool.call",):
            yield {"type": "call", "tool": rec.get("tool"), "args": rec.get("args") or {},
                   "ts": ts, "agent": agent}
        elif et in ("tool.result",):
            yield {"type": "result", "tool": rec.get("tool"),
                   "ok": rec.get("ok", True), "text": rec.get("text", "")}
