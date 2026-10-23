"""Regression tests for scripts/estimate_full_run.py arm cost math.

Covers three bugs found while producing the pilot cost estimate:
  1. a2/a3 scaling multiplied every numeric dict value, so the boolean
     'unknown' flag (False*5 == 0) lost its type and the 'fallback' flag was
     dropped entirely.
  2. a4 panel costs ignored each member's own default level when asked for
     the as-measured ("default") combination.
  3. The 10th-percentile index used int(0.1*n)-1 which is index -1 -> the MAX
     output token count for n=10, inverting the lo/hi range.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "estimate_full_run", ROOT / "scripts" / "estimate_full_run.py")
efr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(efr)

from ensemble_reboot.pricing import PricingTable, Price  # noqa: E402
from ensemble_reboot.roster import load_roster  # noqa: E402


def _rec(model, effort, ts, in_t, out_t, arm="a1"):
    return {"model_id": model, "effort": effort, "task_set": ts, "arm": arm,
            "usage": {"x": 1}, "input_tokens": in_t, "output_tokens": out_t,
            "record_id": "r"}


def _pricing():
    return PricingTable({
        "m1": Price(input=1.0, output=2.0, cache_read=0.1, status="OK"),
    })


def test_token_model_percentile_band_ordered():
    # outputs 100..1000: lo must be the 10th pct (100), not the max
    recs = [_rec("m1", "high", "gpqa", 50, 100 * (i + 1)) for i in range(10)]
    st = efr.TokenModel(recs).stats("m1", "high", "gpqa")
    assert st["lo_out"] == 100
    assert st["hi_out"] == 900
    assert st["lo_out"] <= st["mean_out"] <= st["hi_out"]


def test_a2_a3_scaling_preserves_flags():
    recs = [_rec("m1", "high", "gpqa", 50, 200) for _ in range(10)]
    tm = efr.TokenModel(recs)
    roster = load_roster(ROOT / "config" / "roster.yaml")
    c1 = efr.arm_cost_per_item("a1", "m1", "high", "gpqa", tm, _pricing(),
                               roster, a2_n=5)
    c2 = efr.arm_cost_per_item("a2", "m1", "high", "gpqa", tm, _pricing(),
                               roster, a2_n=5)
    c3 = efr.arm_cost_per_item("a3", "m1", "high", "gpqa", tm, _pricing(),
                               roster, a2_n=5)
    assert c2["mean"] == 5 * c1["mean"]
    assert c3["mean"] == 7 * c1["mean"]
    for c in (c1, c2, c3):
        assert c["unknown"] is False
        assert c["fallback"] is False
    # fallback effort propagates as a real boolean
    cf = efr.arm_cost_per_item("a2", "m1", "max", "gpqa", tm, _pricing(),
                               roster, a2_n=5)
    assert cf["fallback"] is True


def test_token_model_keys_aggregator_calls_separately():
    """A4 aggregator calls read the problem + all panel responses (~2k input
    tokens in the pilot vs ~300 for a plain call). Pooling them with a1 calls
    of the same (model, effort, set) skews both estimates; TokenModel must key
    by role."""
    plain = [_rec("m1", "high", "gpqa", 300, 500, arm="a1") for _ in range(5)]
    agg = [_rec("m1", "high", "gpqa", 2000, 800, arm="a4a") for _ in range(5)]
    tm = efr.TokenModel(plain + agg)
    st_plain = tm.stats("m1", "high", "gpqa")
    st_agg = tm.stats("m1", "high", "gpqa", role="aggregator")
    assert st_plain["mean_in"] == 300 and st_plain["n"] == 5
    assert st_agg["mean_in"] == 2000 and st_agg["n"] == 5
    assert st_agg["fallback_role"] is False


def test_token_model_persona_calls_keyed_separately():
    """A3 persona calls carry a system prompt: ~2x the plain input tokens."""
    plain = [_rec("m1", "high", "gpqa", 300, 500, arm="a1") for _ in range(5)]
    persona = [_rec("m1", "high", "gpqa", 640, 500, arm="a3") for _ in range(5)]
    tm = efr.TokenModel(plain + persona)
    assert tm.stats("m1", "high", "gpqa")["mean_in"] == 300
    assert tm.stats("m1", "high", "gpqa", role="persona")["mean_in"] == 640


def test_aggregator_stats_fall_back_to_proposal_flagged():
    """With no measured aggregator calls at all, aggregator cost falls back to
    the model's plain-call stats, visibly flagged."""
    plain = [_rec("m1", "high", "gpqa", 300, 500, arm="a1") for _ in range(5)]
    st = efr.TokenModel(plain).stats("m1", "high", "gpqa", role="aggregator")
    assert st["mean_in"] == 300
    assert st["fallback_role"] is True


def test_a4_arm_cost_uses_aggregator_call_tokens():
    roster = load_roster(ROOT / "config" / "roster.yaml")
    panel = roster.arms["a4_panel"]
    agg = roster.arms["a4a_aggregator"]
    pricing = PricingTable({
        pid: Price(input=1.0, output=2.0, cache_read=0.1, status="OK")
        for pid in panel + [agg]})
    recs = []
    for pid in panel:
        recs += [_rec(pid, roster.by_id(pid).default_level, "gpqa", 100, 1000)
                 for _ in range(3)]
    agg_lvl = roster.by_id(agg).default_level
    # the aggregator's own a1 records (small input) must NOT be used...
    recs += [_rec(agg, agg_lvl, "gpqa", 100, 1000, arm="a1") for _ in range(3)]
    # ...its measured aggregator calls (large input) must
    recs += [_rec(agg, agg_lvl, "gpqa", 2000, 1000, arm="a4a") for _ in range(3)]
    tm = efr.TokenModel(recs)
    c = efr.arm_cost_per_item("a4a", None, "default", "gpqa", tm, pricing,
                              roster, a2_n=5)
    # 3 panel at 100in/1000out + 1 aggregator at 2000in/1000out
    expected = (3 * (100 * 1.0 + 1000 * 2.0) + (2000 * 1.0 + 1000 * 2.0)) / 1e6
    assert abs(c["mean"] - expected) < 1e-9
    assert c["fallback_role"] is False


def test_a4_default_effort_uses_each_members_default_level():
    roster = load_roster(ROOT / "config" / "roster.yaml")
    panel = roster.arms["a4_panel"]
    agg = roster.arms["a4a_aggregator"]
    pricing = PricingTable({
        pid: Price(input=1.0, output=2.0, cache_read=0.1, status="OK")
        for pid in panel + [agg]})
    recs = []
    for pid in panel + [agg]:
        lvl = roster.by_id(pid).default_level
        recs += [_rec(pid, lvl, "gpqa", 100, 1000) for _ in range(3)]
        # decoy at a non-default level with 10x the tokens
        other = "low" if lvl != "low" else "medium"
        recs += [_rec(pid, other, "gpqa", 1000, 10000) for _ in range(3)]
    tm = efr.TokenModel(recs)
    c = efr.arm_cost_per_item("a4a", None, "default", "gpqa", tm, pricing,
                              roster, a2_n=5)
    # 4 calls (3 panel + 1 agg) at 100in/1000out: 4*(100*1 + 1000*2)/1e6
    assert abs(c["mean"] - 4 * (100 * 1.0 + 1000 * 2.0) / 1e6) < 1e-9
    assert c["fallback"] is False
    for pid in panel:
        assert f"@{roster.by_id(pid).default_level}" in c["components"] or \
            "default" not in c["components"]
