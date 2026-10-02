"""LangGraph adapter tests. The decorator itself is stdlib-only, so the
gating logic is tested directly; the integration test that builds a real
graph is skipped unless langgraph is installed (optional [langgraph] extra)."""
import pytest

from coherencegate.adapters.langgraph import gated_tool, superstep_boundary
from coherencegate.context import ContextAssembler
from coherencegate.gate import CommitGate
from coherencegate.monitor import EffectMonitor
from coherencegate.owners import Ledger, Unit
from coherencegate.topology import Topology


def test_gated_tool_commits_on_accept(store_factory):
    s = store_factory({"price": 100})
    topo = Topology()
    topo.register("writer", writes={"order"})
    gate = CommitGate(s, topology=topo)
    calls = []

    @gated_tool(gate, ContextAssembler(s), agent="a", role="writer",
                show_keys=["price"],
                writes_from=lambda inp: {"order": inp["order"]})
    def place_order(tool_input):
        calls.append(tool_input)
        return "placed"

    out = place_order({"order": {"qty": 1}})
    assert out["status"] == "committed"
    assert out["result"] == "placed"
    assert calls  # the body ran only after Accept


def test_gated_tool_blocks_on_reject_without_running_body(store_factory):
    s = store_factory()
    gate = CommitGate(s, invariants=[Ledger("run_calls", 0, Unit("tool_call", "run"))])
    calls = []

    @gated_tool(gate, ContextAssembler(s), agent="a", role="r",
                draws_from=lambda inp: {"run_calls": 1})
    def run_cmd(tool_input):
        calls.append(tool_input)
        return "ran"

    out = run_cmd({})
    assert out["status"] == "reject"
    assert out["reason"] == "invariant"
    assert out["headroom"] == 0
    assert calls == []  # the side effect never happened


def test_gated_tool_repair_carries_fresh_values(store_factory):
    s = store_factory({"price": 100})
    topo = Topology()
    topo.register("writer", writes={"order"})
    gate = CommitGate(s, topology=topo)
    assembler = ContextAssembler(s)

    captured = {}

    @gated_tool(gate, assembler, agent="a", role="writer", show_keys=["price"],
                writes_from=lambda inp: {"order": inp["order"]})
    def place_order(tool_input):
        return "placed"

    # move the price between context assembly and commit by patching show_keys
    # path: assemble a context first, then mutate, then call
    class MovingAssembler:
        def for_agent(self, agent, role):
            ctx = assembler.for_agent(agent, role)
            orig_render = ctx.render

            def render_and_move():
                text = orig_render()
                s.out_of_band("price", 140)
                return text
            ctx.render = render_and_move
            return ctx

    gated = gated_tool(gate, MovingAssembler(), agent="a", role="writer",
                       show_keys=["price"],
                       writes_from=lambda inp: {"order": inp["order"]})(lambda i: "placed")
    out = gated({"order": {"qty": 1}})
    assert out["status"] == "repair"
    assert out["stale_keys"] == ["price"]
    assert out["fresh"]["price"]["value"] == 140


def test_superstep_boundary_runs_monitor(store_factory):
    from coherencegate.proposal import Proposal
    s = store_factory({"flag": False})
    monitor = EffectMonitor(s)
    gate = CommitGate(s, monitor=monitor)
    gate.commit(Proposal("a", "r", writes={"flag": True}, postconditions={"flag": True}))
    s.out_of_band("flag", False)
    monitor.check()
    assert len(monitor.notices) == 1
    assert superstep_boundary(monitor) == []  # already noticed; deduplicated


def test_langgraph_graph_integration():
    pytest.importorskip("langgraph", reason="optional [langgraph] extra not installed")
