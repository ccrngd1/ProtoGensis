"""Replay regression tests for phase 2a Bug 1 (AC #9, #18).

A synthetic legacy archive mixing structured `edit`/`write` tool calls with
`exec` infra commands must produce infra aggregates identical to spike 1's
traversal + counting (vendored in tests/spike_ref/spike_replay.py), which
counts and evaluates ONLY actions in its INFRA set. file.edit stays in
by_vtool / non_infra counts, never receives INF-rule reading verdicts, and a
BLOCK verdict with an empty fired list is impossible.
"""

import collections
import json
import os

import pytest

from policygate import replay
from tests.spike_ref import spike_replay as spike

# One agent dir ("mainagent") with turns the spike classifies as human / cron /
# system, exec infra commands under each, plus structured edit/write calls
# (which the spike never counts: its loop only reads `exec` arguments).
ARCHIVE_LINES = [
    # human turn -> gateway restart (authorized under every reading) + edits
    {"timestamp": "2026-05-01T10:00:00Z",
     "message": {"role": "user", "content": "please restart the gateway"}},
    {"timestamp": "2026-05-01T10:00:05Z",
     "message": {"role": "assistant", "content": [
         {"type": "toolCall", "name": "exec",
          "arguments": {"command": "openclaw gateway restart"}},
         {"type": "toolCall", "name": "edit",
          "arguments": {"path": "notes.md", "oldText": "alpha", "newText": "beta"}},
         {"type": "toolCall", "name": "write",
          "arguments": {"path": "scratch.md", "content": "draft"}},
     ]}},
    # human turn naming nothing relevant -> service restart blocked strict/plan
    {"timestamp": "2026-05-01T12:00:00Z",
     "message": {"role": "user", "content": "thanks, looks good"}},
    {"timestamp": "2026-05-01T12:00:05Z",
     "message": {"role": "assistant", "content": [
         {"type": "toolCall", "name": "exec",
          "arguments": {"command": "systemctl restart synthetic-unit"}},
     ]}},
    # cron turn in quiet hours -> cron disable blocked under every reading
    {"timestamp": "2026-05-02T01:00:00Z",
     "message": {"role": "user",
                 "content": "[cron: nightly] cron job scheduled maintenance"}},
    {"timestamp": "2026-05-02T01:00:05Z",
     "message": {"role": "assistant", "content": [
         {"type": "toolCall", "name": "exec",
          "arguments": {"command": "openclaw cron disable job-synth-1"}},
         {"type": "toolCall", "name": "write",
          "arguments": {"path": "log.md", "content": "did maintenance"}},
     ]}},
    # system turn -> config set
    {"timestamp": "2026-05-03T09:00:00Z",
     "message": {"role": "user", "content": "System: housekeeping notice"}},
    {"timestamp": "2026-05-03T09:00:05Z",
     "message": {"role": "assistant", "content": [
         {"type": "toolCall", "name": "exec",
          "arguments": {"command": "openclaw config set channels.synthetic"}},
     ]}},
]


@pytest.fixture()
def archive(tmp_path):
    d = tmp_path / "agents"
    arch = d / "mainagent" / "session-sqlite-import-archive"
    arch.mkdir(parents=True)
    with open(arch / "s1.jsonl.imported-1", "w", encoding="utf-8") as f:
        for line in ARCHIVE_LINES:
            f.write(json.dumps(line) + "\n")
    return str(d)


