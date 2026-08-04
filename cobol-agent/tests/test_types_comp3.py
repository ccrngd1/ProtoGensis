"""COMP-3 correctness: the deterministic PIC/USAGE -> Java type rules.

These tests pin the moat: PIC S9(N)V9(M) COMP-3 must map to BigDecimal with
scale=M, COBOL no-ROUNDED arithmetic must truncate (RoundingMode.DOWN), and
monetary comparisons must be exact — verified here with decimal.Decimal as
the executable stand-in for BigDecimal semantics.
"""

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

import pytest

from cobalt.schema import walk_items
from cobalt.types import (
    JAVA_ROUNDED,
    JAVA_TRUNCATION,
    is_comp3,
    java_type_for,
    type_table,
)


def _item(picture=None, usage=None, integer_digits=None, fraction_digits=None,
          alpha_length=None, **kw):
    d = {
        "level": 5, "name": "T", "picture": picture, "usage": usage,
        "signed": picture.startswith("S") if picture else False,
        "integer_digits": integer_digits, "fraction_digits": fraction_digits,
        "alpha_length": alpha_length, "occurs": None, "redefines": None,
        "value": None, "condition_names": [], "children": [], "source": "t",
    }
    d.update(kw)
    return d


class TestPicToJavaType:
    @pytest.mark.parametrize("n,m", [(7, 2), (5, 2), (9, 2), (3, 2), (0, 2), (13, 4)])
    def test_s9n_v9m_comp3_is_bigdecimal_scale_m(self, n, m):
        it = _item(picture=f"S9({n})V9({m})", usage="COMP-3",
                   integer_digits=n, fraction_digits=m)
        jt = java_type_for(it)
        assert jt.java_type == "BigDecimal"
        assert jt.scale == m

    def test_integer_comp3_is_bigdecimal_scale_zero_never_float(self):
        it = _item(picture="S9(5)", usage="COMP-3",
                   integer_digits=5, fraction_digits=0)
        jt = java_type_for(it)
        assert jt.java_type == "BigDecimal"
        assert jt.scale == 0

    @pytest.mark.parametrize("usage", ["COMP-3", "COMPUTATIONAL-3", "PACKED-DECIMAL"])
    def test_comp3_usage_spellings(self, usage):
        it = _item(picture="S9(7)V99", usage=usage,
                   integer_digits=7, fraction_digits=2)
        assert is_comp3(it)
        assert java_type_for(it).java_type == "BigDecimal"

    def test_display_with_v_is_bigdecimal(self):
        # Assumed decimal point forces BigDecimal even without COMP-3.
        it = _item(picture="9(7)V99", usage=None,
                   integer_digits=7, fraction_digits=2)
        jt = java_type_for(it)
        assert jt.java_type == "BigDecimal"
        assert jt.scale == 2

    def test_pic_x_is_string(self):
        it = _item(picture="X(10)", alpha_length=10)
        assert java_type_for(it).java_type == "String"

    def test_small_integer_is_int(self):
        it = _item(picture="9(8)", integer_digits=8, fraction_digits=0)
        assert java_type_for(it).java_type == "int"

    def test_boundary_nine_digits_is_int(self):
        it = _item(picture="9(9)", integer_digits=9, fraction_digits=0)
        assert java_type_for(it).java_type == "int"

    def test_ten_digits_is_long(self):
        it = _item(picture="9(10)", integer_digits=10, fraction_digits=0)
        assert java_type_for(it).java_type == "long"

    def test_group_item_maps_to_none(self):
        assert java_type_for(_item(picture=None)) is None

    def test_rounding_mode_constants(self):
        # COBOL default (no ROUNDED) truncates toward zero; ROUNDED is
        # half-away-from-zero. These strings feed prompts and generated code.
        assert JAVA_TRUNCATION == "RoundingMode.DOWN"
        assert JAVA_ROUNDED == "RoundingMode.HALF_UP"


