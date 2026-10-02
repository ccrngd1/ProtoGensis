"""Ownership lint tests (AC #7): OWN001 + exit 1 for a wrong-unit Ledger,
replay divergence -> OWN002, aligned -> exit 0."""
import json

from coherencegate.audit.ownership_lint import lint_replay, lint_static, run

WRONG_UNIT = {
    "guard": {"unit": {"kind": "tool_call", "name": "write_file"}, "limit": 20},
    "task": {"graded_unit": {"kind": "tool_call", "name": "run"}},
}
ALIGNED = {
    "guard": {"unit": {"kind": "tool_call", "name": "run"}, "limit": 20},
    "task": {"graded_unit": {"kind": "tool_call", "name": "run"}},
}


def _draw(resource, amount):
    return {"kind": "draw", "payload": {"resource": resource, "amount": amount}}


def test_static_wrong_unit_gives_own001_exit_1():
    result = lint_static(WRONG_UNIT)
    assert result.exit_code == 1
    assert result.findings[0]["code"] == "OWN001"
    assert "guard counts tool_call:name=write_file" in result.findings[0]["message"]
    assert "grader counts tool_call:name=run" in result.findings[0]["message"]


def test_static_aligned_exit_0():
    result = lint_static(ALIGNED)
    assert result.exit_code == 0
    assert result.findings == []


def test_replay_divergence_gives_own002():
    # guard counted 5 write_file; grader counts 25 run calls > limit 20
    events = [_draw("write_file", 5)] + [_draw("run", 5)] * 5
    result = lint_replay(WRONG_UNIT, events)
    codes = [f["code"] for f in result.findings]
    assert codes == ["OWN001", "OWN002"]
    own2 = result.findings[1]
    assert (own2["guard_count"], own2["graded_count"]) == (5, 25)
    assert result.findings[0]["divergence"] == 20
    assert result.exit_code == 1


def test_replay_aligned_under_limit_exit_0():
    events = [_draw("run", 4)] * 5  # 20 == limit, aligned unit
    result = lint_replay(ALIGNED, events)
    assert result.exit_code == 0


def test_run_from_files(tmp_path):
    config = tmp_path / "wrong.json"
    config.write_text(json.dumps(WRONG_UNIT))
    assert run(str(config)).exit_code == 1
    aligned = tmp_path / "aligned.json"
    aligned.write_text(json.dumps(ALIGNED))
    assert run(str(aligned)).exit_code == 0


def test_config_error_exit_2(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert run(str(bad)).exit_code == 2
    assert run(str(tmp_path / "missing.json")).exit_code == 2
    missing_fields = tmp_path / "mf.json"
    missing_fields.write_text("{}")
    assert run(str(missing_fields)).exit_code == 2
