"""Spike parity (requirements "Tests" section): the three feasibility-spike
scenarios ported against the real package give the spike's results."""
from coherencegate.context import ContextAssembler
from coherencegate.gate import Accept, CommitGate, Reject, Repair
from coherencegate.monitor import EffectMonitor
from coherencegate.owners import Ledger, Unit
from coherencegate.proposal import Proposal

RUN = Unit("tool_call", "run")


def test_spike_budget_gate_holds_at_limit(store_factory):
    """Scripted 3-role team wants 36 calls; gate keeps used <= 20 and records
    refusals (spike: gate (19, 7))."""
    s = store_factory()
    gate = CommitGate(s, invariants=[Ledger("budget", 20, RUN)])
    plans = {"planner": [2] * 4, "executor": [3] * 6, "verifier": [2] * 5}  # 8+18+10 = 36
    refusals = 0
    for step in range(6):
        for role, spends in plans.items():
            if step < len(spends):
                out = gate.commit(Proposal(role, role, draws={"budget": spends[step]}))
                if isinstance(out, Reject):
                    refusals += 1
    used = s.draw_total("budget")
    assert used <= 20
    assert used == 19 and refusals == 7  # exact spike parity (deterministic order)


def test_spike_budget_no_gate_overspends(store_factory):
    s = store_factory()
    gate = CommitGate(s)  # no invariants
    plans = {"planner": [2] * 4, "executor": [3] * 6, "verifier": [2] * 5}
    for step in range(6):
        for role, spends in plans.items():
            if step < len(spends):
                gate.commit(Proposal(role, role, draws={"budget": spends[step]}))
    assert s.draw_total("budget") == 36


def test_spike_stale_quote_ends_at_140(store_factory):
    s = store_factory({"price": 100, "order": None})
    gate = CommitGate(s)
    ctx = ContextAssembler(s).for_agent("cost", "cost")
    price = ctx.show("price")
    s.out_of_band("price", 140)
    out = gate.commit(Proposal("cost", "cost",
                               {"order": {"qty": 1, "unit_price": price}}, ctx.read_set))
    assert isinstance(out, Repair)
    ctx = ContextAssembler(s).for_agent("cost", "cost")
    price = ctx.show("price")
    out = gate.commit(Proposal("cost", "cost",
                               {"order": {"qty": 1, "unit_price": price}}, ctx.read_set))
    assert isinstance(out, Accept)
    assert s.get("order").value["unit_price"] == 140


def test_spike_stale_quote_no_check_commits_100(store_factory):
    s = store_factory({"price": 100, "order": None})
    gate = CommitGate(s)
    ctx = ContextAssembler(s).for_agent("cost", "cost")
    price = ctx.show("price")
    s.out_of_band("price", 140)
    # no read-set validation: proposal omits the read set entirely
    out = gate.commit(Proposal("cost", "cost",
                               {"order": {"qty": 1, "unit_price": price}}, read_set={}))
    assert isinstance(out, Accept)
    assert s.get("order").value["unit_price"] == 100


def test_spike_revert_monitor_restores_with_one_notice(store_factory):
    s = store_factory({"roaming": False})
    monitor = EffectMonitor(s)
    gate = CommitGate(s, monitor=monitor)
    ctx = ContextAssembler(s).for_agent("assistant", "support")
    ctx.show("roaming")
    gate.commit(Proposal("assistant", "support", {"roaming": True}, ctx.read_set,
                         postconditions={"roaming": True}))
    s.out_of_band("roaming", False)  # silently undone
    notices = monitor.check()
    assert len(monitor.notices) == 1
    # the agent acts on the notice
    ctx = ContextAssembler(s).for_agent("assistant", "support")
    ctx.show("roaming")
    out = gate.commit(Proposal("assistant", "support", {"roaming": True}, ctx.read_set,
                               postconditions={"roaming": True}))
    assert isinstance(out, Accept)
    assert s.get("roaming").value is True
    assert len(monitor.notices) == 1  # still exactly one notice


def test_spike_revert_no_monitor_stays_false(store_factory):
    s = store_factory({"roaming": False})
    gate = CommitGate(s)  # no monitor
    gate.commit(Proposal("assistant", "support", {"roaming": True}, {},
                         postconditions={"roaming": True}))
    s.out_of_band("roaming", False)
    assert s.get("roaming").value is False  # nothing notices; stays reverted
