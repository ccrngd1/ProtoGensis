"""Adapter tests incl. legacy/trajectory parity (AC #10)."""

from pathlib import Path

import pytest

from policygate import normalize as norm
from policygate.adapters import legacy_jsonl, trajectory

FIX = Path(__file__).parent.parent / "fixtures" / "adapters"


def _actions_from_events(events):
    out = []
    for ev in events:
        if ev.get("type") != "call" or ev.get("tool") != "exec":
            continue
        cmd = str((ev.get("args") or {}).get("command", ""))
        for a in norm.normalize_exec(cmd)["actions"]:
            out.append(a["vtool"])
    return out


def test_legacy_trajectory_parity():
    legacy_events = list(legacy_jsonl.read_file(str(FIX / "pair_legacy.jsonl"), str(FIX)))
    traj_events = list(trajectory.read_bundle(str(FIX / "pair_trajectory")))
    assert _actions_from_events(legacy_events) == _actions_from_events(traj_events)
    assert _actions_from_events(legacy_events) == ["gateway.restart", "cron.disable"]


def test_trajectory_typed_principals():
    events = list(trajectory.read_bundle(str(FIX / "pair_trajectory")))
    turns = [e for e in events if e["type"] == "turn"]
    assert all(t["provenance_source"] == "typed" for t in turns)
    assert all(t["principal"] == "cc_direct" for t in turns)


def test_unknown_schema_version():
    with pytest.raises(trajectory.TrajectorySchemaError):
        list(trajectory.read_bundle(str(FIX / "bad_version")))


def test_legacy_is_heuristic():
    events = list(legacy_jsonl.read_file(str(FIX / "pair_legacy.jsonl"), str(FIX)))
    turns = [e for e in events if e["type"] == "turn"]
    assert all(t["provenance_source"] == "heuristic" for t in turns)
