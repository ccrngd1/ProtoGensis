"""Topology tests: authority registry, GYO join-tree check (star acyclic,
3-cycle cyclic), Bernstein parallel-safety table."""
from coherencegate.topology import Topology


def test_authority_registry():
    topo = Topology()
    topo.register("executor", reads={"plan"}, writes={"result"})
    assert topo.can_write("executor", "result")
    assert not topo.can_write("executor", "plan")
    assert not topo.can_write("ghost_role", "result")


def test_gyo_star_is_acyclic():
    """Hub-and-spoke: hub holds the shared fields -> join tree exists."""
    topo = Topology()
    topo.register("hub", reads={"a", "b", "c"}, writes={"a", "b", "c"})
    topo.register("spoke1", reads={"a"}, writes={"a"})
    topo.register("spoke2", reads={"b"}, writes={"b"})
    topo.register("spoke3", reads={"c"}, writes={"c"})
    result = topo.gyo_check()
    assert result["acyclic"] is True
    assert "acyclic" in result["message"]


def test_gyo_three_cycle_is_cyclic():
    """Pairwise overlaps forming a 3-cycle: pairwise reconciliation insufficient."""
    topo = Topology()
    topo.register("r1", reads={"a", "b"}, writes=set())
    topo.register("r2", reads={"b", "c"}, writes=set())
    topo.register("r3", reads={"c", "a"}, writes=set())
    result = topo.gyo_check()
    assert result["acyclic"] is False
    assert "pairwise reconciliation insufficient" in result["message"]


def test_bernstein_table():
    topo = Topology()
    topo.register("writer", reads=set(), writes={"x"})
    topo.register("reader", reads={"x"}, writes=set())
    topo.register("loner", reads={"y"}, writes={"z"})
    rows = {tuple(r["pair"]): r for r in topo.bernstein_table()}
    assert rows[("reader", "writer")]["parallel_safe"] is False
    assert rows[("reader", "writer")]["conflict_keys"] == ["x"]
    assert rows[("loner", "reader")]["parallel_safe"] is True
    assert rows[("loner", "writer")]["parallel_safe"] is True
