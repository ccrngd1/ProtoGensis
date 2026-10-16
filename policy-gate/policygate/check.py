"""CHECK(vtool, args, facts, rules, t) -> ALLOW | BLOCK(fired[]) (AC #12, #15).

Pure and deterministic. Audit mode evaluates EVERY rule (stop_at_first=False)
and records all fired rules per call. Fail-safety asymmetry (NOMOS §3.1): a
missing fact makes a PRECONDITION block and a FORBIDDEN pass, and every such
evaluation is logged as fact_missing.
"""

from . import vocab


def _fires(rule, call, facts):
    """Return (fires: bool, fact_missing: bool)."""
    pred = rule["predicate"]
    val = vocab.evaluate(pred, rule, call, facts)
    if val == vocab.MISSING:
        # fail-safety asymmetry
        if rule["type"] == "PRECONDITION":
            return True, True   # missing precondition blocks
        return False, True       # missing forbidden-condition passes
    truth = bool(val)
    if rule["type"] == "FORBIDDEN":
        return truth, False
    # PRECONDITION blocks until the predicate holds
    return (not truth), False


def check(vtool, call, facts, rules, stop_at_first=False):
    """Evaluate in-force rules bound to vtool. Returns dict with verdict,
    fired rule ids, and fact_missing ids."""
    fired = []
    fact_missing = []
    for rule in rules:
        if vtool not in rule["tools"]:
            continue
        fires, missing = _fires(rule, call, facts)
        if missing:
            fact_missing.append(rule["id"])
        if fires:
            fired.append(rule["id"])
            if stop_at_first:
                break
    verdict = "BLOCK" if fired else "ALLOW"
    return {"verdict": verdict, "fired": fired, "fact_missing": fact_missing}
