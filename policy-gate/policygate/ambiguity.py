"""Ambiguity queue (AC #17). DETERMINISTIC.

One item per undecidable (clause, action-class) pair:
{id, kind ∈ {subject_scope, plan_reading, deferred_authorization,
temporal_scope, conflict, unclassified_clause}, clause_ref, action_class,
question, options, affected {strict, plan, lenient}, proposed_amendment,
action_keys}. It is a FILE; nothing is posted to the Temple (CC-D7).

- clause_ref points at a POLICY CLAUSE (`file@commit:line`, falling back to the
  rule id for builtins), never at an action.
- action_class is the vtool family: `<prefix>.*` for infra-mutating vtools
  (cron.*, gateway.*, ...), the vtool itself otherwise (file.edit).
- affected sums, per reading, the actions whose verdict hinges on the item.
- action_keys is the per-action evidence; it exists only in local/tmp run
  dirs (results/ carries only the counts by kind, via counts_by_kind).
- deferred_authorization follows research §3.2: the triggering turn is `cron`
  AND its prompt references a queued/validated item WITHOUT provenance (who
  approved, which Temple item). A cron trigger alone is NOT deferred
  authorization, and the question only exists where an authorization clause
  binds the action's vtool (otherwise there is no clause to point at).
"""

import hashlib
import json
import os
import re

from . import vtools as vtools_mod

KINDS = ["subject_scope", "plan_reading", "deferred_authorization",
         "temporal_scope", "conflict", "unclassified_clause"]

# predicates whose rules carry an authorization verdict (same set as replay)
AUTH_PREDICATES = {"cc_authorized", "confirmation_fresh"}

# research §3.2: a queued / "already validated" item referenced by a cron
# prompt, without provenance (who approved, when, which Temple item)
QUEUE_RE = re.compile(r"queue|action[- ]burst|already validated|validated when",
                      re.I)
PROVENANCE_RE = re.compile(r"approved[- ]by|temple[- ]item|decision[- ]id",
                           re.I)


def load(run_dir):
    with open(os.path.join(run_dir, "ambiguity.json"), encoding="utf-8") as f:
        return json.load(f)


def render_run(run_dir, fmt):
    data = load(run_dir)
    if fmt == "json":
        return json.dumps(data, sort_keys=True, indent=2)
    lines = ["# Ambiguity queue", ""]
    for it in data.get("items", []):
        lines.append(f"## {it['id']} ({it['kind']})")
        lines.append(f"- clause: {it.get('clause_ref')}")
        lines.append(f"- action class: {it.get('action_class')}")
        lines.append(f"- question: {it['question']}")
        lines.append(f"- options: {', '.join(it.get('options', []))}")
        lines.append(f"- affected: {it.get('affected')}")
        lines.append(f"- evidence: {len(it.get('action_keys', []))} action(s)")
        lines.append("")
    return "\n".join(lines)


def counts_by_kind(items):
    """Aggregate-safe count by kind (the only ambiguity data in results/)."""
    counts = {}
    for it in items:
        counts[it["kind"]] = counts.get(it["kind"], 0) + 1
    return {k: counts[k] for k in sorted(counts)}


def _clause_str(rule):
    """`file@commit:line` for a rule's source clause; rule id for builtins."""
    ref = (rule or {}).get("clause_ref") or {}
    if ref.get("file"):
        return f"{ref['file']}@{str(ref.get('commit', ''))[:8]}:{ref.get('line', 0)}"
    return (rule or {}).get("id", "")


def _family(vtool, infra):
    """Action class: vtool family for infra-mutating vtools, else the vtool."""
    if infra:
        return vtool.split(".", 1)[0] + ".*"
    return vtool


def _rule_families(rule, schema):
    """Sorted families of every vtool a rule binds (for clause-level items)."""
    fams = set()
    for t in rule.get("tools", []):
        spec = schema.get(t)
        if spec is None:
            continue
        fams.add(_family(t, spec["infra_mutating"]))
    return sorted(fams)


def _item_id(kind, clause_ref, action_class):
    h = hashlib.sha256(f"{kind}|{clause_ref}|{action_class}".encode("utf-8"))
    return f"AMB-{kind[:4].upper()}-{h.hexdigest()[:8]}"


def _binding(rules, vtool, predicates=None):
    """First (by id) gating rule binding vtool, optionally by predicate set."""
    hits = [r for r in rules
            if vtool in r.get("tools", [])
            and (predicates is None or r.get("predicate") in predicates)]
    return min(hits, key=lambda r: r["id"]) if hits else None