class TestFixtureFieldMappings:
    """Every monetary field in the real sample must decode correctly."""

    def _by_name(self, doc):
        return {i["name"]: i for i in walk_items(doc) if i["name"] != "FILLER"}

    def test_claim_money_fields_are_bigdecimal_scale_2(self, fixture_doc):
        items = self._by_name(fixture_doc)
        for name in ("CLM-BILLED-AMT", "CLM-ALLOWED-AMT", "CLM-COINS-AMT",
                     "CLM-PLAN-PAID-AMT", "CLM-MEMBER-RESP-AMT"):
            it = items[name]
            assert it["usage"] == "COMP-3", name
            jt = java_type_for(it)
            assert (jt.java_type, jt.scale) == ("BigDecimal", 2), name

    def test_deduct_applied_scale_from_s9_5_v99(self, fixture_doc):
        it = self._by_name(fixture_doc)["CLM-DEDUCT-APPLIED"]
        assert it["picture"] == "S9(5)V99"
        assert it["integer_digits"] == 5 and it["fraction_digits"] == 2
        assert java_type_for(it).scale == 2

    def test_coins_pct_sv99_is_scale_2_zero_int_digits(self, fixture_doc):
        # PIC SV99 COMP-3: no integer digits at all, still exact decimal.
        it = self._by_name(fixture_doc)["WS-COINS-PCT"]
        assert it["integer_digits"] == 0 and it["fraction_digits"] == 2
        jt = java_type_for(it)
        assert (jt.java_type, jt.scale) == ("BigDecimal", 2)

    def test_no_comp3_field_ever_maps_to_float(self, fixture_doc):
        for it in walk_items(fixture_doc):
            if is_comp3(it):
                jt = java_type_for(it)
                assert jt.java_type == "BigDecimal", it["name"]

    def test_type_table_flags_redefines_and_occurs(self, fixture_doc):
        rows = {r["name"]: r for r in type_table(fixture_doc)}
        assert rows["BENEFIT-TABLE"]["redefines"] == "BENEFIT-TABLE-INIT"
        assert rows["BENEFIT-ENTRY"]["occurs"] == 4
        assert rows["INPUT-CLAIM"]["occurs"] == 5
        assert "CLM-TYPE-PHARMACY" in rows["CLM-TYPE"]["condition_names"]


class TestTruncationSemantics:
    """COBOL COMPUTE without ROUNDED == RoundingMode.DOWN, checked against
    the numbers in the GnuCOBOL golden master (decimal.Decimal.quantize with
    ROUND_DOWN is semantically identical to BigDecimal.setScale(2, DOWN))."""

    def test_allowed_amount_truncates_not_rounds(self):
        # Golden master claim 2: 1234.56 * 0.80 = 987.648 -> stored 987.64.
        billed = Decimal("1234.56")
        allowed = (billed * Decimal("0.80")).quantize(Decimal("0.01"), ROUND_DOWN)
        assert allowed == Decimal("987.64")
        # HALF_UP would give a DIFFERENT (wrong-for-COBOL) answer:
        rounded = (billed * Decimal("0.80")).quantize(Decimal("0.01"), ROUND_HALF_UP)
        assert rounded == Decimal("987.65")
        assert allowed != rounded

    def test_coinsurance_truncates(self):
        # Golden master claim 2: 987.64 * .20 = 197.528 -> 197.52 (not .53).
        post_deduct = Decimal("987.64")
        coins = (post_deduct * Decimal("0.20")).quantize(Decimal("0.01"), ROUND_DOWN)
        assert coins == Decimal("197.52")
        assert (post_deduct * Decimal("0.20")).quantize(
            Decimal("0.01"), ROUND_HALF_UP) == Decimal("197.53")

    def test_golden_master_claim2_full_chain_exact(self):
        # Reproduce the whole adjudication of claim 2 with exact decimals
        # and compare to the GnuCOBOL-printed values digit-for-digit.
        billed = Decimal("1234.56")
        allowed = (billed * Decimal("0.80")).quantize(Decimal("0.01"), ROUND_DOWN)
        deduct_applied = Decimal("0.00")        # deductible already met
        post = allowed - deduct_applied
        coins = (post * Decimal("0.20")).quantize(Decimal("0.01"), ROUND_DOWN)
        plan_paid = post - coins
        member_resp = billed - plan_paid
        assert allowed == Decimal("987.64")
        assert coins == Decimal("197.52")
        assert plan_paid == Decimal("790.12")
        assert member_resp == Decimal("444.44")

    def test_exact_comparison_not_float_delta(self):
        # The moat rule: monetary equality is exact, never float-delta.
        # binary float cannot represent 987.64, so going through float
        # changes the value — this is why double is banned for COMP-3.
        exact = Decimal("987.64")
        via_float = Decimal(987.64)
        assert via_float != exact
        # Exact decimals are stable under scale-2 truncation (idempotent).
        assert exact.quantize(Decimal("0.01"), ROUND_DOWN) == exact
