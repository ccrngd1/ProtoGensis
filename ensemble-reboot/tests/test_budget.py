"""BudgetGuard: cap enforcement (counting in-flight) and resume skip logic."""

import threading

import pytest

from ensemble_reboot.budget import BudgetExceeded, BudgetGuard
from ensemble_reboot.records import Record, RecordStore


def make_record(store, *, stage="stage0", arm="a1", ts="gpqa", item="q1",
                model="m", effort="high", seed=0, **kw):
    r = Record(
        record_id=Record.new_id(), run_id=store.run_id, stage=stage, arm=arm,
        task_set=ts, item_id=item, item_sha256="x", seed=seed, model_id=model,
        family="fam", effort=effort, request_params={}, stop_reason="end_turn",
        usage={}, input_tokens=10, output_tokens=5, cache_read_tokens=0,
        cost_usd=kw.get("cost_usd", 0.01), price_status=kw.get("price_status", "OK"),
        latency_s=1.0, extracted_answer="A", correct=True,
        is_mock=kw.get("is_mock", False),
    )
    store.append(r, response_text=kw.get("text", ""))
    return r


def test_cap_blocks_next_call():
    g = BudgetGuard(cap_usd=1.0, reserve_per_call_usd=0.25)
    with g.reserve():
        g.settle(0.9, 0.9)
    # spent 0.9 + one reservation 0.25 > 1.0
    with pytest.raises(BudgetExceeded):
        with g.reserve():
            pass


def test_inflight_reservations_counted():
    g = BudgetGuard(cap_usd=1.0, reserve_per_call_usd=0.4)
    r1 = g.reserve()
    r2 = g.reserve()
    r1.__enter__()
    r2.__enter__()
    # 2 in-flight * 0.4 = 0.8; a third (1.2) would exceed the cap
    with pytest.raises(BudgetExceeded):
        with g.reserve():
            pass
    r1.__exit__(None, None, None)
    r2.__exit__(None, None, None)
    # after release there is room again
    with g.reserve():
        g.settle(0.1, 0.1)


def test_unknown_cost_settles_conservative():
    g = BudgetGuard(cap_usd=10.0)
    with g.reserve():
        g.settle(None, 2.5)   # UNKNOWN price billed at max known rate
    assert g.spent_conservative == 2.5
    assert g.spent_known == 0.0
    assert g.unknown_price_calls == 1
    s = g.status()
    assert s["unknown_price_calls"] == 1


def test_concurrent_reserves_never_exceed_cap():
    g = BudgetGuard(cap_usd=2.0, reserve_per_call_usd=0.5)
    granted = []
    denied = []
    lock = threading.Lock()

    def worker():
        try:
            with g.reserve():
                with lock:
                    granted.append(1)
                g.settle(0.5, 0.5)
        except BudgetExceeded:
            with lock:
                denied.append(1)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert g.spent_conservative <= 2.0
    assert len(granted) <= 4
    assert len(granted) + len(denied) == 10


def test_resume_skips_existing_records(tmp_path):
    store = RecordStore(tmp_path, "run1")
    make_record(store, item="q1", seed=0)
    make_record(store, item="q2", seed=0)
    keys = store.existing_keys()
    assert ("stage0", "a1", "gpqa", "q1", "m", "high", 0) in keys
    assert ("stage0", "a1", "gpqa", "q2", "m", "high", 0) in keys
    # a different seed is NOT covered -> would be re-run
    assert ("stage0", "a1", "gpqa", "q1", "m", "high", 1) not in keys

    # simulate resume: only dispatch calls whose key is absent
    planned = [("q1", 0), ("q1", 1), ("q3", 0)]
    todo = [(i, s) for i, s in planned
            if ("stage0", "a1", "gpqa", i, "m", "high", s) not in keys]
    assert todo == [("q1", 1), ("q3", 0)]


def test_resume_preseeds_guard(tmp_path):
    import json

    store = RecordStore(tmp_path, "run1")
    make_record(store, item="q1", cost_usd=1.0, price_status="OK")
    make_record(store, item="q2", cost_usd=1.0, price_status="OK")
    make_record(store, item="q3", cost_usd=None, price_status="UNKNOWN")

    # same pre-seeding path as scripts/run_pilot.py live_run()
    g = BudgetGuard(cap_usd=2.5, reserve_per_call_usd=0.6)
    with open(store.records_path) as f:
        for line in f:
            r = json.loads(line)
            if r.get("price_status") == "OK":
                g.settle(r["cost_usd"], r["cost_usd"])

    assert g.spent_conservative == 2.0
    assert g.unknown_price_calls == 0
    # 2.0 spent + 0.6 reserve > 2.5 cap
    with pytest.raises(BudgetExceeded):
        with g.reserve():
            pass


def test_record_refuses_token_leak(tmp_path):
    store = RecordStore(tmp_path, "run1")
    r = Record(
        record_id=Record.new_id(), run_id="run1", stage="stage0", arm="a1",
        task_set="gpqa", item_id="q1", item_sha256="x", seed=0, model_id="m",
        family="fam", effort="high",
        request_params={"headers": {"Authorization": "Bearer secret"}},
        stop_reason=None, usage={}, input_tokens=0, output_tokens=0,
        cache_read_tokens=0, cost_usd=None, price_status="UNKNOWN",
        latency_s=0.0, extracted_answer=None, correct=None,
    )
    with pytest.raises(ValueError, match="auth header"):
        store.append(r)
