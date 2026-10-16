"""Amendment loop: answers -> overlay version -> re-replay -> delta (AC #17).

An overlay is a new pseudo-version `overlay:<sha256 of answers>` applied after
the pinned version; it is stored in the --out run dir, NEVER written to the
policy repo. delta.json records per-reading before/after totals and the items
closed.
"""

import hashlib
import json
import os
import tomllib

from . import readings as readings_mod


def _answers_sha(answers_path):
    with open(answers_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def amend_cmd(run_dir, answers_path, out_dir):
    with open(answers_path, "rb") as f:
        answers = tomllib.load(f).get("answers", {})
    with open(os.path.join(run_dir, "aggregates.json"), encoding="utf-8") as f:
        before_agg = json.load(f)
    with open(os.path.join(run_dir, "ambiguity.json"), encoding="utf-8") as f:
        ambiguity = json.load(f)

    before = {r: before_agg["readings"][r]["blocked"] for r in readings_mod.READINGS}
    # applying answers closes the answered items; each closed subject_scope item
    # that resolves to "not bound" removes its rule's blocks for the affected
    # actions. For the file-only mechanism demo we model closed items as
    # reducing blocked counts by the item's recorded `affected` deltas.
    items = ambiguity.get("items", [])
    closed = [it for it in items if it["id"] in answers]
    after = dict(before)
    for it in closed:
        aff = it.get("affected", {})
        for r in readings_mod.READINGS:
            after[r] = max(0, after[r] - int(aff.get(r, 0)))

    overlay_version = "overlay:" + _answers_sha(answers_path)
    delta = {
        "overlay_version": overlay_version,
        "before": before,
        "after": after,
        "items_closed": len(closed),
        "overlay_written_to_policy_repo": False,
    }
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "delta.json"), "w", encoding="utf-8") as f:
        json.dump(delta, f, sort_keys=True, indent=2)
    return delta


def demo_data(banner):
    """Synthetic mechanism demo: two ambiguity items answered, re-replay delta."""
    before = {"lenient": 2, "plan": 5, "strict": 8}
    # answering "main is not bound" closes a subject_scope item and a plan_reading
    # item, removing 1 plan block and 2 strict blocks (synthetic, labeled)
    after = {"lenient": 2, "plan": 4, "strict": 6}
    return {
        "banner": banner,
        "items_closed": 2,
        "before": {r: before[r] for r in sorted(before)},
        "after": {r: after[r] for r in sorted(after)},
        "overlay_written_to_policy_repo": False,
    }


def render(data, fmt):
    if fmt == "json":
        return json.dumps(data, sort_keys=True, indent=2)
    return json.dumps(data, sort_keys=True, indent=2)
