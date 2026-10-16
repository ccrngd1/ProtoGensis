"""`policygate candidates check` on synthetic parse dumps (phase 2b).

Also pins the action_key contract: the key is sha256(agent|ts|vtool|segment),
with no profile-dependent input, so hand labels written against one profile's
actions.jsonl join against any other profile's run of the same archive.
"""

import json

import pytest

from policygate import candidates_check, cli, replay

CLAUSE_A = {
    "clause_sha256": "aa" * 32,
    "section_hash": "bb" * 32,
    "heading_chain": ["Synthetic Rules", "Forbidden"],
    "id": "global/BASE-AGENTS.md@1111111111111111111111111111111111111111:7",
    "kind": "clause", "rule_bearing": True,
    "src": {"file": "global/BASE-AGENTS.md",
            "commit": "1111111111111111111111111111111111111111",
            "heading": "Forbidden", "line": 7},
    "subjects": ["*"], "inherited_qualifiers": [],
    "text": "synthetic: do not mutate cron",
}
CLAUSE_B = {
    "clause_sha256": "cc" * 32,
    "section_hash": "dd" * 32,
    "heading_chain": ["Synthetic Rules", "Quiet"],
    "id": "global/BASE-AGENTS.md@2222222222222222222222222222222222222222:9",
    "kind": "clause", "rule_bearing": True,
    "src": {"file": "global/BASE-AGENTS.md",
            "commit": "2222222222222222222222222222222222222222",
            "heading": "Quiet", "line": 9},
    "subjects": ["*"], "inherited_qualifiers": [],
    "text": "synthetic: no infra work at night",
}


@pytest.fixture()
def dumps(tmp_path):
    p1 = tmp_path / "parse-t1.json"
    p2 = tmp_path / "parse-t2.json"
    p1.write_text(json.dumps({"at": "2026-01-01T00:00:00Z", "count": 1,
                              "fenced_blocks_skipped": 0, "clauses": [CLAUSE_A]}))
    p2.write_text(json.dumps({"at": "2026-06-01T00:00:00Z", "count": 2,
                              "fenced_blocks_skipped": 0,
                              "clauses": [CLAUSE_A, CLAUSE_B]}))
    return [str(p1), str(p2)]


def _cand(cid, ref, predicate="cc_authorized", polarity="block_until_true",
          tools=("cron.edit",), **extra):
    c = {"id": cid, "polarity": polarity, "predicate": predicate, "params": {},
         "tools": list(tools), "subjects": ["agent:synthetic"],
         "origin": "builder", "class": "gateable", "clause_ref": ref,
         "src": {"file": ref.get("file", "policygate:builtin")}}
    c.update(extra)
    return c


def _write(tmp_path, cands):
    p = tmp_path / "cands.json"
    p.write_text(json.dumps({"synthetic": True, "candidates": cands}))
    return str(p)


