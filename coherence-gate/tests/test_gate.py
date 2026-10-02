"""Commit gate tests (AC #3): cross-key stale -> Repair (with the per-key CAS
contrast), stale_policy=reject, authority reject, outcome order."""
import pytest

from coherencegate.context import ContextAssembler
from coherencegate.gate import Accept, CommitGate, Reject, Repair
from coherencegate.proposal import Proposal
from coherencegate.topology import Topology


def make_topology():
    topo = Topology()
    topo.register("cost", reads={"price", "order"}, writes={"order"})
    return topo


def test_cross_key_stale_gets_repair(store_factory):
    """Proposal read price@v1, writes only order; price moved to v2 -> Repair."""
    s = store_factory({"price": 100, "order": None})
    gate = CommitGate(s, topology=make_topology())
    ctx = ContextAssembler(s).for_agent("a1", "cost")
    price = ctx.show("price")
    s.out_of_band("price", 140)  # price -> v2 between quote and order
    out = gate.commit(Proposal("a1", "cost", writes={"order": {"qty": 1, "unit_price": price}},
                               read_set=ctx.read_set))
    assert isinstance(out, Repair)
    assert out.stale_keys == ["price"]
    assert out.fresh["price"] == (140, 2)


def test_per_key_cas_on_write_key_alone_accepts(store_factory):
    """Contrast: validating only the written key's version misses the stale read."""
    s = store_factory({"price": 100, "order": None})
    gate = CommitGate(s, topology=make_topology())
    ctx = ContextAssembler(s).for_agent("a1", "cost")
    price = ctx.show("price")
    order_version = s.get("order").version
    s.out_of_band("price", 140)
    # per-key CAS: read set covers only the write key, so the gate accepts
    out = gate.commit(Proposal("a1", "cost", writes={"order": {"unit_price": price}},
                               read_set={"order": order_version}))
    assert isinstance(out, Accept)
    assert s.get("order").value == {"unit_price": 100}  # the stale quote got committed


def test_repair_then_requote_commits_fresh(store_factory):
    s = store_factory({"price": 100, "order": None})
    gate = CommitGate(s, topology=make_topology())
    ctx = ContextAssembler(s).for_agent("a1", "cost")
    price = ctx.show("price")
    s.out_of_band("price", 140)
    out = gate.commit(Proposal("a1", "cost", {"order": {"unit_price": price}}, ctx.read_set))
    assert isinstance(out, Repair)
    ctx2 = ContextAssembler(s).for_agent("a1", "cost")
    price2 = ctx2.show("price")
    out2 = gate.commit(Proposal("a1", "cost", {"order": {"unit_price": price2}}, ctx2.read_set))
    assert isinstance(out2, Accept)
    assert s.get("order").value == {"unit_price": 140}


def test_stale_policy_reject(store_factory):
    s = store_factory({"price": 100})
    topo = Topology()
    topo.register("cost", writes={"order"})
    gate = CommitGate(s, topology=topo, stale_policy="reject")
    ctx = ContextAssembler(s).for_agent("a1", "cost")
    ctx.show("price")
    s.out_of_band("price", 140)
    out = gate.commit(Proposal("a1", "cost", {"order": 1}, ctx.read_set))
    assert isinstance(out, Reject)
    assert out.reason == "stale"


def test_authority_reject_for_unregistered_write(store_factory):
    s = store_factory({"price": 100})
    gate = CommitGate(s, topology=make_topology())
    out = gate.commit(Proposal("a1", "cost", writes={"price": 999}, read_set={}))
    assert isinstance(out, Reject)
    assert out.reason == "authority"


def test_authority_checked_before_stale(store_factory):
    """Outcome order: a proposal that is both unauthorized and stale gets
    Reject(authority), not Repair."""
    s = store_factory({"price": 100})
    gate = CommitGate(s, topology=make_topology())
    ctx = ContextAssembler(s).for_agent("a1", "cost")
    ctx.show("price")
    s.out_of_band("price", 140)  # read set now stale
    out = gate.commit(Proposal("a1", "cost", writes={"price": 1}, read_set=ctx.read_set))
    assert isinstance(out, Reject)
    assert out.reason == "authority"


def test_fresh_read_set_accepts(store_factory):
    s = store_factory({"price": 100, "order": None})
    gate = CommitGate(s, topology=make_topology())
    ctx = ContextAssembler(s).for_agent("a1", "cost")
    price = ctx.show("price")
    out = gate.commit(Proposal("a1", "cost", {"order": {"unit_price": price}}, ctx.read_set))
    assert isinstance(out, Accept)


def test_invalid_configs_raise():
    from coherencegate.store import InMemoryStore
    with pytest.raises(ValueError):
        CommitGate(InMemoryStore(), stale_policy="bogus")
    with pytest.raises(ValueError):
        CommitGate(InMemoryStore(), mode="bogus")
