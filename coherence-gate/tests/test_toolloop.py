"""Tool-loop adapter tests (AC #10): MockModel loop end to end, Converse
codec round-trips recorded fixtures, live tests skipped without boto3."""
import json
import os
import pathlib

import pytest

from coherencegate.adapters.toolloop import (
    BedrockConverseCodec, GatedToolLoop, MockModel, ModelTurn, ToolCall,
    ToolResult, WriteToolSpec,
)
from coherencegate.context import ContextAssembler
from coherencegate.gate import CommitGate
from coherencegate.monitor import EffectMonitor
from coherencegate.owners import Ledger, Unit
from coherencegate.topology import Topology

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "converse"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text())


def test_mock_loop_stale_repair_then_requote(store_factory):
    """End to end: initial order hits Repair (stale price); the scripted model
    reads the fresh value from the tool result and re-quotes; second commit
    accepts."""
    s = store_factory({"price": 100, "order": None})
    topo = Topology()
    topo.register("cost", writes={"order"})
    gate = CommitGate(s, topology=topo)
    asm = ContextAssembler(s)
    seen = {}

    def turn1(ctx_text, results):
        seen["ctx1"] = ctx_text
        price = json.loads(ctx_text.splitlines()[0].split(" = ", 1)[1])
        s.out_of_band("price", 140)  # price moves after the model saw the quote
        return ModelTurn(tool_calls=[ToolCall("t1", "place_order",
                                              {"key": "order",
                                               "value": {"unit_price": price}})])

    def turn2(ctx_text, results):
        assert results[0].status == "error"
        assert results[0].content["result"] == "repair"
        fresh = results[0].content["fresh"]["price"]["value"]
        return ModelTurn(tool_calls=[ToolCall("t2", "place_order",
                                              {"key": "order",
                                               "value": {"unit_price": fresh}})])

    def turn3(ctx_text, results):
        assert results[0].content["result"] == "committed"
        return ModelTurn(stop=True)

    loop = GatedToolLoop(
        MockModel([turn1, turn2, turn3]), gate, asm,
        tools={}, write_tools={"place_order": WriteToolSpec(writes_key="key")},
        agent="cost", role="cost", show_keys=["price"], max_turns=5)
    loop.run()
    assert s.get("order").value == {"unit_price": 140}
    assert seen["ctx1"].startswith("[price@v1]")


def test_mock_loop_invariant_reject_carries_headroom(store_factory):
    s = store_factory()
    gate = CommitGate(s, invariants=[Ledger("run_calls", 2, Unit("tool_call", "run"))])
    results_seen = []

    def turn1(ctx, results):
        return ModelTurn(tool_calls=[ToolCall("t1", "run", {"n": 3})])

    def turn2(ctx, results):
        results_seen.extend(results)
        return ModelTurn(stop=True)

    loop = GatedToolLoop(
        MockModel([turn1, turn2]), gate, ContextAssembler(s),
        tools={}, write_tools={"run": WriteToolSpec(draws={"run_calls": "n"})},
        max_turns=3)
    loop.run()
    assert results_seen[0].status == "error"
    assert results_seen[0].content["reason"] == "invariant"
    assert results_seen[0].content["headroom"] == 2


def test_mock_loop_monitor_notice_injected_next_turn(store_factory):
    s = store_factory({"roaming": False})
    monitor = EffectMonitor(s)
    topo = Topology()
    topo.register("support", writes={"roaming"})
    gate = CommitGate(s, topology=topo, monitor=monitor)
    contexts = []

    def turn1(ctx, results):
        return ModelTurn(tool_calls=[ToolCall(
            "t1", "set_flag", {"key": "roaming", "value": True})])

    def turn2(ctx, results):
        s.out_of_band("roaming", False)  # silent revert before next turn
        return ModelTurn(tool_calls=[ToolCall("t2", "noop", {})])

    def turn3(ctx, results):
        contexts.append(ctx)
        return ModelTurn(stop=True)

    loop = GatedToolLoop(
        MockModel([turn1, turn2, turn3]), gate, ContextAssembler(s),
        tools={"noop": lambda inp: "ok"},
        write_tools={"set_flag": WriteToolSpec(writes_key="key",
                                               postconditions_from_writes=True)},
        monitor=monitor, agent="agent", role="support", max_turns=5)
    loop.run()
    assert "NOTICE to agent: committed effect roaming=True no longer holds" in contexts[0]


def test_codec_parses_recorded_tool_use_fixture():
    msg = load_fixture("assistant_tool_use.json")
    calls = BedrockConverseCodec.parse_tool_uses(msg)
    assert len(calls) == 1
    assert calls[0].tool_use_id == "tooluse_order_001"
    assert calls[0].name == "place_order"
    assert calls[0].input == {"key": "order", "value": {"qty": 1, "unit_price": 100}}


def test_codec_encodes_repair_as_error_matching_fixture():
    result = ToolResult("tooluse_order_001",
                        {"result": "repair", "stale_keys": ["price"],
                         "fresh": {"price": {"value": 140, "version": 2}}},
                        status="error")
    encoded = BedrockConverseCodec.encode_tool_results([result])
    assert encoded == load_fixture("tool_result_error_repair.json")


def test_codec_encodes_reject_as_error_matching_fixture():
    result = ToolResult("tooluse_spend_002",
                        {"result": "reject", "reason": "invariant",
                         "detail": "ledger run_calls: 19+3>20", "headroom": 1},
                        status="error")
    encoded = BedrockConverseCodec.encode_tool_results([result])
    assert encoded == load_fixture("tool_result_error_reject.json")


def test_codec_encodes_success_matching_fixture():
    result = ToolResult("tooluse_order_001", {"result": "committed", "commit_id": 1})
    encoded = BedrockConverseCodec.encode_tool_results([result])
    assert encoded == load_fixture("tool_result_success.json")


def test_codec_tool_config_shape():
    cfg = BedrockConverseCodec.tool_config(
        {"run": {"description": "run a command",
                 "schema": {"type": "object", "properties": {"n": {"type": "integer"}}}}})
    spec = cfg["tools"][0]["toolSpec"]
    assert spec["name"] == "run"
    assert "json" in spec["inputSchema"]


def test_live_bedrock_skipped_without_extra():
    pytest.importorskip("boto3", reason="requires the [bedrock] extra")
    if not (os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("AWS_PROFILE")):
        pytest.skip("no AWS credentials; live Bedrock is opt-in only")
