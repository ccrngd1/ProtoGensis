"""Provider-neutral gated tool-use loop (AC #10).

Declared write tools become Proposals through the gate; context comes from
ContextAssembler. Gate outcomes go back to the model as tool results: Repair
carries the fresh values, Reject carries the reason and headroom. MockModel
is scripted, deterministic, and offline; all tests and demos use it.
BedrockConverseCodec translates to/from the Converse message shapes and is
tested against recorded fixtures. Live Bedrock is opt-in (--live bedrock)
and imports boto3 lazily inside the function; tests never need it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..context import ContextAssembler
from ..gate import Accept, CommitGate, Reject, Repair
from ..monitor import EffectMonitor
from ..proposal import Proposal


@dataclass
class ToolCall:
    tool_use_id: str
    name: str
    input: dict


@dataclass
class ToolResult:
    tool_use_id: str
    content: dict
    status: str = "success"  # "error" on Reject or Repair


@dataclass
class ModelTurn:
    tool_calls: list[ToolCall] = field(default_factory=list)
    text: str = ""
    stop: bool = False


class MockModel:
    """Scripted model: a list of callables (context_text, tool_results) -> ModelTurn."""

    def __init__(self, script: list[Callable[[str, list[ToolResult]], ModelTurn]]):
        self._script = list(script)
        self._i = 0

    def __call__(self, context_text: str, tool_results: list[ToolResult]) -> ModelTurn:
        if self._i >= len(self._script):
            return ModelTurn(stop=True)
        turn = self._script[self._i](context_text, tool_results)
        self._i += 1
        return turn


@dataclass
class WriteToolSpec:
    """Declares how a write tool's input maps onto a Proposal."""
    writes_key: str | None = None          # input field "key" -> writes {key: value}
    draws: dict[str, str] | None = None    # resource -> input field holding amount
    postconditions_from_writes: bool = False


class GatedToolLoop:
    def __init__(self, model, gate: CommitGate, assembler: ContextAssembler,
                 tools: dict[str, Callable[[dict], Any]],
                 write_tools: dict[str, WriteToolSpec],
                 monitor: EffectMonitor | None = None,
                 agent: str = "agent", role: str = "agent",
                 show_keys: list[str] | None = None, max_turns: int = 10):
        self.model = model
        self.gate = gate
        self.assembler = assembler
        self.tools = tools
        self.write_tools = write_tools
        self.monitor = monitor
        self.agent = agent
        self.role = role
        self.show_keys = list(show_keys or [])
        self.max_turns = max_turns
        self.transcript: list[dict] = []

    def _proposal_from_call(self, call: ToolCall, read_set: dict[str, int]) -> Proposal:
        spec = self.write_tools[call.name]
        writes: dict[str, Any] = {}
        if spec.writes_key is not None:
            writes = {call.input[spec.writes_key]: call.input.get("value")}
        draws: dict[str, int] = {}
        if spec.draws:
            draws = {resource: int(call.input.get(fld, 0))
                     for resource, fld in spec.draws.items()}
        postconditions = dict(writes) if spec.postconditions_from_writes else {}
        return Proposal(agent=self.agent, role=self.role, writes=writes,
                        read_set=read_set, draws=draws,
                        postconditions=postconditions,
                        premises=call.input.get("premises"))

    def _encode_outcome(self, call: ToolCall, outcome) -> ToolResult:
        if isinstance(outcome, Accept):
            return ToolResult(call.tool_use_id,
                              {"result": "committed", "commit_id": outcome.commit_id})
        if isinstance(outcome, Repair):
            return ToolResult(call.tool_use_id,
                              {"result": "repair", "stale_keys": outcome.stale_keys,
                               "fresh": {k: {"value": v, "version": ver}
                                         for k, (v, ver) in outcome.fresh.items()}},
                              status="error")
        assert isinstance(outcome, Reject)
        content = {"result": "reject", "reason": outcome.reason, "detail": outcome.detail}
        if outcome.headroom is not None:
            content["headroom"] = outcome.headroom
        return ToolResult(call.tool_use_id, content, status="error")

    def run(self) -> list[dict]:
        tool_results: list[ToolResult] = []
        for _ in range(self.max_turns):
            ctx = self.assembler.for_agent(self.agent, self.role)
            if self.monitor is not None:
                self.monitor.check()  # turn boundary
                for notice in self.monitor.pending_for(self.agent):
                    ctx.note(notice.render())
            for key in self.show_keys:
                ctx.show(key)
            text = ctx.render()
            turn = self.model(text, tool_results)
            self.transcript.append({"context": text,
                                    "tool_calls": [c.name for c in turn.tool_calls]})
            if turn.stop and not turn.tool_calls:
                break
            tool_results = []
            for call in turn.tool_calls:
                if call.name in self.write_tools:
                    proposal = self._proposal_from_call(call, dict(ctx.read_set))
                    outcome = self.gate.commit(proposal)
                    tool_results.append(self._encode_outcome(call, outcome))
                else:
                    value = self.tools[call.name](call.input)
                    tool_results.append(ToolResult(call.tool_use_id, {"result": value}))
        return self.transcript


class BedrockConverseCodec:
    """Translate between internal messages and Bedrock Converse shapes
    (toolUse / toolResult blocks). Shape per the documented Converse API."""

    @staticmethod
    def tool_config(tools: dict[str, dict]) -> dict:
        return {"tools": [
            {"toolSpec": {"name": name,
                          "description": spec.get("description", name),
                          "inputSchema": {"json": spec.get("schema", {"type": "object"})}}}
            for name, spec in sorted(tools.items())]}

    @staticmethod
    def parse_tool_uses(message: dict) -> list[ToolCall]:
        calls = []
        for block in message.get("content", []):
            if "toolUse" in block:
                tu = block["toolUse"]
                calls.append(ToolCall(tool_use_id=tu["toolUseId"], name=tu["name"],
                                      input=tu.get("input", {})))
        return calls

    @staticmethod
    def encode_tool_results(results: list[ToolResult]) -> dict:
        return {"role": "user", "content": [
            {"toolResult": {"toolUseId": r.tool_use_id,
                            "content": [{"json": r.content}],
                            "status": r.status}}
            for r in results]}


def run_live_bedrock(model_id: str, messages: list[dict], tool_config: dict,
                     region: str | None = None) -> dict:
    """Opt-in live mode (--live bedrock). Requires the [bedrock] extra and
    credentials. Never used by tests."""
    import boto3  # lazy: only on live runs
    client = boto3.client("bedrock-runtime", region_name=region)
    return client.converse(modelId=model_id, messages=messages, toolConfig=tool_config)
