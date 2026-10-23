"""The cap must bound WORST-CASE spend, not average spend.

The old guard reserved a fixed $0.25 per in-flight call; a frontier call at
max effort can bill ~$1.61 (32,000 output tokens x $50/M), so 8 workers could
overshoot the cap by ~$13. The fix reserves each call's own worst case
(estimated input + the request's max_tokens of output, priced conservatively)
and admits a call only if spent + sum(in-flight reservations) + this
reservation <= cap.
"""

import threading

import pytest

from ensemble_reboot.budget import (
    BudgetExceeded,
    BudgetGuard,
    estimate_input_tokens,
)
from ensemble_reboot.client import ConverseResult
from ensemble_reboot.pilot import PilotRunner, PlannedCall
from ensemble_reboot.pricing import Price, PricingTable
from ensemble_reboot.records import RecordStore
from ensemble_reboot.roster import ModelSpec, Roster

MAX_TOKENS = 32000
# $10/M input, $50/M output: 32k output alone bills $1.60 (the fable-5-1 case)
PRICING = PricingTable({"m1": Price(input=10.0, output=50.0,
                                    cache_read=None, status="OK")})


class FakeItem:
    def __init__(self, i):
        self.item_id = f"q{i}"
        self.item_sha256 = "x"
        self.prompt = f"question {i}: pick a letter"
        self.correct_letter = "A"


class AdversarialClient:
    """Every call returns the maximum possible output tokens."""

    def __init__(self, attempts_per_call=None):
        self.calls = 0
        self._lock = threading.Lock()
        self.attempts_per_call = attempts_per_call or []

    def converse(self, spec, prompt, level, max_tokens=MAX_TOKENS,
                 system_prompt=None):
        with self._lock:
            self.calls += 1
        return ConverseResult(
            status_code=200, text="Answer: A", stop_reason="max_tokens",
            usage={"inputTokens": len(prompt) // 4, "outputTokens": max_tokens},
            latency_s=0.1, request_params={"inferenceConfig": {}},
            attempts=list(self.attempts_per_call),
        )


def make_runner(tmp_path, cap_usd, n_items=20, client=None):
    spec = ModelSpec(profile_id="m1", family="fam", tier="frontier",
                     effort_style="claude", candidate_levels=["high"],
                     default_level="high")
    roster = Roster(region="us-east-1", models=[spec],
                    default_max_tokens=MAX_TOKENS, arms={})
    items = [FakeItem(i) for i in range(n_items)]
    store = RecordStore(tmp_path, "run1")
    guard = BudgetGuard(cap_usd=cap_usd)
    runner = PilotRunner(roster, PRICING, store, guard,
                         client or AdversarialClient(),
                         {"gpqa": items}, max_workers=8)
    plan = [PlannedCall("stage0", "a1", "gpqa", it.item_id, "m1", "high", 0)
            for it in items]
    return runner, guard, plan


def test_adversarial_max_output_never_exceeds_cap(tmp_path):
    """8 threads, every call billing its absolute maximum: the final spend
    must stay under the cap, with the excess calls refused."""
    cap = 5.0
    runner, guard, plan = make_runner(tmp_path, cap)
    with pytest.raises(BudgetExceeded):
        runner._run_parallel(plan, progress=lambda *a: None)
    assert guard.spent_conservative <= cap
    # the cap is ~3 worst-case calls (~$1.6 each); something must have run
    assert 0 < guard.spent_known <= cap


def test_adversarial_cap_holds_across_many_caps(tmp_path):
    for i, cap in enumerate((2.0, 3.3, 7.9)):
        runner, guard, plan = make_runner(tmp_path / str(i), cap)
        try:
            runner._run_parallel(plan, progress=lambda *a: None)
        except BudgetExceeded:
            pass
        assert guard.spent_conservative <= cap, f"cap {cap} overshot"


def test_old_fixed_reservation_overshoots():
    """The pre-fix behavior: a fixed $0.25 reservation admits 8 concurrent
    worst-case calls under a $5 cap, and when each bills $1.61 the total blows
    past the cap. This is what the per-call worst-case reservation prevents."""
    g = BudgetGuard(cap_usd=5.0, reserve_per_call_usd=0.25)
    # all 8 workers get admitted while their calls are in flight: the fixed
    # reservation projects only 8 x 0.25 = $2 against the $5 cap
    reservations = [g.reserve() for _ in range(8)]
    for r in reservations:
        r.__enter__()
    # ...then each in-flight call bills its real worst case
    for r in reservations:
        g.settle(1.61, 1.61)   # frontier call at max effort
        r.__exit__(None, None, None)
    # all 8 were admitted (8 x 0.25 = $2 of reservations under a $5 cap)...
    assert g.spent_conservative == pytest.approx(8 * 1.61)
    # ...and the cap was blown by ~$8
    assert g.spent_conservative > g.cap_usd


def test_worst_case_reservation_blocks_concurrent_overshoot():
    """Same adversarial schedule as above, but reserving each call's worst
    case: only 3 of 8 calls fit under the cap; the rest are refused BEFORE
    dispatch and the total never exceeds the cap."""
    g = BudgetGuard(cap_usd=5.0)
    worst = 1.61
    start = threading.Barrier(8)
    granted, denied = [], []
    lock = threading.Lock()

    def worker():
        start.wait()
        try:
            with g.reserve(worst):
                with lock:
                    granted.append(1)
                g.settle(worst, worst)
        except BudgetExceeded:
            with lock:
                denied.append(1)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert g.spent_conservative <= g.cap_usd
    assert len(granted) == 3          # floor(5.0 / 1.61)
    assert len(denied) == 5


def test_estimate_input_tokens_bounds():
    # chars/2 is far above the ~1 token / 4 chars of English text
    assert estimate_input_tokens("x" * 400) == 200
    # system prompt counts
    assert estimate_input_tokens("x" * 400, "y" * 100) == 250
    # measured tokens take precedence, with 25% headroom
    assert estimate_input_tokens("x" * 400, None, measured_input_tokens=100) == 126


def test_reserve_default_falls_back_to_fixed():
    g = BudgetGuard(cap_usd=1.0, reserve_per_call_usd=0.6)
    r1 = g.reserve()
    r1.__enter__()
    with pytest.raises(BudgetExceeded):
        with g.reserve():
            pass
    r1.__exit__(None, None, None)
