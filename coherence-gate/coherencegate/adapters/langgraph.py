"""Optional LangGraph adapter (should-ship; requires the [langgraph] extra).

`gated_tool(gate, assembler, ...)` wraps a tool function used in a ToolNode so
writes go through the gate inside the tool body. Superstep boundaries are
natural commit points: call `superstep_boundary(monitor)` from a graph hook to
run EffectMonitor.check(). langgraph itself is imported only by the caller;
this module stays stdlib-only and works with any callable-wrapping framework.
"""
from __future__ import annotations

import functools
from typing import Any, Callable

from ..context import ContextAssembler
from ..gate import Accept, CommitGate, Reject, Repair
from ..monitor import EffectMonitor
from ..proposal import Proposal


def gated_tool(gate: CommitGate, assembler: ContextAssembler, *,
               agent: str, role: str, show_keys: list[str] | None = None,
               writes_from: Callable[[dict], dict[str, Any]] | None = None,
               draws_from: Callable[[dict], dict[str, int]] | None = None,
               postconditions_from: Callable[[dict], dict] | None = None):
    """Decorator: the wrapped tool's input becomes a Proposal through the gate.

    The wrapped function runs ONLY on Accept, so an invariant refusal or stale
    read stops the side effect inside the tool body, where LangGraph's
    reducers can't merge past it."""
    def decorate(fn: Callable[..., Any]):
        @functools.wraps(fn)
        def wrapper(tool_input: dict) -> dict:
            ctx = assembler.for_agent(agent, role)
            for key in (show_keys or []):
                ctx.show(key)
            ctx.render()
            proposal = Proposal(
                agent=agent, role=role,
                writes=writes_from(tool_input) if writes_from else {},
                read_set=dict(ctx.read_set),
                draws=draws_from(tool_input) if draws_from else {},
                postconditions=postconditions_from(tool_input) if postconditions_from else {})
            outcome = gate.commit(proposal)
            if isinstance(outcome, Accept):
                return {"status": "committed", "commit_id": outcome.commit_id,
                        "result": fn(tool_input)}
            if isinstance(outcome, Repair):
                return {"status": "repair", "stale_keys": outcome.stale_keys,
                        "fresh": {k: {"value": v, "version": ver}
                                  for k, (v, ver) in outcome.fresh.items()}}
            assert isinstance(outcome, Reject)
            out: dict[str, Any] = {"status": "reject", "reason": outcome.reason,
                                   "detail": outcome.detail}
            if outcome.headroom is not None:
                out["headroom"] = outcome.headroom
            return out
        return wrapper
    return decorate


def superstep_boundary(monitor: EffectMonitor) -> list:
    """Run the committed-effect check at a LangGraph superstep boundary."""
    return monitor.check()
