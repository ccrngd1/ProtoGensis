"""Offline candidate checker (phase 2b). DETERMINISTIC, stdlib only.

`policygate candidates check --parse-dump <file> [--parse-dump <file> ...]
--candidates <file> --format json|terminal` verifies that every candidate's
`clause_ref` resolves to a clause in at least one of the given parse dumps
(the JSON written by `policygate parse --format json`), then runs RESOLVE and
reports counts per RESOLVE class/outcome and per candidate origin.

A clause_ref resolves when every key it carries matches a dumped clause:
  file   -> clause src.file (exact)
  commit -> clause src.commit (prefix match, so 8-hex pins work)
  clause_sha256 -> clause clause_sha256 (prefix match)
  section_hash  -> clause section_hash (prefix match)
  line   -> clause src.line (exact)
A ref must carry `file` plus at least one of clause_sha256 / section_hash to
be checkable. Candidates for rules with no bundle clause (PolicyGate built-ins,
platform rules from config/) mark their ref `{"builtin": <why>}` and are
counted separately, never as unresolved.

Exit 1 only when a checkable clause_ref fails to resolve (or a dump cannot be
read); RESOLVE repairs/rejects are findings, not errors.
"""

import json

from . import pinning as pinning_mod
from . import resolve as resolve_mod
from . import rules as rules_mod

EXIT_OK, EXIT_CHECK_FAILED = 0, 1


def load_dump(path):
    """Load one parse dump; returns {"path", "at", "clauses": [...]}."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "clauses" not in data:
        raise ValueError(f"{path}: not a parse dump (no 'clauses' key)")
    return {"path": path, "at": data.get("at", ""), "clauses": data["clauses"]}


def _matches(ref, clause):
    src = clause.get("src") or {}
    if ref.get("file") != src.get("file"):
        return False
    commit = ref.get("commit")
    if commit and not str(src.get("commit", "")).startswith(commit):
        return False
    ch = ref.get("clause_sha256")
    if ch and not str(clause.get("clause_sha256", "")).startswith(ch):
        return False
    sh = ref.get("section_hash")
    if sh and not str(clause.get("section_hash", "")).startswith(sh):
        return False
    if "line" in ref and ref["line"] != src.get("line"):
        return False
    return True


def resolve_ref(ref, dumps):
    """Return the list of (dump_at, clause_id) matches for one clause_ref."""
    hits = []
    for d in dumps:
        for c in d["clauses"]:
            if _matches(ref, c):
                hits.append({"at": d["at"], "id": c.get("id", "")})
    return hits


def check(dump_paths, candidates_path):
    dumps = [load_dump(p) for p in dump_paths]
    cands = rules_mod.load_candidates(candidates_path)

    ref_rows = []
    n_resolved = n_builtin = n_unresolved = n_uncheckable = 0
    for c in cands:
        cid = c.get("id", "<no-id>")
        ref = c.get("clause_ref") or {}
        if ref.get("builtin"):
            n_builtin += 1
            ref_rows.append({"id": cid, "status": "builtin",
                             "detail": str(ref.get("builtin"))})
            continue
        if not ref.get("file") or not (ref.get("clause_sha256") or ref.get("section_hash")):
            n_uncheckable += 1
            ref_rows.append({"id": cid, "status": "uncheckable",
                             "detail": "clause_ref needs file + clause_sha256|section_hash"})
            continue
        hits = resolve_ref(ref, dumps)
        if hits:
            n_resolved += 1
            ref_rows.append({"id": cid, "status": "resolved", "hits": hits})
        else:
            n_unresolved += 1
            ref_rows.append({"id": cid, "status": "UNRESOLVED",
                             "detail": f"no clause in any dump matches {ref}"})

    _, report = resolve_mod.resolve(cands)
    by_outcome, by_class = {}, {}
    for row in report:
        by_outcome[row["outcome"]] = by_outcome.get(row["outcome"], 0) + 1
        by_class[row["class"]] = by_class.get(row["class"], 0) + 1
    by_origin = {}
    for c in cands:
        o = c.get("origin", "builder")
        by_origin[o] = by_origin.get(o, 0) + 1
    by_predicate, by_polarity, by_cls = {}, {}, {}
    for c in cands:
        p = c.get("predicate", "?")
        by_predicate[p] = by_predicate.get(p, 0) + 1
        pol = c.get("polarity", "?")
        by_polarity[pol] = by_polarity.get(pol, 0) + 1
        k = c.get("class", "gateable")
        by_cls[k] = by_cls.get(k, 0) + 1

    result = {
        "schema": "policygate-candidates-check-v1",
        "dumps": [{"path": d["path"], "at": d["at"], "clauses": len(d["clauses"])}
                  for d in dumps],
        "candidates_in": len(cands),
        "clause_refs": {
            "resolved": n_resolved, "builtin": n_builtin,
            "uncheckable": n_uncheckable, "unresolved": n_unresolved,
            "unresolved_ids": [r["id"] for r in ref_rows if r["status"] == "UNRESOLVED"],
            "uncheckable_ids": [r["id"] for r in ref_rows if r["status"] == "uncheckable"],
        },
        "per_origin": dict(sorted(by_origin.items())),
        "per_predicate": dict(sorted(by_predicate.items())),
        "per_polarity": dict(sorted(by_polarity.items())),
        "per_class": dict(sorted(by_cls.items())),
        # replay routing per clause class (AC #17e)
        "class_routing": pinning_mod.routing_table(cands),
        "resolve_outcomes": dict(sorted(by_outcome.items())),
        "resolve_classes": dict(sorted(by_class.items())),
        "resolve_report": report,
        "ref_rows": ref_rows,
        "ok": n_unresolved == 0 and n_uncheckable == 0,
    }
    return result


def render(result, fmt):
    if fmt == "json":
        return json.dumps(result, sort_keys=True, indent=2)
    lines = ["# candidates check"]
    for d in result["dumps"]:
        lines.append(f"dump {d['path']}: at={d['at']} clauses={d['clauses']}")
    cr = result["clause_refs"]
    lines.append(f"candidates: {result['candidates_in']} "
                 f"(resolved {cr['resolved']}, builtin {cr['builtin']}, "
                 f"uncheckable {cr['uncheckable']}, UNRESOLVED {cr['unresolved']})")
    for cid in cr["unresolved_ids"]:
        lines.append(f"  UNRESOLVED: {cid}")
    for cid in cr["uncheckable_ids"]:
        lines.append(f"  uncheckable: {cid}")
    lines.append("origins: " + json.dumps(result["per_origin"], sort_keys=True))
    lines.append("class routing (non-gateable classes never BLOCK): "
                 + json.dumps(result["class_routing"], sort_keys=True))
    lines.append("RESOLVE outcomes: " + json.dumps(result["resolve_outcomes"], sort_keys=True))
    lines.append("RESOLVE classes: " + json.dumps(result["resolve_classes"], sort_keys=True))
    lines.append("candidates check: " + ("OK" if result["ok"] else "FAILED"))
    return "\n".join(lines)


def check_cmd(ns):
    import sys
    try:
        result = check(ns.parse_dump, ns.candidates)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_CHECK_FAILED
    print(render(result, ns.format))
    return EXIT_OK if result["ok"] else EXIT_CHECK_FAILED
