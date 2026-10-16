"""Clause-class routing (AC #17e, phase 3 item 4): non-gateable candidate
classes (obligation, text-only, ambiguous) never produce a BLOCK; runtime-
predicate classes (temporal, ordering, counting) may gate. compile and
candidates check report the routing per class. Synthetic data only."""

import json

from policygate import pinning, replay, rules as rules_mod


def _cand(rid, cls, predicate="cc_authorized", tools=("file.edit",)):
    return {"id": rid, "polarity": "block_until_true", "predicate": predicate,
            "params": {}, "tools": list(tools), "subjects": ["*"],
            "class": cls, "origin": "builder", "clause_ref": {"builtin": "t"}}


def test_route_rules_splits_by_class():
    rules = [rules_mod.candidate_to_rule(c) for c in [
        _cand("G1", "gateable"),
        _cand("T1", "temporal", predicate="quiet_hours_utc"),
        _cand("O1", "ordering", predicate="checkpoint_seen"),
        _cand("C1", "counting", predicate="attempts_lt"),
        _cand("B1", "obligation"),
        _cand("A1", "ambiguous"),
        _cand("X1", "text-only"),
    ]]
    routed = pinning.route_rules(rules)
    assert [r["id"] for r in routed["gating"]] == ["G1", "T1", "O1", "C1"]
    assert [r["id"] for r in routed["obligation"]] == ["B1"]
    assert [r["id"] for r in routed["ambiguous"]] == ["A1"]
    assert [r["id"] for r in routed["text_only"]] == ["X1"]


def test_routing_table():
    table = pinning.routing_table([
        _cand("G1", "gateable"), _cand("B1", "obligation"),
        _cand("A1", "ambiguous"), _cand("X1", "text-only"),
        _cand("T1", "temporal"),
    ])
    assert table["gateable"] == {"count": 1, "routing": "gate"}
    assert table["temporal"] == {"count": 1, "routing": "gate"}
    assert table["obligation"] == {"count": 1, "routing": "obligations_report"}
    assert table["ambiguous"] == {"count": 1, "routing": "ambiguity_item"}
    assert table["text-only"] == {"count": 1, "routing": "not_evaluated"}


def test_obligation_candidate_never_blocks_file_edit(tmp_path):
    """The phase-3 host finding: an obligation-class cc_authorized candidate on
    file.edit fired BLOCK on ~4,180 edits. Obligations are not gates."""
    d = tmp_path / "agents" / "mainagent" / "session-sqlite-import-archive"
    d.mkdir(parents=True)
    lines = [
        {"timestamp": "2026-05-01T10:00:00Z",
         "message": {"role": "user", "content": "tidy the notes"}},
        {"timestamp": "2026-05-01T10:00:05Z",
         "message": {"role": "assistant", "content": [
             {"type": "toolCall", "name": "edit",
              "arguments": {"path": "notes.md", "oldText": "a", "newText": "b"}},
         ]}},
    ]
    with open(d / "s1.jsonl.imported-1", "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")
    obligation = rules_mod.candidate_to_rule(_cand("OBL-01", "obligation"))
    agg, actions = replay.replay_stream("legacy-archive", str(tmp_path / "agents"),
                                        "pinned", pinned_rules=[obligation])
    a = actions[0]
    assert all(v != "BLOCK" for v in a["verdicts"].values())
    assert agg["verdict_classes"]["strict"]["BLOCK"] == 0


def test_compile_report_carries_class_routing(tmp_path):
    import os
    import subprocess
    import sys
    from policygate import emit
    repo_dir = os.path.dirname(os.path.dirname(__file__))
    repo = tmp_path / "repo"
    subprocess.run([sys.executable,
                    os.path.join(repo_dir, "tests", "fixtures", "make_policy_repo.py"),
                    str(repo)], check=True, capture_output=True)
    report, _ = emit.compile_bundle(
        str(repo), os.path.join(repo_dir, "fixtures", "bundle.synthetic.toml"),
        "2026-03-01T00:00:00Z",
        os.path.join(repo_dir, "fixtures", "candidates", "synthetic.json"))
    cr = report["class_routing"]
    assert cr["gateable"]["routing"] == "gate"
    assert cr["temporal"]["routing"] == "gate"
    assert cr["ordering"]["routing"] == "gate"
    md = emit.render_report(report, "md")
    assert "Replay routing per clause class" in md


def test_candidates_check_reports_class_routing(tmp_path, capsys):
    from policygate import cli
    dump = tmp_path / "dump.json"
    dump.write_text(json.dumps({"at": "t", "clauses": []}))
    cands = tmp_path / "cands.json"
    cands.write_text(json.dumps({"synthetic": True, "candidates": [
        _cand("B1", "obligation"), _cand("G1", "gateable")]}))
    rc = cli.main(["candidates", "check", "--parse-dump", str(dump),
                   "--candidates", str(cands), "--format", "json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["class_routing"]["obligation"] == \
        {"count": 1, "routing": "obligations_report"}
    assert out["class_routing"]["gateable"] == {"count": 1, "routing": "gate"}
