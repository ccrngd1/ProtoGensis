"""summarize.py spend accounting and latency exclusions.

A spend total must never add vote rows on top of their parents (their cost is
attributed, not billed), and records on the documented latency-exclusion list
are dropped from p50/p95 latency only (kept in accuracy and cost).
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from ensemble_reboot.records import RecordStore
from tests.test_billed_spend import vote_record
from tests.test_budget import make_record

ROOT = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location(
    "summarize", ROOT / "scripts" / "summarize.py")
summarize_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summarize_mod)


def run_summary(tmp_path, monkeypatch, exclusions=None):
    monkeypatch.setattr(summarize_mod, "load_latency_exclusions",
                        lambda path=None: exclusions or {})
    summarize_mod.summarize("run1", tmp_path)
    return json.loads((tmp_path / "run1" / "summary.json").read_text())


def test_spend_total_excludes_vote_events(tmp_path, monkeypatch):
    store = RecordStore(tmp_path, "run1")
    make_record(store, item="q1", cost_usd=1.0)
    make_record(store, item="q2", cost_usd=2.0)
    vote_record(store, item="q1", cost_usd=3.0)
    summary = run_summary(tmp_path, monkeypatch)
    assert summary["spend"]["billed_usd"] == pytest.approx(3.0)
    assert summary["spend"]["billed_calls"] == 2
    assert summary["spend"]["attributed_vote_usd"] == pytest.approx(3.0)
    assert summary["spend"]["vote_records"] == 1
    md = (tmp_path / "run1" / "summary.md").read_text()
    assert "Billed spend: $3.0000" in md
    assert "$3.0000" in md and "NOT billed" in md


def test_vote_rows_labeled_attributed(tmp_path, monkeypatch):
    store = RecordStore(tmp_path, "run1")
    make_record(store, item="q1", cost_usd=1.0)
    vote_record(store, item="q1", cost_usd=1.0)
    summary = run_summary(tmp_path, monkeypatch)
    by_arm = {c["arm"]: c for c in summary["cells"]}
    assert by_arm["a1"]["cost_is_attributed"] is False
    assert by_arm["a2"]["cost_is_attributed"] is True   # the vote row
    md = (tmp_path / "run1" / "summary.md").read_text()
    assert "attr." in md


def test_latency_exclusions_affect_latency_only(tmp_path, monkeypatch):
    store = RecordStore(tmp_path, "run1")
    fast = [make_record(store, item=f"q{i}", cost_usd=0.5) for i in range(4)]
    # one SIGSTOP-inflated record: huge latency, same cell
    slow = make_record(store, item="q9", cost_usd=0.5)
    lines = store.records_path.read_text().splitlines()
    d = json.loads(lines[-1])
    d["latency_s"] = 600.0
    lines[-1] = json.dumps(d)
    store.records_path.write_text("\n".join(lines) + "\n")

    excl = {slow.record_id: "SIGSTOP artifact"}
    summary = run_summary(tmp_path, monkeypatch, exclusions=excl)
    cell = summary["cells"][0]
    # latency ignores the 600s record...
    assert cell["latency"]["p95"] < 600
    assert cell["latency_excluded_records"] == 1
    # ...but n and cost keep it
    assert cell["n"] == 5
    assert cell["cost_usd_known"] == pytest.approx(2.5)
    assert summary["latency_exclusions"] == {slow.record_id: "SIGSTOP artifact"}


def test_real_exclusion_config_lists_the_three_sigstop_records():
    excl = summarize_mod.load_latency_exclusions(
        ROOT / "config" / "latency_exclusions.yaml")
    assert set(excl) == {"5047626ad9554cd4", "de26961352b24f30",
                        "2aaa7145744e462c"}
    assert all("SIGSTOP" in r for r in excl.values())
