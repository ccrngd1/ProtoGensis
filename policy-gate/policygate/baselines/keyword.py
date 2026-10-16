"""agenthook-style keyword baseline (our reimplementation, not agenthook) (AC #20).

A fixed phrase -> regex catalog over RAW exec strings (no normalizer, no
principals, no pinning, no readings), committed in config/keyword_catalog.toml.
It runs on the same events and is scored by eval.
"""

import json
import os
import re
import tomllib

LABEL = "agenthook-style keyword baseline (our reimplementation, not agenthook)"
_CATALOG = os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir,
                                         "config", "keyword_catalog.toml"))


def _load_catalog(path=None):
    with open(path or _CATALOG, "rb") as f:
        cfg = tomllib.load(f)
    return [(e["name"], re.compile(e["pattern"], re.I)) for e in cfg.get("entry", [])]


def matches(raw_command, catalog=None):
    """Return the list of catalog entry names that fire on a raw command."""
    cat = catalog or _load_catalog()
    return [name for name, pat in cat if pat.search(raw_command or "")]


def flags(raw_command, catalog=None):
    return bool(matches(raw_command, catalog))


def feb19_summary(ep2_events, jobmap):
    """Count how many episode-2 calls the keyword baseline would flag, over the
    raw command text (reconstructed from the vtool). Mechanism illustration."""
    cat = _load_catalog()
    blocked = 0
    total = 0
    for e in ep2_events:
        if e.get("type") != "call":
            continue
        total += 1
        vt = e["vtool"]
        # synthesize a raw command the baseline would see
        raw = {
            "cron.disable": "openclaw cron disable",
            "cron.rm": "openclaw cron rm",
            "cron.list": "openclaw cron list",
            "file.edit": "edit MEMORY.md",
        }.get(vt, vt.replace(".", " "))
        if flags(raw, cat):
            blocked += 1
    return {"label": LABEL, "ep2_blocked": blocked, "ep2_total": total}
