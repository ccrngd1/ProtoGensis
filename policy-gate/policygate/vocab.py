"""Closed predicate vocabulary (AC #5). DETERMINISTIC.

Each predicate declares kind, reads (arg keys it inspects), enable (vtools or
fact kinds that clear it), a declared argument domain, and a deterministic
evaluator. Evaluators are pure functions of (rule, call, facts). Fail-safety
asymmetry (NOMOS §3.1) is handled by check.py, not here: a missing fact makes a
PRECONDITION block and a FORBIDDEN pass, logged as fact_missing.

evaluate(name, rule, call, facts) returns the *predicate truth value*
(True = condition holds). check.py maps truth + derived type to ALLOW/BLOCK.
"""

import json
import re

from .vendor.aegis_scanners import SecretScanner, extract_strings

_SCANNER = SecretScanner(check_entropy=False)
PROHIBITION = re.compile(r"(DO NOT|Do NOT|NEVER|must not|❌|PERMANENT|Forbidden|do not)", re.I)

# A sentinel the evaluators return when a fact they need is absent. check.py
# turns this into a fact_missing log + fail-safety asymmetry.
MISSING = "__fact_missing__"


def _ts_hour(call):
    ts = call.get("ts") or ""
    if len(ts) >= 13 and ts[11:13].isdigit():
        return int(ts[11:13])
    return None


def ev_cc_authorized(rule, call, facts):
    fam = (rule.get("params") or {}).get("action_class", "")
    auth = facts.get("cc_authorized")
    if auth is None:
        return MISSING
    # auth is {reading: bool} or bool; a dict is resolved per-reading in check
    if isinstance(auth, dict):
        return auth
    return bool(auth)


def ev_principal_is(rule, call, facts):
    want = (rule.get("params") or {}).get("principal")
    have = facts.get("principal")
    if have is None:
        return MISSING
    return have == want


def ev_agent_in(rule, call, facts):
    agents = (rule.get("params") or {}).get("agents", [])
    agent = facts.get("agent")
    if agent is None:
        return MISSING
    return agent in agents


def ev_quiet_hours(rule, call, facts):
    p = rule.get("params") or {}
    start, end = int(p.get("start", 0)), int(p.get("end", 8))
    hour = _ts_hour(call)
    if hour is None:
        return MISSING
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


def ev_target_protected(rule, call, facts):
    protected = set((rule.get("data") or {}).get("protected", []))
    args = call.get("args") or {}
    for key in ("jobId", "unit", "path"):
        if args.get(key) in protected:
            return True
    return False


def ev_path_in(rule, call, facts):
    import fnmatch
    globs = (rule.get("params") or {}).get("globs", [])
    path = (call.get("args") or {}).get("path")
    if path is None:
        return MISSING
    return any(fnmatch.fnmatch(path, g) for g in globs)


def ev_weakens_policy(rule, call, facts):
    args = call.get("args") or {}
    path = args.get("path") or ""
    if "removed_text" not in args or args.get("removed_text") is None:
        return MISSING
    is_policy = bool(re.search(r"(SOUL|AGENTS|MEMORY)\.md$", path))
    return is_policy and bool(PROHIBITION.search(args.get("removed_text") or ""))


def ev_checkpoint_seen(rule, call, facts):
    seen = facts.get("checkpoints")
    if seen is None:
        return MISSING
    target = (rule.get("params") or {}).get("target") or (call.get("args") or {}).get("target")
    return target in seen


def ev_host_in(rule, call, facts):
    hosts = (rule.get("params") or {}).get("hosts", [])
    url = (call.get("args") or {}).get("url")
    if url is None:
        return MISSING
    return any(h in url for h in hosts)


def ev_confirmation_fresh(rule, call, facts):
    fresh = facts.get("confirmation_fresh")
    if fresh is None:
        return MISSING
    return bool(fresh)


def ev_secret_in_args(rule, call, facts):
    strings = extract_strings(call.get("args") or {})
    return _SCANNER.scan(strings)["detected"]


def ev_attempts_lt(rule, call, facts):
    limit = int((rule.get("params") or {}).get("limit", 3))
    target = (rule.get("params") or {}).get("target") or (call.get("args") or {}).get("target")
    counts = facts.get("attempts")
    if counts is None:
        return MISSING
    return counts.get(target, 0) < limit


def ev_channel_shared(rule, call, facts):
    shared = facts.get("channel_shared")
    if shared is None:
        return MISSING
    return bool(shared)


# predicate registry
VOCAB = {
    "cc_authorized":     {"kind": "principal", "reads": [], "enable": ["cc_turn"],
                          "domain": {}, "evaluator": ev_cc_authorized},
    "principal_is":      {"kind": "principal", "reads": [], "enable": [],
                          "domain": {}, "evaluator": ev_principal_is},
    "agent_in":          {"kind": "subject", "reads": [], "enable": [],
                          "domain": {}, "evaluator": ev_agent_in},
    "quiet_hours_utc":   {"kind": "temporal", "reads": ["ts"], "enable": [],
                          "domain": {"start": [0, 23], "end": [0, 24]}, "evaluator": ev_quiet_hours},
    "target_protected":  {"kind": "arg", "reads": ["jobId", "unit", "path"], "enable": [],
                          "domain": {}, "evaluator": ev_target_protected},
    "path_in":           {"kind": "arg", "reads": ["path"], "enable": [],
                          "domain": {}, "evaluator": ev_path_in},
    "weakens_policy":    {"kind": "arg", "reads": ["path", "removed_text"], "enable": ["cc_turn"],
                          "domain": {}, "evaluator": ev_weakens_policy},
    "checkpoint_seen":   {"kind": "ordering", "reads": ["target"], "enable": ["backup.create", "backup.*"],
                          "domain": {}, "evaluator": ev_checkpoint_seen},
    "host_in":           {"kind": "arg", "reads": ["url"], "enable": [],
                          "domain": {}, "evaluator": ev_host_in},
    "confirmation_fresh": {"kind": "principal", "reads": [], "enable": ["cc_turn"],
                           "domain": {}, "evaluator": ev_confirmation_fresh},
    "secret_in_args":    {"kind": "arg", "reads": ["*"], "enable": [],
                          "domain": {}, "evaluator": ev_secret_in_args},
    # should-ship
    "attempts_lt":       {"kind": "counting", "reads": ["target"], "enable": ["cc_turn"],
                          "domain": {"limit": [1, 99]}, "evaluator": ev_attempts_lt},
    "channel_shared":    {"kind": "read-gate", "reads": [], "enable": [],
                          "domain": {}, "evaluator": ev_channel_shared},
}


def names():
    return list(VOCAB)


def is_known(name):
    return name in VOCAB or name.startswith("obligation:")


def evaluate(name, rule, call, facts):
    spec = VOCAB.get(name)
    if spec is None:
        raise KeyError(name)
    return spec["evaluator"](rule, call, facts)


def domain_ok(name, params):
    spec = VOCAB.get(name)
    if not spec:
        return False
    for key, (lo, hi) in spec["domain"].items():
        if key in (params or {}):
            try:
                v = int(params[key])
            except (TypeError, ValueError):
                return False
            if not (lo <= v <= hi):
                return False
    return True


def render_list(fmt):
    data = [
        {"name": n, "kind": s["kind"], "reads": s["reads"], "enable": s["enable"]}
        for n, s in VOCAB.items()
    ]
    if fmt == "json":
        return json.dumps(data, sort_keys=True, indent=2)
    lines = []
    for d in data:
        lines.append(f"  {d['name']:20s} kind={d['kind']:10s} reads={d['reads']} enable={d['enable']}")
    return "\n".join(lines)
