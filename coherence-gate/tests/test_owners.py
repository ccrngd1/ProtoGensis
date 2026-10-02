"""Invariant owner tests (AC #4): Ledger refuses the 21st, Escrow per-role
refusal and construction validation, same-snapshot concurrent draws both
accepted (no OCC thrash), headroom in the reject."""
import pytest

from coherencegate.context import ContextAssembler
from coherencegate.gate import Accept, CommitGate, Reject
from coherencegate.owners import Escrow, Ledger, Unit
from coherencegate.proposal import Proposal

RUN = Unit("tool_call", "run")


def test_ledger_refuses_draw_past_limit(store_factory):
    s = store_factory()
    gate = CommitGate(s, invariants=[Ledger("run_calls", 20, RUN)])
    for _ in range(20):
        assert isinstance(gate.commit(Proposal("a", "r", draws={"run_calls": 1})), Accept)
    out = gate.commit(Proposal("a", "r", draws={"run_calls": 1}))  # the 21st
    assert isinstance(out, Reject)
    assert out.reason == "invariant"
    assert out.headroom == 0
    assert s.draw_total("run_calls") == 20


def test_ledger_reject_reports_headroom(store_factory):
    s = store_factory()
    gate = CommitGate(s, invariants=[Ledger("run_calls", 20, RUN)])
    gate.commit(Proposal("a", "r", draws={"run_calls": 18}))
    out = gate.commit(Proposal("a", "r", draws={"run_calls": 3}))
    assert isinstance(out, Reject)
    assert out.headroom == 2


def test_escrow_per_role_refusal(store_factory):
    s = store_factory()
    escrow = Escrow("run_calls", {"planner": 2, "executor": 12, "verifier": 6},
                    RUN, global_limit=20)
    gate = CommitGate(s, invariants=[escrow])
    assert isinstance(gate.commit(Proposal("p", "planner", draws={"run_calls": 2})), Accept)
    out = gate.commit(Proposal("p", "planner", draws={"run_calls": 1}))
    assert isinstance(out, Reject)
    assert out.reason == "invariant"
    assert out.headroom == 0
    # another role's quota is untouched
    assert isinstance(gate.commit(Proposal("e", "executor", draws={"run_calls": 12})), Accept)


def test_escrow_construction_validates_quota_sum():
    with pytest.raises(ValueError):
        Escrow("run_calls", {"a": 15, "b": 10}, RUN, global_limit=20)
    Escrow("run_calls", {"a": 10, "b": 10}, RUN, global_limit=20)  # == limit is fine


def test_same_snapshot_in_limit_draws_both_accepted(store_factory):
    """Two proposals that both saw run_calls at the same point and both fit
    under the limit are both accepted: draws are commutative operations
    validated against the invariant, never version-validated."""
    s = store_factory()
    gate = CommitGate(s, invariants=[Ledger("run_calls", 20, RUN)])
    asm = ContextAssembler(s)
    # both contexts built from the same snapshot (headroom display-only)
    ctx_a = asm.for_agent("a", "r1")
    ctx_a.show_owned("run_calls", limit=20)
    ctx_b = asm.for_agent("b", "r2")
    ctx_b.show_owned("run_calls", limit=20)
    pa = Proposal("a", "r1", read_set=ctx_a.read_set, draws={"run_calls": 8})
    pb = Proposal("b", "r2", read_set=ctx_b.read_set, draws={"run_calls": 8})
    assert isinstance(gate.commit(pa), Accept)
    assert isinstance(gate.commit(pb), Accept)  # no stale-counter conflict
    assert s.draw_total("run_calls") == 16


def test_custom_invariant_callable(store_factory):
    from coherencegate.owners import Violation

    class NonNegativeBalance:
        unit = Unit("key", "balance")

        def check(self, store_view, proposal):
            new = proposal.writes.get("balance")
            if new is not None and new < 0:
                return Violation(reason=f"balance {new}<0", headroom=0)
            return None

    s = store_factory({"balance": 5})
    gate = CommitGate(s, invariants=[NonNegativeBalance()])
    out = gate.commit(Proposal("a", "r", writes={"balance": -1}))
    assert isinstance(out, Reject) and out.reason == "invariant"
    assert isinstance(gate.commit(Proposal("a", "r", writes={"balance": 3})), Accept)