def test_resolved_builtin_and_counts(tmp_path, dumps, capsys):
    cands = [
        # resolves in both dumps by full hash
        _cand("S-01", {"file": "global/BASE-AGENTS.md", "clause_sha256": "aa" * 32}),
        # resolves only in dump 2, by hash prefix + commit prefix
        _cand("S-02", {"file": "global/BASE-AGENTS.md", "commit": "22222222",
                       "clause_sha256": "cccccccccccc"},
              predicate="quiet_hours_utc", polarity="block_when_true",
              params={"start": 0, "end": 8}),
        # builtin: no bundle clause, counted separately
        _cand("S-03", {"builtin": "policygate weakens_policy built-in"},
              predicate="weakens_policy", polarity="block_when_true",
              tools=("file.edit",)),
        # section-hash-only ref
        _cand("S-04", {"file": "global/BASE-AGENTS.md", "section_hash": "dd" * 32}),
    ]
    rc = cli.main(["candidates", "check", "--parse-dump", dumps[0],
                   "--parse-dump", dumps[1], "--candidates",
                   _write(tmp_path, cands), "--format", "json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["ok"] is True
    assert out["clause_refs"] == {"resolved": 3, "builtin": 1, "uncheckable": 0,
                                  "unresolved": 0, "unresolved_ids": [],
                                  "uncheckable_ids": []}
    assert out["per_origin"] == {"builder": 4}
    assert out["per_predicate"]["cc_authorized"] == 2
    # S-01 resolves in both dumps, S-02 only where CLAUSE_B exists
    rows = {r["id"]: r for r in out["ref_rows"]}
    assert len(rows["S-01"]["hits"]) == 2
    assert len(rows["S-02"]["hits"]) == 1


def test_unresolved_and_uncheckable_fail(tmp_path, dumps, capsys):
    cands = [
        _cand("S-BAD", {"file": "global/BASE-AGENTS.md", "clause_sha256": "ee" * 32}),
        _cand("S-NOREF", {"file": "global/BASE-AGENTS.md"}),  # no hash
    ]
    rc = cli.main(["candidates", "check", "--parse-dump", dumps[1],
                   "--candidates", _write(tmp_path, cands), "--format", "json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["ok"] is False
    assert out["clause_refs"]["unresolved_ids"] == ["S-BAD"]
    assert out["clause_refs"]["uncheckable_ids"] == ["S-NOREF"]


def test_resolve_findings_are_not_errors(tmp_path, dumps, capsys):
    # a candidate RESOLVE repairs (write-scope) and one it rejects (wildcard)
    # still exit 0 when every clause_ref resolves: repairs/rejects are findings
    cands = [
        _cand("S-WS", {"file": "global/BASE-AGENTS.md", "clause_sha256": "aa" * 32},
              tools=("cron.list", "cron.edit")),
        _cand("S-WILD", {"file": "global/BASE-AGENTS.md", "clause_sha256": "aa" * 32},
              tools=("*",)),
    ]
    rc = cli.main(["candidates", "check", "--parse-dump", dumps[0],
                   "--candidates", _write(tmp_path, cands), "--format", "json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["ok"] is True
    assert out["resolve_classes"].get("write-scope", 0) >= 1
    assert out["resolve_classes"].get("unscoped-wildcard", 0) == 1
    assert out["resolve_outcomes"].get("REJECT", 0) == 1


def test_bad_dump_errors(tmp_path, capsys):
    bad = tmp_path / "notadump.json"
    bad.write_text(json.dumps({"nope": 1}))
    rc = cli.main(["candidates", "check", "--parse-dump", str(bad),
                   "--candidates", _write(tmp_path, []), "--format", "json"])
    assert rc == 1


def test_action_key_profile_independent():
    # the key hashes agent|ts|vtool|segment only — no profile input exists
    key = replay._action_key("synthetic-agent", "2026-05-01T10:00",
                             "cron.edit", "openclaw cron edit job-synth-1")
    import hashlib
    want = hashlib.sha256(
        b"synthetic-agent|2026-05-01T10:00|cron.edit|openclaw cron edit job-synth-1"
    ).hexdigest()
    assert key == want


def test_action_key_same_across_profiles(tmp_path):
    """The same synthetic archive replayed under spike-parity and pinned
    profiles yields identical action_key sets, so hand labels join either."""
    from tests.test_replay import ARCHIVE_LINES
    d = tmp_path / "agents" / "mainagent" / "session-sqlite-import-archive"
    d.mkdir(parents=True)
    with open(d / "s1.jsonl.imported-1", "w", encoding="utf-8") as f:
        for line in ARCHIVE_LINES:
            f.write(json.dumps(line) + "\n")
    archive = str(tmp_path / "agents")

    pinned_rules = [{
        "id": "SYN-PIN-01", "type": "PRECONDITION", "predicate": "cc_authorized",
        "params": {}, "tools": ["cron.disable"], "subjects": ["*"],
        "clause_ref": {}, "src": {}, "votes": "", "origin": "builder",
        "resolve": [],
    }]
    keys = {}
    for profile, rules in (("spike-parity", None), ("pinned", pinned_rules)):
        agg, actions = replay.replay_stream("legacy-archive", archive, profile,
                                            pinned_rules=rules)
        out = tmp_path / f"run-{profile}"
        replay.write_run_dir(str(out), agg, actions, profile)
        with open(out / "actions.jsonl", encoding="utf-8") as f:
            keys[profile] = sorted(json.loads(l)["action_key"] for l in f)
    assert keys["spike-parity"] == keys["pinned"]
    assert len(keys["pinned"]) > 0
