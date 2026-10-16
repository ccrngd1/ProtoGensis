#!/usr/bin/env python3
"""Re-key a labels file after an action_key change (AC #19, phase 3).

The action_key moved from sha256(agent|ts|vtool|cmd[:200]) to
sha256(agent|ts|vtool|full-segment[|occurrence]). Labels are keyed on it, so
MasterControl re-keys local/labels/real-actions.jsonl after the next host run
WITHOUT the builder seeing the real data: given two run dirs over the same
archive (old and new actions.jsonl), actions are matched on (agent, ts, vtool)
in stream order, and each old key maps to the new key at the same position.
A duplicated old key (the collision this fixes) maps to ALL its new keys, each
new row carrying the same label.

Generic + offline: reads only the two actions.jsonl files and the labels file;
writes the re-keyed labels to --out (default: stdout). No real content is
printed — keys only.

Usage:
  python scripts/rekey_labels.py --old-run <dir> --new-run <dir> \
      --labels <labels.jsonl> [--out <out.jsonl>]
"""

import argparse
import json
import sys


def read_actions(run_dir_or_file):
    import os
    path = run_dir_or_file
    if os.path.isdir(path):
        path = os.path.join(path, "actions.jsonl")
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                d = json.loads(line)
                out.append((d["agent"], d["ts"], d["vtool"], d["action_key"]))
    return out


def build_key_map(old_actions, new_actions):
    """old_key -> [new_key, ...], matching on (agent, ts, vtool) and order.

    Both runs must come from the same archive: the i-th action with a given
    (agent, ts, vtool) triple in the old run corresponds to the i-th in the
    new run. Raises ValueError when the triples do not line up."""
    def by_triple(actions):
        d = {}
        for agent, ts, vtool, key in actions:
            d.setdefault((agent, ts, vtool), []).append(key)
        return d

    old_t, new_t = by_triple(old_actions), by_triple(new_actions)
    if sorted(old_t) != sorted(new_t):
        only_old = set(old_t) - set(new_t)
        only_new = set(new_t) - set(old_t)
        raise ValueError(
            f"runs do not cover the same actions: {len(only_old)} triple(s) only "
            f"in old, {len(only_new)} only in new (same archive required)")
    key_map = {}
    for triple, old_keys in old_t.items():
        new_keys = new_t[triple]
        if len(old_keys) != len(new_keys):
            raise ValueError(f"triple {triple!r}: {len(old_keys)} old vs "
                             f"{len(new_keys)} new actions")
        for ok, nk in zip(old_keys, new_keys):
            key_map.setdefault(ok, [])
            if nk not in key_map[ok]:
                key_map[ok].append(nk)
    return key_map


def rekey(labels_path, key_map):
    """Returns (rows, stats). A duplicated old key fans out to all its new
    keys with the same label; an unknown key is kept verbatim and counted."""
    rows = []
    stats = {"in": 0, "out": 0, "fanned_out": 0, "unmatched": 0}
    with open(labels_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if "action_key" not in d:   # header/comment rows pass through
                rows.append(d)
                continue
            stats["in"] += 1
            new_keys = key_map.get(d["action_key"])
            if not new_keys:
                stats["unmatched"] += 1
                rows.append(d)
                stats["out"] += 1
                continue
            if len(new_keys) > 1:
                stats["fanned_out"] += 1
            for nk in new_keys:
                rows.append({**d, "action_key": nk})
                stats["out"] += 1
    # one label per new key: fan-out can collide with an existing row
    seen, deduped = set(), []
    for d in rows:
        k = d.get("action_key")
        if k is None:
            deduped.append(d)
            continue
        if k in seen:
            continue
        seen.add(k)
        deduped.append(d)
    stats["out"] = sum(1 for d in deduped if "action_key" in d)
    return deduped, stats


def keys_join(labels_path, run_dir):
    """True when every labelled key appears in the run's actions.jsonl (used
    by host_run.sh to decide whether re-keying is needed at all)."""
    run_keys = {k for _, _, _, k in read_actions(run_dir)}
    with open(labels_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if "action_key" in d and d["action_key"] not in run_keys:
                return False
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--old-run", required=True, help="run dir (or actions.jsonl) with the OLD keys")
    ap.add_argument("--new-run", required=True, help="run dir (or actions.jsonl) with the NEW keys")
    ap.add_argument("--labels", required=True, help="labels jsonl keyed with OLD keys")
    ap.add_argument("--out", help="output path (default: stdout)")
    ap.add_argument("--check-join", action="store_true",
                    help="exit 0 if the labels already join the NEW run (no rekey needed), else 1")
    ns = ap.parse_args(argv)

    if ns.check_join:
        return 0 if keys_join(ns.labels, ns.new_run) else 1

    key_map = build_key_map(read_actions(ns.old_run), read_actions(ns.new_run))
    rows, stats = rekey(ns.labels, key_map)
    out = "\n".join(json.dumps(d, sort_keys=True) for d in rows) + "\n"
    if ns.out:
        with open(ns.out, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        sys.stdout.write(out)
    print(f"rekey: {stats['in']} label row(s) in, {stats['out']} out, "
          f"{stats['fanned_out']} duplicated old key(s) fanned out, "
          f"{stats['unmatched']} unmatched (kept verbatim)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
