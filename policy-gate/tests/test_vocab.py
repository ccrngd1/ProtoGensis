"""Vocabulary evaluator tests, one per MVP predicate (AC #5)."""

from policygate import vocab


def ev(name, rule, call, facts):
    return vocab.evaluate(name, rule, call, facts)


def test_cc_authorized():
    assert ev("cc_authorized", {"params": {"action_class": "x"}}, {}, {"cc_authorized": True}) is True
    assert ev("cc_authorized", {"params": {}}, {}, {}) == vocab.MISSING


def test_principal_is():
    assert ev("principal_is", {"params": {"principal": "cc_direct"}}, {}, {"principal": "cc_direct"}) is True
    assert ev("principal_is", {"params": {"principal": "cc_direct"}}, {}, {"principal": "cron"}) is False
    assert ev("principal_is", {"params": {"principal": "cc_direct"}}, {}, {}) == vocab.MISSING


def test_agent_in():
    assert ev("agent_in", {"params": {"agents": ["main"]}}, {}, {"agent": "main"}) is True
    assert ev("agent_in", {"params": {"agents": ["main"]}}, {}, {"agent": "enhancer"}) is False


def test_quiet_hours_utc():
    r = {"params": {"start": 0, "end": 8}}
    assert ev("quiet_hours_utc", r, {"ts": "2026-02-19T01:00:00Z"}, {}) is True
    assert ev("quiet_hours_utc", r, {"ts": "2026-02-19T12:00:00Z"}, {}) is False
    assert ev("quiet_hours_utc", r, {"ts": ""}, {}) == vocab.MISSING


def test_target_protected():
    r = {"data": {"protected": ["j1", "j2"]}}
    assert ev("target_protected", r, {"args": {"jobId": "j1"}}, {}) is True
    assert ev("target_protected", r, {"args": {"jobId": "j9"}}, {}) is False


def test_path_in():
    r = {"params": {"globs": ["/opt/temple/data/*"]}}
    assert ev("path_in", r, {"args": {"path": "/opt/temple/data/x"}}, {}) is True
    assert ev("path_in", r, {"args": {"path": "/home/x"}}, {}) is False


def test_weakens_policy():
    call = {"args": {"path": "workspace/MEMORY.md", "removed_text": "DO NOT disable"}}
    assert ev("weakens_policy", {}, call, {}) is True
    call2 = {"args": {"path": "workspace/MEMORY.md", "removed_text": "just a note"}}
    assert ev("weakens_policy", {}, call2, {}) is False
    call3 = {"args": {"path": "workspace/MEMORY.md", "removed_text": None}}
    assert ev("weakens_policy", {}, call3, {}) == vocab.MISSING


def test_checkpoint_seen():
    r = {"params": {"target": "svc"}}
    assert ev("checkpoint_seen", r, {}, {"checkpoints": {"svc"}}) is True
    assert ev("checkpoint_seen", r, {}, {"checkpoints": set()}) is False
    assert ev("checkpoint_seen", r, {}, {}) == vocab.MISSING


def test_host_in():
    # private IP assembled at runtime so no literal RFC1918 address is committed
    ip = "192." + "168." + "1.27"
    r = {"params": {"hosts": [ip]}}
    assert ev("host_in", r, {"args": {"url": f"http://{ip}:3002/x"}}, {}) is True
    assert ev("host_in", r, {"args": {"url": "http://example"}}, {}) is False


def test_confirmation_fresh():
    assert ev("confirmation_fresh", {}, {}, {"confirmation_fresh": True}) is True
    assert ev("confirmation_fresh", {}, {}, {"confirmation_fresh": False}) is False
    assert ev("confirmation_fresh", {}, {}, {}) == vocab.MISSING


def test_secret_in_args():
    # assembled at runtime so no literal secret is committed (R10)
    fake_key = "AKIA" + "IOSFODNN7" + "EXAMPLE"
    call = {"args": {"command": f"export AWS_KEY={fake_key}"}}
    assert ev("secret_in_args", {}, call, {}) is True
    assert ev("secret_in_args", {}, {"args": {"jobId": "j1"}}, {}) is False


def test_domain_ok():
    assert vocab.domain_ok("quiet_hours_utc", {"start": 0, "end": 8}) is True
    assert vocab.domain_ok("quiet_hours_utc", {"start": 25, "end": 8}) is False
