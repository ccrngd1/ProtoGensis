"""scripts/rekey_labels.py: map an old-key labels file to new keys given two
run dirs of the same archive (AC #19 key change). Synthetic data only."""

import importlib.util
import json
import os

import pytest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                      "scripts", "rekey_labels.py")
spec = importlib.util.spec_from_file_location("rekey_labels", SCRIPT)
rekey_labels = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rekey_labels)


def _run_dir(tmp_path, name, rows):
    d = tmp_path / name
    d.mkdir()
    with open(d / "actions.jsonl", "w", encoding="utf-8") as f:
        for agent, ts, vtool, key in rows:
            f.write(json.dumps({"agent": agent, "ts": ts, "vtool": vtool,
                                "action_key": key}) + "\n")
    return str(d)


def _labels(tmp_path, rows):
    p = tmp_path / "labels.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps({"synthetic": True}) + "\n")
        for key, label in rows:
            f.write(json.dumps({"action_key": key, "label": label,
                                "rubric_rule": "r", "labeller": "builder",
                                "cc_confirmed": False}) + "\n")
    return str(p)


def test_rekey_simple_and_fanout(tmp_path):
    # OLD run: the cmd[:200]-based key collides -> one key covers two actions
    old = _run_dir(tmp_path, "old", [
        ("main", "2026-05-01T10:00", "cron.edit", "oldk-dup"),
        ("main", "2026-05-01T10:00", "cron.edit", "oldk-dup"),
        ("main", "2026-05-01T12:00", "gateway.restart", "oldk-gw"),
    ])
    # NEW run: segment-based keys are distinct
    new = _run_dir(tmp_path, "new", [
        ("main", "2026-05-01T10:00", "cron.edit", "newk-1"),
        ("main", "2026-05-01T10:00", "cron.edit", "newk-2"),
        ("main", "2026-05-01T12:00", "gateway.restart", "newk-gw"),
    ])
    labels = _labels(tmp_path, [("oldk-dup", "unauthorized"),
                                ("oldk-gw", "authorized-explicit")])
    key_map = rekey_labels.build_key_map(rekey_labels.read_actions(old),
                                         rekey_labels.read_actions(new))
    assert sorted(key_map["oldk-dup"]) == ["newk-1", "newk-2"]
    assert key_map["oldk-gw"] == ["newk-gw"]
    rows, stats = rekey_labels.rekey(labels, key_map)
    labelled = {d["action_key"]: d["label"] for d in rows if "action_key" in d}
    # the duplicated old key maps to ALL its new keys with the same label
    assert labelled == {"newk-1": "unauthorized", "newk-2": "unauthorized",
                        "newk-gw": "authorized-explicit"}
    assert stats["fanned_out"] == 1
    assert stats["unmatched"] == 0


def test_rekey_mismatched_runs_error(tmp_path):
    old = _run_dir(tmp_path, "old", [("main", "t1", "cron.edit", "k1")])
    new = _run_dir(tmp_path, "new", [("main", "t2", "cron.edit", "k2")])
    with pytest.raises(ValueError, match="same archive"):
        rekey_labels.build_key_map(rekey_labels.read_actions(old),
                                   rekey_labels.read_actions(new))


def test_check_join(tmp_path):
    run = _run_dir(tmp_path, "run", [("main", "t", "cron.edit", "k-new")])
    joined = _labels(tmp_path, [("k-new", "unauthorized")])
    assert rekey_labels.keys_join(joined, run) is True
    assert rekey_labels.main(["--old-run", run, "--new-run", run,
                              "--labels", joined, "--check-join"]) == 0
    stale = tmp_path / "stale.jsonl"
    stale.write_text(json.dumps({"action_key": "k-old", "label": "x"}) + "\n")
    assert rekey_labels.keys_join(str(stale), run) is False
    assert rekey_labels.main(["--old-run", run, "--new-run", run,
                              "--labels", str(stale), "--check-join"]) == 1


def test_cli_writes_output(tmp_path, capsys):
    old = _run_dir(tmp_path, "old", [("main", "t", "cron.edit", "ok")])
    new = _run_dir(tmp_path, "new", [("main", "t", "cron.edit", "nk")])
    labels = _labels(tmp_path, [("ok", "policy-silent")])
    out = tmp_path / "out.jsonl"
    rc = rekey_labels.main(["--old-run", old, "--new-run", new,
                            "--labels", labels, "--out", str(out)])
    assert rc == 0
    rows = [json.loads(l) for l in open(out, encoding="utf-8") if l.strip()]
    assert any(d.get("action_key") == "nk" and d["label"] == "policy-silent"
               for d in rows)
    # the synthetic header row passes through
    assert any("synthetic" in d for d in rows)
