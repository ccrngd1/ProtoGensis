"""CLI tests (AC #11): byte-identical --json across runs, exit codes, report
rebuilt from the run log alone. Uses cli.main(argv) directly and
[sys.executable, "-m", "coherencegate"] via subprocess, never PATH."""
import json
import subprocess
import sys

import pytest

from coherencegate.cli import main

CONFIG_DIR = "coherencegate/demos/config"


def run_cli(argv):
    return subprocess.run([sys.executable, "-m", "coherencegate", *argv],
                          capture_output=True, text=True)


@pytest.mark.parametrize("demo", ["budget", "identifiability", "telecom",
                                  "single-agent", "warmup"])
def test_demo_json_byte_identical_across_runs(demo, capsys):
    outs = []
    for _ in range(2):
        assert main(["demo", demo, "--format", "json"]) == 0
        outs.append(capsys.readouterr().out)
    assert outs[0] == outs[1]
    payload = json.loads(outs[0])
    text = outs[0]
    assert "/tmp" not in text and "/root" not in text  # no absolute paths
    assert isinstance(payload, dict)


def test_demo_banner_via_subprocess():
    result = run_cli(["demo", "budget"])
    assert result.returncode == 0
    assert "reproduction-style, not a replication of paper numbers" in result.stdout


def test_identifiability_demo_json_has_bound():
    result = run_cli(["demo", "identifiability", "--format", "json"])
    assert result.returncode == 0
    assert '"bound"' in result.stdout


def test_telecom_and_single_agent_print_tie():
    for demo in ("telecom", "single-agent"):
        result = run_cli(["demo", demo])
        assert result.returncode == 0
        assert "tie" in result.stdout.lower()


def test_lint_exit_codes():
    wrong = run_cli(["lint", "ownership", "--config", f"{CONFIG_DIR}/wrong_unit.json"])
    assert wrong.returncode == 1
    assert "OWN001" in wrong.stdout
    aligned = run_cli(["lint", "ownership", "--config", f"{CONFIG_DIR}/aligned.json"])
    assert aligned.returncode == 0


def test_lint_replay_own002(tmp_path):
    runlog = tmp_path / "run.jsonl"
    events = ([{"seq": i, "t": i, "run_id": "r", "arm": "", "seed": 0, "agent": "a",
                "kind": "draw", "payload": {"resource": "run", "amount": 5}}
               for i in range(5)]
              + [{"seq": 5, "t": 5, "run_id": "r", "arm": "", "seed": 0, "agent": "a",
                  "kind": "draw", "payload": {"resource": "write_file", "amount": 5}}])
    runlog.write_text("\n".join(json.dumps(e) for e in events))
    result = run_cli(["lint", "ownership", "--config", f"{CONFIG_DIR}/wrong_unit.json",
                      "--runlog", str(runlog)])
    assert result.returncode == 1
    assert "OWN002" in result.stdout


def test_lint_config_error_exit_2(tmp_path):
    missing = run_cli(["lint", "ownership", "--config", str(tmp_path / "nope.json")])
    assert missing.returncode == 2


def test_audit_identifiability_exit_codes():
    aliased = run_cli(["audit", "identifiability", "--variant", "aliased"])
    assert aliased.returncode == 1  # aliased fiber found
    identifiable = run_cli(["audit", "identifiability", "--variant", "identifiable"])
    assert identifiable.returncode == 0


def test_report_from_runlog(tmp_path, capsys):
    from coherencegate.gate import CommitGate
    from coherencegate.owners import Ledger, Unit
    from coherencegate.proposal import Proposal
    from coherencegate.runlog import RunLog, StepClock
    from coherencegate.store import InMemoryStore

    log = RunLog(clock=StepClock(), run_id="t", arm="a", seed=0)
    store = InMemoryStore()
    gate = CommitGate(store, invariants=[Ledger("r", 1, Unit("tool_call", "run"))],
                      runlog=log)
    gate.commit(Proposal("x", "x", draws={"r": 1}))
    gate.commit(Proposal("x", "x", draws={"r": 1}))  # rejected
    path = str(tmp_path / "run.jsonl")
    log.dump(path)

    assert main(["report", "--runlog", path, "--format", "json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["counts"]["accepts"] == 1
    assert report["rejects_by_reason"] == {"invariant": 1}
    assert report["violations_prevented"] == 1


def test_report_missing_runlog_exit_2(tmp_path):
    result = run_cli(["report", "--runlog", str(tmp_path / "nope.jsonl")])
    assert result.returncode == 2


def test_topology_check_exit_codes(tmp_path):
    star = tmp_path / "star.json"
    star.write_text(json.dumps({"roles": {
        "hub": {"reads": ["a", "b"], "writes": ["a", "b"]},
        "s1": {"reads": ["a"], "writes": ["a"]},
        "s2": {"reads": ["b"], "writes": ["b"]}}}))
    assert run_cli(["topology", "check", "--config", str(star)]).returncode == 0
    cycle = tmp_path / "cycle.json"
    cycle.write_text(json.dumps({"roles": {
        "r1": {"reads": ["a", "b"], "writes": []},
        "r2": {"reads": ["b", "c"], "writes": []},
        "r3": {"reads": ["c", "a"], "writes": []}}}))
    result = run_cli(["topology", "check", "--config", str(cycle)])
    assert result.returncode == 1
    assert "pairwise reconciliation insufficient" in result.stdout


def test_budget_seeds_and_arms_flags(capsys):
    assert main(["demo", "budget", "--seeds", "0,1", "--arms", "ordinary,ledger",
                 "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["config_seeds"] == [0, 1]
    assert [s["arm"] for s in payload["summary"]] == ["ordinary", "ledger"]
