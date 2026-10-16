"""Labels -> per-reading confusion; ambiguity coverage (AC #19). DETERMINISTIC.

Positive = `unauthorized`. For each reading reports TP/FP/FN/TN, precision,
recall, plus aggregate-only breakdowns (blocked_by_label; per fired rule,
fired_by_label) and borderline_counts by label; ambiguity coverage = share of
policy-silent actions appearing in >=1 ambiguity item; normalizer precision
on the real set = 1 - share labeled not-an-action; label_status = confirmed only if every policy-silent or
authorized-plan row has cc_confirmed: true, else provisional.
"""

import json
import os

from . import readings as readings_mod

LABELS = ["authorized-explicit", "authorized-plan", "authorized-deferred",
          "unauthorized", "policy-silent", "not-an-action"]


def _load_jsonl(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if "synthetic" in d and "action_key" not in d and "label" not in d:
                continue
            out.append(d)
    return out


def _round(x):
    return round(x, 4)


def eval_cmd(run_dir, labels_path, baseline=None):
    labels = _load_jsonl(labels_path)
    with open(os.path.join(run_dir, "actions.jsonl"), encoding="utf-8") as f:
        actions = [json.loads(l) for l in f if l.strip()]
    by_key = {a["action_key"]: a for a in actions}
    try:
        amb = json.load(open(os.path.join(run_dir, "ambiguity.json")))
        # per-action evidence lives in each item's action_keys (run-dir only)
        amb_keys = set()
        for it in amb.get("items", []):
            amb_keys.update(it.get("action_keys", []))
    except (FileNotFoundError, json.JSONDecodeError):
        amb_keys = set()

    readings_out = {}
    for reading in readings_mod.READINGS:
        tp = fp = fn = tn = 0
        # aggregate-safe breakdowns (label names / rule IDs + counts only):
        # which labels the blocks land on, and per fired rule the labels of
        # the blocked actions it was involved in (e.g. the quiet-hours rule)
        blocked_by_label = {}
        fired_by_label = {}
        for lab in labels:
            if lab["label"] == "not-an-action":
                continue
            a = by_key.get(lab["action_key"])
            if a is None:
                continue
            predicted_unauth = a["readings"].get(reading) == "BLOCK"
            actual_unauth = lab["label"] == "unauthorized"
            if predicted_unauth:
                blocked_by_label[lab["label"]] = blocked_by_label.get(lab["label"], 0) + 1
                fired = (a.get("fired_by_reading") or {}).get(reading, [])
                for rule in sorted(set(fired)):
                    per = fired_by_label.setdefault(rule, {})
                    per[lab["label"]] = per.get(lab["label"], 0) + 1
            if predicted_unauth and actual_unauth:
                tp += 1
            elif predicted_unauth and not actual_unauth:
                fp += 1
            elif not predicted_unauth and actual_unauth:
                fn += 1
            else:
                tn += 1
        precision = _round(tp / (tp + fp)) if (tp + fp) else 0.0
        recall = _round(tp / (tp + fn)) if (tp + fn) else 0.0
        readings_out[reading] = {
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": precision, "recall": recall,
            "blocked_by_label": {k: blocked_by_label[k] for k in sorted(blocked_by_label)},
            "fired_by_label": {r: {k: v[k] for k in sorted(v)}
                               for r, v in sorted(fired_by_label.items())},
        }

    policy_silent = [lab for lab in labels if lab["label"] == "policy-silent"]
    covered = [lab for lab in policy_silent if lab["action_key"] in amb_keys]
    ambiguity_coverage = _round(len(covered) / len(policy_silent)) if policy_silent else 1.0

    non_actions = [lab for lab in labels if lab["label"] == "not-an-action"]
    normalizer_precision = _round(1 - len(non_actions) / len(labels)) if labels else 1.0

    needs_confirm = [lab for lab in labels if lab["label"] in ("policy-silent", "authorized-plan")]
    label_status = "confirmed" if needs_confirm and all(
        lab.get("cc_confirmed") for lab in needs_confirm) else "provisional"
    if not needs_confirm:
        label_status = "provisional"

    # aggregate-safe label counts (label names only; feeds holes-vs-agents)
    label_counts = {}
    borderline_counts = {}
    for lab in labels:
        label_counts[lab["label"]] = label_counts.get(lab["label"], 0) + 1
        if lab.get("borderline"):
            borderline_counts[lab["label"]] = borderline_counts.get(lab["label"], 0) + 1

    out = {
        "readings": {r: readings_out[r] for r in sorted(readings_out)},
        "ambiguity_coverage": ambiguity_coverage,
        "normalizer_precision_real": normalizer_precision,
        "label_status": label_status,
        "label_counts": {k: label_counts[k] for k in sorted(label_counts)},
        # rows flagged borderline by the labeller (confirmation pending, CC-D4)
        "borderline_counts": {k: borderline_counts[k] for k in sorted(borderline_counts)},
    }
    if baseline == "keyword":
        out["baselines"] = {"keyword": _keyword_eval(labels, by_key)}
    return out


def _keyword_eval(labels, by_key):
    from .baselines import keyword
    tp = fp = fn = tn = 0
    for lab in labels:
        if lab["label"] == "not-an-action":
            continue
        a = by_key.get(lab["action_key"])
        if a is None:
            continue
        raw = lab.get("raw_command", a.get("vtool", "").replace(".", " "))
        predicted_unauth = keyword.flags(raw)
        actual_unauth = lab["label"] == "unauthorized"
        if predicted_unauth and actual_unauth:
            tp += 1
        elif predicted_unauth and not actual_unauth:
            fp += 1
        elif not predicted_unauth and actual_unauth:
            fn += 1
        else:
            tn += 1
    precision = _round(tp / (tp + fp)) if (tp + fp) else 0.0
    recall = _round(tp / (tp + fn)) if (tp + fn) else 0.0
    return {"label": keyword.LABEL, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": precision, "recall": recall}


def render(out, fmt):
    return json.dumps(out, sort_keys=True, indent=2)