def _spike_counts(agents_dir):
    """Spike 1's traversal + counting (its main() loop) on a synthetic archive,
    using the vendored functions verbatim: only `exec` commands are segmented,
    only INFRA-matching actions are counted and evaluated."""
    files = []
    for agent in sorted(os.listdir(agents_dir)):
        sub = os.path.join(agents_dir, agent, "session-sqlite-import-archive")
        if os.path.isdir(sub):
            files += [os.path.join(sub, f) for f in sorted(os.listdir(sub))
                      if ".jsonl.imported-" in f and "trajectory" not in f]
    actions = []
    for fpath in files:
        agent = os.path.relpath(fpath, agents_dir).split(os.sep)[0]
        turn_principal = None
        cc_text = None
        prev_assistant = ""
        last_assistant_text = ""
        for line in open(fpath, errors="ignore"):
            d = json.loads(line)
            m = d.get("message") or {}
            role = m.get("role")
            if role == "user":
                txt = spike.text_of(m)
                turn_principal = spike.principal(txt)
                cc_text = (spike.re.sub(r"^\[[^\]]{8,40}\]\s*", "", txt)
                           if turn_principal == "human" else None)
                prev_assistant = last_assistant_text
                continue
            if role != "assistant":
                continue
            at = spike.text_of(m)
            if at.strip():
                last_assistant_text = at
            for p in m.get("content") or []:
                if not isinstance(p, dict) or p.get("type") != "toolCall":
                    continue
                if p.get("name") != "exec":
                    continue
                cmd = str((p.get("arguments") or {}).get("command", ""))
                for seg in spike.segments(cmd):
                    a = spike.classify(seg)
                    if a and a["vtool"] == "unparsed":
                        continue
                    if not a or not spike.INFRA.match(a["vtool"]):
                        continue
                    ts = d.get("timestamp", "")
                    hour = int(ts[11:13]) if len(ts) >= 13 and ts[11:13].isdigit() else 12
                    v = {r: spike.authorized(r, a["vtool"], cc_text, prev_assistant)
                         for r in ("strict", "plan", "lenient")}
                    actions.append((agent, ts[:16], a["vtool"],
                                    turn_principal or "none", v, hour < 8))
    return {
        "infra_actions": len(actions),
        "by_vtool": dict(collections.Counter(a[2] for a in actions)),
        "by_agent": dict(collections.Counter(a[0] for a in actions)),
        "by_principal": dict(collections.Counter(a[3] for a in actions)),
        "blocked": {r: sum(1 for a in actions if not a[4][r])
                    for r in ("strict", "plan", "lenient")},
        "quiet_in_window": sum(1 for a in actions if a[5]),
        "quiet_blocked_plan": sum(1 for a in actions if a[5] and not a[4]["plan"]),
    }


# spike principal names <-> PolicyGate principal classes (the parity mapping:
# spike "human" is our cc_direct heuristic class)
SPIKE_TO_PG_PRINCIPAL = {"human": "cc_direct", "cron": "cron", "system": "system",
                         "heartbeat": "heartbeat", "agent": "agent"}


def test_spike_parity_on_synthetic_archive(archive):
    """Bug 1 regression: infra aggregates equal the spike's own counting; the
    structured edit/write calls never leak into them."""
    want = _spike_counts(archive)
    agg, _ = replay.replay_stream("legacy-archive", archive, "spike-parity")

    assert agg["normalizer"]["infra_actions"] == want["infra_actions"] == 4
    assert agg["by_agent"] == want["by_agent"]
    want_principals = {SPIKE_TO_PG_PRINCIPAL[k]: v
                       for k, v in want["by_principal"].items()}
    assert agg["by_principal"] == want_principals
    for r in ("strict", "plan", "lenient"):
        assert agg["readings"][r]["blocked"] == want["blocked"][r]
        assert agg["readings"][r]["total"] == want["infra_actions"]
    assert agg["quiet_hours"]["in_window"] == want["quiet_in_window"]
    assert agg["quiet_hours"]["blocked_plan"] == want["quiet_blocked_plan"]

    # by_vtool keeps non-infra writes, but only as their own entries
    infra_by_vtool = {k: v for k, v in agg["by_vtool"].items() if k != "file.edit"}
    assert infra_by_vtool == want["by_vtool"]
    assert agg["by_vtool"]["file.edit"] == 3
    assert agg["normalizer"]["non_infra_actions"] == 3
    assert agg["non_infra_by_vtool"] == {"file.edit": 3}