def generate(actions, resolve_report, by_kind_only=False, ambiguous_rules=None,
             rules=None):
    """Generate ambiguity items: ONE item per undecidable
    (clause, action-class) pair (AC #17), with `affected` summed over the
    actions whose verdict hinges on it and per-action evidence kept as
    `action_keys` (run-dir only).

    `rules` are the gating rules of the run (used to resolve the policy clause
    each question points at). `ambiguous_rules` are candidates classified
    `ambiguous` (never gate, AC #17e): each becomes an unclassified_clause
    item. Returns a list of item dicts (or counts by kind when by_kind_only,
    for the aggregate-safe real-data path)."""
    rules = rules or []
    rules_by_id = {r["id"]: r for r in rules}
    schema = vtools_mod.load()
    groups = {}

    def add(kind, clause_ref, action_class, question, options, amendment,
            affected=None, action_key=None):
        key = (kind, clause_ref, action_class)
        g = groups.get(key)
        if g is None:
            g = groups[key] = {
                "id": _item_id(kind, clause_ref, action_class),
                "kind": kind, "clause_ref": clause_ref,
                "action_class": action_class, "question": question,
                "options": options,
                "affected": {"strict": 0, "plan": 0, "lenient": 0},
                "proposed_amendment": amendment, "action_keys": []}
        for r, n in (affected or {}).items():
            g["affected"][r] += int(n)
        if action_key and action_key not in g["action_keys"]:
            g["action_keys"].append(action_key)

    def fired_counts(rule_id, acts):
        out = {"strict": 0, "plan": 0, "lenient": 0}
        for a in acts:
            by = a.get("fired_by_reading") or {}
            for r in out:
                if rule_id in (by.get(r) or []):
                    out[r] += 1
        return out

    # subject_scope + conflict from RESOLVE: clause-level items, one per
    # (clause, family) with >= 1 bound action; one zero-affected item over all
    # the rule's families when no action binds (the clause is still undecided)
    for row in resolve_report or []:
        if row["outcome"] == "SUBJECT_UNDECIDED":
            rule = rules_by_id.get(row["id"])
            clause = _clause_str(rule) or row["id"]
            question = (f"Does the rule {row['id']} bind this agent? "
                        "(is main a subject?)")
            amendment = "scope the clause with an explicit subject list"
            bound = [a for a in actions or []
                     if rule and a.get("vtool") in rule.get("tools", [])]
            if bound:
                for a in bound:
                    fam = _family(a["vtool"], a.get("infra", False))
                    add("subject_scope", clause, fam, question, ["yes", "no"],
                        amendment, affected=fired_counts(row["id"], [a]),
                        action_key=a.get("action_key"))
            else:
                fams = _rule_families(rule, schema) if rule else []
                add("subject_scope", clause, ",".join(fams) or "*", question,
                    ["yes", "no"], amendment)
        elif row["outcome"] == "CONFLICT":
            ids = row["id"].split("~")
            rule_a = rules_by_id.get(ids[0])
            clause = _clause_str(rule_a) or row["id"]
            question = f"Conflict: {row['detail']} — which wins?"
            amendment = "narrow the whole-file protection to rule-bearing sections"
            options = ["forbid", "require", "narrow-to-section"]
            bound = [a for a in actions or []
                     if rule_a and a.get("vtool") in rule_a.get("tools", [])]
            if bound:
                for a in bound:
                    fam = _family(a["vtool"], a.get("infra", False))
                    add("conflict", clause, fam, question, options, amendment,
                        affected=fired_counts(ids[0], [a]),
                        action_key=a.get("action_key"))
            else:
                fams = _rule_families(rule_a, schema) if rule_a else []
                add("conflict", clause, ",".join(fams) or "*", question,
                    options, amendment)

    for a in actions or []:
        vtool = a.get("vtool", "")
        fam = _family(vtool, a.get("infra", False))
        key = a.get("action_key")
        # plan_reading: the authorization clause is undecided between the
        # strict and plan readings for this action
        auth = a.get("readings_auth") or {}
        if auth.get("strict") != auth.get("plan"):
            rule = _binding(rules, vtool, AUTH_PREDICATES)
            if rule is not None:
                add("plan_reading", _clause_str(rule), fam,
                    f"Does 'yes' to a plan authorize each step of {fam} actions?",
                    ["yes", "no"], "define whether plan affirmation is per-step",
                    affected={"strict": 1, "plan": 0, "lenient": 0},
                    action_key=key)
        # deferred_authorization (research §3.2): cron trigger referencing a
        # queued/validated item WITHOUT provenance, where an authorization
        # clause binds the vtool. NOT every cron-triggered action.
        trigger = a.get("cc_text") or a.get("turn_text") or ""
        if a.get("principal") == "cron" and QUEUE_RE.search(trigger) \
                and not PROVENANCE_RE.search(trigger):
            rule = _binding(rules, vtool, AUTH_PREDICATES)
            if rule is not None:
                add("deferred_authorization", _clause_str(rule), fam,
                    "Does a queued Action Burst item (no recorded approver) "
                    f"carry CC's authority for {fam} actions?",
                    ["yes", "no"],
                    "require queue items to record who approved them",
                    affected={"strict": 1, "plan": 1, "lenient": 0},
                    action_key=key)
        # temporal_scope: in-window infra action against the quiet-hours clause
        if a.get("hour") is not None and a["hour"] < 8 and vtool.startswith("cron."):
            rule = _binding(rules, vtool, {"quiet_hours_utc"})
            if rule is not None:
                add("temporal_scope", _clause_str(rule), fam,
                    f"Is an in-quiet-window {fam} action 'autonomous infra work'?",
                    ["yes", "no"], "define infra-work scope for quiet hours",
                    affected={"strict": 0, "plan": 1, "lenient": 0},
                    action_key=key)

    # unclassified_clause: candidates classified `ambiguous` never gate; each
    # becomes one queue item naming its clause (AC #17e)
    for r in ambiguous_rules or []:
        clause = _clause_str(r) or r["id"]
        fams = _rule_families(r, schema)
        add("unclassified_clause", clause, ",".join(fams) or "*",
            f"Clause of rule {r['id']} is classified ambiguous — "
            "is it gateable, an obligation, or text-only?",
            ["gateable", "obligation", "text-only"],
            "classify the clause explicitly in the candidate file")

    items = [groups[k] for k in sorted(groups)]
    if by_kind_only:
        return counts_by_kind(items)
    return items


def write(run_dir, items):
    with open(os.path.join(run_dir, "ambiguity.json"), "w", encoding="utf-8") as f:
        json.dump({"items": items}, f, sort_keys=True, indent=2)
    with open(os.path.join(run_dir, "ambiguity.md"), "w", encoding="utf-8") as f:
        f.write(render_run(run_dir, "md"))
