"""Rule dataclass, derive_type(), load/save (sorted keys) (AC #5).

A rule is {id, type ∈ {FORBIDDEN, PRECONDITION}, predicate, params, tools[],
subjects, clause_ref, src, votes, resolve[]}. Type is DERIVED from the
candidate's polarity, never chosen: block_when_true -> FORBIDDEN,
block_until_true -> PRECONDITION (NOMOS §3.1). A candidate carrying an explicit
`type` field is rejected (REJECT type-not-derivable).
"""

import json

POLARITY_TO_TYPE = {
    "block_when_true": "FORBIDDEN",
    "block_until_true": "PRECONDITION",
}


class RuleError(Exception):
    pass


def derive_type(polarity):
    if polarity not in POLARITY_TO_TYPE:
        raise RuleError(f"unknown polarity {polarity!r}")
    return POLARITY_TO_TYPE[polarity]


def candidate_to_rule(c):
    """Validate a candidate and derive its type. Raises RuleError on an
    explicit type field or an unknown polarity."""
    if "type" in c:
        raise RuleError("REJECT type-not-derivable: candidate carries an explicit `type` field")
    polarity = c.get("polarity")
    if polarity is None:
        raise RuleError("REJECT type-not-derivable: candidate has no polarity")
    rule = {
        "id": c["id"],
        "type": derive_type(polarity),
        "predicate": c["predicate"],
        "params": c.get("params", {}),
        "tools": list(c.get("tools", [])),
        "subjects": c.get("subjects", ["*"]),
        "clause_ref": c.get("clause_ref", {}),
        "src": c.get("src", {}),
        "votes": c.get("votes", ""),
        "origin": c.get("origin", "builder"),
        "resolve": [],
    }
    if "data" in c:
        rule["data"] = c["data"]
    if c.get("requires_write"):
        rule["requires_write"] = True
    if "clause" in c:
        rule["clause"] = c["clause"]
    if "class" in c:
        rule["class"] = c["class"]
    if "effective_from" in c:
        rule["effective_from"] = c["effective_from"]
    if "version_of" in c:
        # per-version candidate override: one rule per clause version (AC #14)
        rule["version_of"] = c["version_of"]
    return rule


def load_candidates(path):
    """Load builder/cached candidate file(s). Returns a list of candidate dicts.

    Accepts a single JSON file (object with `candidates` or a bare list) or a
    directory of such files.
    """
    import os
    cands = []
    if os.path.isdir(path):
        files = sorted(os.path.join(path, f) for f in os.listdir(path) if f.endswith(".json"))
    else:
        files = [path]
    for fp in files:
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cands.extend(data.get("candidates", []))
        elif isinstance(data, list):
            cands.extend(data)
    return cands


def save_rules(rules, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"rules": sorted(rules, key=lambda r: r["id"])}, f,
                  sort_keys=True, indent=2)


def rules_json(rules):
    return json.dumps({"rules": sorted(rules, key=lambda r: r["id"])},
                      sort_keys=True, indent=2)
