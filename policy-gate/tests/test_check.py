"""CHECK tests: audit mode, fail-safety, determinism (AC #12, #15)."""

from policygate import check


RULES = [
    {"id": "PRE", "type": "PRECONDITION", "predicate": "cc_authorized",
     "params": {"action_class": "x"}, "tools": ["cron.disable"]},
    {"id": "FBD", "type": "FORBIDDEN", "predicate": "target_protected",
     "params": {}, "tools": ["cron.disable"], "data": {"protected": ["j1"]}},
]


def test_double_fire_audit_mode():
    call = {"vtool": "cron.disable", "args": {"jobId": "j1"}, "ts": ""}
    facts = {"cc_authorized": False}
    out = check.check("cron.disable", call, facts, RULES)
    assert out["verdict"] == "BLOCK"
    assert set(out["fired"]) == {"PRE", "FBD"}


def test_allow_when_authorized_and_not_protected():
    call = {"vtool": "cron.disable", "args": {"jobId": "j9"}, "ts": ""}
    facts = {"cc_authorized": True}
    out = check.check("cron.disable", call, facts, RULES)
    assert out["verdict"] == "ALLOW"
    assert out["fired"] == []


def test_fail_safety_precondition_blocks_on_missing():
    call = {"vtool": "cron.disable", "args": {"jobId": "j9"}, "ts": ""}
    out = check.check("cron.disable", call, {}, [RULES[0]])
    assert out["verdict"] == "BLOCK"
    assert "PRE" in out["fact_missing"]


def test_fail_safety_forbidden_passes_on_missing():
    fbd = {"id": "W", "type": "FORBIDDEN", "predicate": "weakens_policy",
           "params": {}, "tools": ["file.edit"]}
    call = {"vtool": "file.edit", "args": {"path": "MEMORY.md", "removed_text": None}, "ts": ""}
    out = check.check("file.edit", call, {}, [fbd])
    assert out["verdict"] == "ALLOW"
    assert "W" in out["fact_missing"]


def test_pure_function():
    call = {"vtool": "cron.disable", "args": {"jobId": "j1"}, "ts": ""}
    facts = {"cc_authorized": False}
    a = check.check("cron.disable", call, facts, RULES)
    b = check.check("cron.disable", call, facts, RULES)
    assert a == b
