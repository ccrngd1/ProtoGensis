"""Reporting refusal of is_mock records; UNKNOWN price cost propagation."""

import pytest

from ensemble_reboot.pricing import Price, PricingTable
from ensemble_reboot.records import MockRecordError, RecordStore
from tests.test_budget import make_record


# ------------------------------------------------------------ is_mock refusal


def test_load_all_refuses_mock_records(tmp_path):
    store = RecordStore(tmp_path, "run1")
    make_record(store, item="q1")
    make_record(store, item="q2", is_mock=True)
    with pytest.raises(MockRecordError, match="is_mock"):
        store.load_all()


def test_load_all_allow_mock_for_tests_only(tmp_path):
    store = RecordStore(tmp_path, "run1")
    make_record(store, item="q1", is_mock=True)
    records = store.load_all(allow_mock=True)
    assert len(records) == 1 and records[0]["is_mock"]


def test_summarize_refuses_mock_run(tmp_path):
    """The reporting entry point must blow up on mock data end to end."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import summarize

    store = RecordStore(tmp_path, "mockrun")
    make_record(store, item="q1", is_mock=True)
    with pytest.raises(MockRecordError):
        summarize.summarize("mockrun", tmp_path)


def test_raw_text_written_and_hashed(tmp_path):
    store = RecordStore(tmp_path, "run1")
    r = make_record(store, item="q1", text="the full response text")
    raw = (tmp_path / "raw_text" / f"{r.record_id}.txt").read_text()
    assert raw == "the full response text"
    assert len(r.response_sha256) == 64


# --------------------------------------------------- UNKNOWN cost propagation


def table(**entries):
    return PricingTable({
        pid: Price(input=i, output=o, cache_read=c, status=s)
        for pid, (i, o, c, s) in entries.items()
    })


def test_known_price_cost():
    t = table(m1=(2.0, 10.0, 0.1, "OK"))
    c = t.cost("m1", 1_000_000, 100_000, 50_000)
    assert c.price_status == "OK"
    assert c.cost_usd == pytest.approx(2.0 + 1.0 + 0.005)
    assert c.conservative_usd == c.cost_usd
    assert not c.conservative_is_estimate


def test_unknown_price_is_never_zero():
    t = table(m1=(2.0, 10.0, 0.1, "OK"), m2=(None, None, None, "UNKNOWN"))
    c = t.cost("m2", 1_000_000, 1_000_000)
    assert c.cost_usd is None                     # NOT 0.0
    assert c.price_status == "UNKNOWN"
    assert c.conservative_is_estimate
    # billed at the highest known rates: 2 + 10
    assert c.conservative_usd == pytest.approx(12.0)


def test_unknown_profile_id_treated_as_unknown():
    t = table(m1=(1.0, 5.0, 0.1, "OK"))
    c = t.cost("never-heard-of-it", 1000, 1000)
    assert c.cost_usd is None
    assert c.price_status == "UNKNOWN"
    assert c.conservative_usd > 0


def test_no_known_prices_at_all_raises():
    t = table(m1=(None, None, None, "UNKNOWN"))
    with pytest.raises(ValueError, match="cannot even bound"):
        t.cost("m1", 1000, 1000)


def test_real_pricing_yaml_loads_with_all_roster_models():
    from pathlib import Path

    from ensemble_reboot.roster import load_roster

    root = Path(__file__).resolve().parent.parent
    t = PricingTable.load(root / "config" / "pricing.yaml")
    roster = load_roster(root / "config" / "roster.yaml")
    for pid in roster.profile_ids:
        assert pid in t.profiles, f"no pricing entry for {pid}"
        p = t.profiles[pid]
        # every entry must have a source; UNKNOWN entries must have null prices
        assert p.source, f"{pid}: missing price source"
        if p.status == "OK":
            assert p.input is not None and p.output is not None


def test_cost_propagates_into_arm_cost():
    from ensemble_reboot.arms import arm_cost_usd

    t = table(m1=(2.0, 10.0, 0.1, "OK"), m2=(None, None, None, "UNKNOWN"))
    known = t.cost("m1", 1000, 1000).cost_usd
    unknown = t.cost("m2", 1000, 1000).cost_usd
    assert arm_cost_usd([known, known]) is not None
    assert arm_cost_usd([known, unknown]) is None  # visibly UNKNOWN, never $0
