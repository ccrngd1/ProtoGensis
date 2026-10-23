"""Billed vs attributed cost.

Vote-event records store ATTRIBUTED arm cost (the sum of their parent
proposal calls) in cost_usd; those parents are themselves records, so any
naive sum(cost_usd) double-counts. is_billed()/billed_spend() separate the
two, and the resume pre-seed / summarizer use them.
"""

import json
from pathlib import Path

import pytest

from ensemble_reboot.budget import BudgetGuard
from ensemble_reboot.records import (
    VOTE_MODEL_ID,
    Record,
    RecordStore,
    billed_spend,
    is_billed,
)
from tests.test_budget import make_record

ROOT = Path(__file__).resolve().parent.parent
PILOT_RECORDS = ROOT / "results" / "pilot_2026-10-22" / "records.jsonl"


def vote_record(store, *, item="q1", cost_usd=0.05, **kw):
    r = Record(
        record_id=Record.new_id(), run_id=store.run_id, stage="stage1",
        arm=kw.get("arm", "a2"), task_set="gpqa", item_id=item, item_sha256="x",
        seed=0, model_id=VOTE_MODEL_ID, family="n/a", effort="high",
        request_params={"aggregation": "majority-vote"}, stop_reason=None,
        usage={}, input_tokens=0, output_tokens=0, cache_read_tokens=0,
        cost_usd=cost_usd, price_status="OK", latency_s=0.0,
        extracted_answer="A", correct=True,
        billed=False, attributed_cost_usd=cost_usd,
    )
    store.append(r)
    return r


# -------------------------------------------------------------- the helpers

def test_is_billed_prefers_explicit_field():
    assert is_billed({"billed": True, "model_id": VOTE_MODEL_ID})
    assert not is_billed({"billed": False, "model_id": "real-model"})


def test_is_billed_falls_back_to_model_id_for_old_records():
    # records written before the `billed` field existed
    assert is_billed({"model_id": "global.anthropic.claude-opus-5-5"})
    assert not is_billed({"model_id": VOTE_MODEL_ID})


def test_billed_spend_excludes_vote_events(tmp_path):
    store = RecordStore(tmp_path, "run1")
    make_record(store, item="q1", cost_usd=1.0)
    make_record(store, item="q2", cost_usd=2.0)
    vote_record(store, item="q1", cost_usd=3.0)   # attributes q1+q2
    records = store.load_all()
    assert billed_spend(records) == pytest.approx(3.0)
    # the naive sum double-counts
    assert sum(r["cost_usd"] for r in records) == pytest.approx(6.0)


def test_vote_events_marked_not_billed_by_runner_field(tmp_path):
    store = RecordStore(tmp_path, "run1")
    v = vote_record(store, cost_usd=0.5)
    d = store.load_all()[0]
    assert d["billed"] is False
    assert d["attributed_cost_usd"] == 0.5
    assert not is_billed(d)
    assert not is_billed(v)   # dataclass form too


# ------------------------------------------------------- resume pre-seeding

def test_resume_preseeds_billed_records_only(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "run_pilot", ROOT / "scripts" / "run_pilot.py")
    rp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rp)

    store = RecordStore(tmp_path, "run1")
    make_record(store, item="q1", cost_usd=1.0)
    make_record(store, item="q2", cost_usd=2.0)
    vote_record(store, item="q1", cost_usd=3.0)
    # an old-style vote event without the billed field: model_id fallback
    old_vote = vote_record(store, item="q2", cost_usd=1.5)
    lines = store.records_path.read_text().splitlines()
    d = json.loads(lines[-1])
    del d["billed"], d["attributed_cost_usd"]
    lines[-1] = json.dumps(d)
    store.records_path.write_text("\n".join(lines) + "\n")

    guard = BudgetGuard(cap_usd=100.0)
    total = rp.preseed_guard(store, guard, log=lambda *a: None)
    assert total == pytest.approx(3.0)          # API records only
    assert guard.spent_known == pytest.approx(3.0)


# ------------------------------------------------------------ the real data

@pytest.mark.skipif(not PILOT_RECORDS.exists(), reason="pilot records absent")
def test_pilot_2026_10_22_billed_and_attributed_totals():
    records = [json.loads(l) for l in PILOT_RECORDS.read_text().splitlines() if l]
    assert len(records) == 1139
    assert billed_spend(records) == pytest.approx(75.4628, abs=1e-4)
    votes = [r for r in records if not is_billed(r)]
    assert len(votes) == 90
    assert sum(r["cost_usd"] for r in votes) == pytest.approx(12.4328, abs=1e-4)
    assert sum(1 for r in records if is_billed(r)) == 1049
