"""Report tests: mock logs never evaluate hypotheses; invalid gate exit 3;
prereg-hash mismatch refusal."""

import json
from pathlib import Path

import pytest

from memdoc.report import build_report, render
from memdoc.runner import run_mock


@pytest.fixture(scope="module")
def runlog(tmp_path_factory):
    out = tmp_path_factory.mktemp("report-run")
    _, log = run_mock(["a0", "astar", "a1", "a4"], [5000], [0], out,
                      storyline_ids=["c2s0", "c3s0", "c7s0"])
    return log


def test_mock_report_never_evaluates_hypotheses(runlog):
    report, code = build_report(runlog)
    assert report["hypotheses"] == "hypotheses not evaluated: mock run"
    assert code == 0
    text = render(report)
    assert "hypotheses not evaluated: mock run" in text
    assert report["banner"] is not None


def test_mock_report_labels_mechanism(runlog):
    report, _ = build_report(runlog)
    assert report["label"] == "context delivery (mechanism)"


def test_report_json_sorted_and_deterministic(runlog):
    r1, _ = build_report(runlog)
    r2, _ = build_report(runlog)
    assert render(r1, "json") == render(r2, "json")
    parsed = json.loads(render(r1, "json"))
    assert list(parsed) == sorted(parsed)


def test_invalid_gate_exit_3(tmp_path, runlog):
    # rewrite the log, breaking every a4 cell's embedding count
    lines = Path(runlog).read_text().splitlines()
    out = []
    for line in lines:
        e = json.loads(line)
        if e.get("event") == "cell" and e["arm"] == "a4":
            e["embedding_calls"] = 0
        out.append(json.dumps(e))
    bad = tmp_path / "bad.jsonl"
    bad.write_text("\n".join(out) + "\n")
    report, code = build_report(bad)
    assert code == 3
    assert not report["validity"]["headline_ok"]
    assert "REFUSED" in render(report)


def test_live_log_with_stale_prereg_hash_refused(tmp_path, runlog):
    lines = Path(runlog).read_text().splitlines()
    out = []
    for line in lines:
        e = json.loads(line)
        if e.get("event") == "run_header":
            e["mode"] = "live"
            e["prereg_hash"] = "deadbeef"
        out.append(json.dumps(e))
    live = tmp_path / "live.jsonl"
    live.write_text("\n".join(out) + "\n")
    report, code = build_report(live)
    assert "REFUSED" in str(report["hypotheses"])
    assert code == 1


def test_live_log_not_tested_arms(tmp_path, runlog):
    from memdoc.prereg import prereg_hash
    lines = Path(runlog).read_text().splitlines()
    out = []
    for line in lines:
        e = json.loads(line)
        if e.get("event") == "run_header":
            e["mode"] = "live"
            e["prereg_hash"] = prereg_hash()
        out.append(json.dumps(e))
    live = tmp_path / "live.jsonl"
    live.write_text("\n".join(out) + "\n")
    report, _ = build_report(live)
    hyp = report["hypotheses"]
    assert isinstance(hyp, dict)
    # a3/a5bg/a5/a2/a6 were not in this run -> their hypotheses are NOT_TESTED
    assert hyp["H3"]["verdict"] == "NOT_TESTED"
    assert hyp["H7"]["verdict"] == "NOT_TESTED"
    assert "not built/run" in hyp["H7"]["reason"]
