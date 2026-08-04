"""Re-derive every number in the GnuCOBOL golden master with exact decimal
arithmetic (COBOL truncation semantics), proving the documented business
rules and the fixture agree. This is the same math a faithful Java
translation must produce with BigDecimal + RoundingMode.DOWN.
"""

from decimal import ROUND_DOWN, Decimal
from pathlib import Path

import pytest

GOLDEN = (Path(__file__).resolve().parent.parent
          / "assets" / "samples" / "golden" / "expected_output.txt")

CENT = Decimal("0.01")

# The five hard-coded claims from INPUT-CLAIMS in claimcalc.cbl.
CLAIMS = [
    ("CLM0000001", "PPO", "MD", Decimal("4500.00")),
    ("CLM0000002", "PPO", "MD", Decimal("1234.56")),
    ("CLM0000003", "PPO", "DN", Decimal("300.00")),
    ("CLM0000004", "XXX", "MD", Decimal("500.00")),
    ("CLM0000005", "PPO", "RX", Decimal("75.99")),
]

# BENFTABL.cpy: plan -> (deductible, coinsurance pct, copay)
PLANS = {
    "PPO": (Decimal("500.00"), Decimal("0.20"), Decimal("25.00")),
    "HMO": (Decimal("0.00"), Decimal("0.10"), Decimal("15.00")),
    "EPO": (Decimal("750.00"), Decimal("0.25"), Decimal("30.00")),
    "POS": (Decimal("1000.00"), Decimal("0.30"), Decimal("40.00")),
}


def adjudicate():
    """Port of the CLAIMCALC adjudication loop with COBOL truncation."""
    deduct_met = Decimal("0.00")
    results = []
    for clm_id, plan, ctype, billed in CLAIMS:
        if plan not in PLANS:
            results.append(dict(id=clm_id, status="DENIED",
                                billed=billed, allowed=CENT * 0,
                                deduct=CENT * 0, coins=CENT * 0,
                                plan_paid=CENT * 0, member=billed))
            continue
        deduct_limit, coins_pct, copay = PLANS[plan]
        # 2300-CALC-ALLOWED: 80% of billed, truncated (no ROUNDED).
        allowed = (billed * Decimal("0.80")).quantize(CENT, ROUND_DOWN)
        # 2400-APPLY-DEDUCTIBLE
        remain = max(deduct_limit - deduct_met, Decimal("0.00"))
        deduct_applied = min(allowed, remain)
        deduct_met += deduct_applied
        post = allowed - deduct_applied
        # 2500-APPLY-COST-SHARE
        if ctype == "RX":
            coins = Decimal("0.00")
            if post < copay:
                plan_paid = Decimal("0.00")
            else:
                plan_paid = post - copay
        else:
            coins = (post * coins_pct).quantize(CENT, ROUND_DOWN)
            plan_paid = post - coins
        member = billed - plan_paid
        results.append(dict(id=clm_id, status="ADJUDICATED", billed=billed,
                            allowed=allowed, deduct=deduct_applied,
                            coins=coins, plan_paid=plan_paid, member=member))
    return results, deduct_met


def _golden_amounts():
    """Parse the labeled money lines out of expected_output.txt."""
    amounts: list[tuple[str, Decimal]] = []
    for line in GOLDEN.read_text().splitlines():
        line = line.rstrip()
        if ":" in line and any(ch.isdigit() for ch in line.split(":")[-1]):
            label, _, val = line.rpartition(":")
            val = val.strip().rstrip("-").replace(",", "")
            try:
                amounts.append((label.strip(), Decimal(val)))
            except ArithmeticError:
                pass
    return amounts


EXPECTED_CLAIM2 = dict(allowed=Decimal("987.64"), coins=Decimal("197.52"),
                       plan_paid=Decimal("790.12"), member=Decimal("444.44"))


def test_claim2_truncation_chain_matches_golden():
    results, _ = adjudicate()
    c2 = results[1]
    for key, want in EXPECTED_CLAIM2.items():
        assert c2[key] == want, key


def test_denied_claim_member_owes_billed():
    results, _ = adjudicate()
    c4 = results[3]
    assert c4["status"] == "DENIED"
    assert c4["plan_paid"] == Decimal("0.00")
    assert c4["member"] == Decimal("500.00")


def test_pharmacy_flat_copay_not_coinsurance():
    results, _ = adjudicate()
    c5 = results[4]
    assert c5["coins"] == Decimal("0.00")
    # 75.99 * .80 = 60.792 -> 60.79 allowed; minus 25.00 copay = 35.79
    assert c5["allowed"] == Decimal("60.79")
    assert c5["plan_paid"] == Decimal("35.79")
    assert c5["member"] == Decimal("40.20")


def test_deductible_applies_once_across_claims():
    results, deduct_met = adjudicate()
    assert results[0]["deduct"] == Decimal("500.00")   # first claim eats it
    assert results[1]["deduct"] == Decimal("0.00")     # already met
    assert deduct_met == Decimal("500.00")


def test_totals_match_golden_master_exactly():
    results, deduct_met = adjudicate()
    tot_billed = sum(r["billed"] for r in results)
    tot_plan = sum(r["plan_paid"] for r in results)
    tot_member = sum(r["member"] for r in results)
    assert tot_billed == Decimal("6610.55")
    assert tot_plan == Decimal("3497.91")
    assert tot_member == Decimal("3112.64")
    # Invariant: every billed dollar is either plan-paid or member-owed.
    assert tot_plan + tot_member == tot_billed


@pytest.mark.parametrize("label,value", _golden_amounts())
def test_every_golden_number_reproduced(label, value):
    """Each money line in the golden file appears in our recomputation."""
    results, deduct_met = adjudicate()
    universe = {deduct_met,
                sum(r["billed"] for r in results),
                sum(r["plan_paid"] for r in results),
                sum(r["member"] for r in results)}
    for r in results:
        universe |= {r["billed"], r["allowed"], r["deduct"], r["coins"],
                     r["plan_paid"], r["member"]}
    assert value in universe, f"{label}: {value} not derivable from the rules"
