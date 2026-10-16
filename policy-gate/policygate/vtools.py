"""Virtual-tool schema loader (config/vtools.toml). DETERMINISTIC.

Each vtool has params, is_write, infra_mutating. The infra-mutating set is
exactly spike 1's INFRA regex so parity is possible; cron.add is a write but
NOT infra-mutating in v1 (Open Question Q7).
"""

import json
import os
import tomllib

_CONFIG = os.path.join(os.path.dirname(__file__), os.pardir, "config", "vtools.toml")


def _load(path=None):
    with open(path or os.path.normpath(_CONFIG), "rb") as f:
        return tomllib.load(f)


def load(path=None):
    cfg = _load(path)
    out = {}
    for v in cfg.get("vtool", []):
        out[v["name"]] = {
            "params": v.get("params", []),
            "is_write": bool(v.get("is_write", False)),
            "infra_mutating": bool(v.get("infra_mutating", False)),
        }
    return out


def render_list(fmt, path=None):
    vt = load(path)
    data = [{"name": n, **spec} for n, spec in sorted(vt.items())]
    if fmt == "json":
        return json.dumps(data, sort_keys=True, indent=2)
    lines = []
    for d in data:
        flags = []
        if d["is_write"]:
            flags.append("write")
        if d["infra_mutating"]:
            flags.append("infra")
        lines.append(f"  {d['name']:16s} params={d['params']} {','.join(flags)}")
    return "\n".join(lines)