def test_file_edit_gets_no_inf_rule_verdicts(archive, tmp_path):
    """file.edit rows in actions.jsonl are NO_RULE_IN_FORCE under the parity
    rules (nothing binds file.edit), never BLOCK with fired []."""
    agg, actions = replay.replay_stream("legacy-archive", archive, "spike-parity")
    out = tmp_path / "run"
    replay.write_run_dir(str(out), agg, actions, "spike-parity")
    recs = [json.loads(l) for l in open(out / "actions.jsonl", encoding="utf-8")]
    edits = [r for r in recs if r["vtool"] == "file.edit"]
    assert len(edits) == 3
    for r in edits:
        assert r["infra"] is False
        assert r["verdict_class"] == "NO_RULE_IN_FORCE"
        assert all(v == "NO_RULE_IN_FORCE" for v in r["readings"].values())
    # every BLOCK row names at least one fired rule, per reading
    for r in recs:
        for reading, v in r["readings"].items():
            if v == "BLOCK":
                assert r["fired_by_reading"][reading], r


def test_block_with_empty_fired_is_impossible():
    """The invariant check raises on a BLOCK verdict with an empty fired list."""
    bad = {"vtool": "cron.disable", "ts": "2026-05-02T01:00",
           "verdict_class": "BLOCK", "fired": [],
           "readings": {"strict": "BLOCK"}, "fired_by_reading": {"strict": []}}
    with pytest.raises(replay.ReplayInvariantError):
        replay.check_verdict_invariant(bad)
    ok = {"vtool": "cron.disable", "ts": "2026-05-02T01:00",
          "verdict_class": "BLOCK", "fired": ["INF-PRE-01"],
          "readings": {"strict": "BLOCK"},
          "fired_by_reading": {"strict": ["INF-PRE-01"]}}
    replay.check_verdict_invariant(ok)  # does not raise


def test_non_infra_still_evaluated_by_binding_rules(tmp_path):
    """A non-infra write is still evaluated by a rule that binds it (the pinned
    weakens_policy case): BLOCK with the binding rule in fired, no INF rules."""
    d = tmp_path / "agents"
    arch = d / "mainagent" / "session-sqlite-import-archive"
    arch.mkdir(parents=True)
    lines = [
        {"timestamp": "2026-05-01T10:00:00Z",
         "message": {"role": "user", "content": "tidy the notes"}},
        {"timestamp": "2026-05-01T10:00:05Z",
         "message": {"role": "assistant", "content": [
             {"type": "toolCall", "name": "edit",
              "arguments": {"path": "workspace/MEMORY.md",
                            "oldText": "Do NOT disable the nightly job.",
                            "newText": "(cleaned)"}},
         ]}},
    ]
    with open(arch / "s1.jsonl.imported-1", "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")
    weakens_rule = {
        "id": "TWR-FBD-03", "polarity": "block_when_true",
        "predicate": "weakens_policy", "params": {},
        "tools": ["file.edit"], "subjects": ["*"],
    }
    from policygate import rules as rules_mod
    agg, actions = replay.replay_stream(
        "legacy-archive", str(d), "pinned",
        pinned_rules=[rules_mod.candidate_to_rule(weakens_rule)])
    assert agg["normalizer"]["infra_actions"] == 0
    assert agg["normalizer"]["non_infra_actions"] == 1
    a = actions[0]
    assert a["verdicts"]["strict"] == "BLOCK"
    assert a["fired_by_reading"]["strict"] == ["TWR-FBD-03"]
    out = tmp_path / "run"
    replay.write_run_dir(str(out), agg, actions, "pinned")  # invariant holds


def test_parity_check_principal_mapping(archive):
    """The parity ids principal_human/cron/system read the cc_direct/cron/
    system entries of by_principal (spike `human` ↔ cc_direct heuristic)."""
    agg, _ = replay.replay_stream("legacy-archive", archive, "spike-parity")
    rows = {r["id"]: r["actual"]
            for r in agg["parity_check"]["matches"] + agg["parity_check"]["deltas"]}
    assert rows["principal_human"] == agg["by_principal"].get("cc_direct", 0) == 2
    assert rows["principal_cron"] == agg["by_principal"].get("cron", 0) == 1
    assert rows["principal_system"] == agg["by_principal"].get("system", 0) == 1
    # infra_actions parity value excludes the file.edit rows
    assert rows["infra_actions"] == 4
