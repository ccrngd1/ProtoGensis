"""Warmup demo (should-ship): the classical lost update, caught by version
compare-and-swap. This is Prop 4.1 (Kung & Robinson 1981 OCC).

`agent-coherence` already prevents this. Shown for completeness: it is the
warm-up, not the headline. The headline failures (shared-budget overspend,
aliasing) are the ones version checks alone do not catch.
"""
from __future__ import annotations

from ..context import ContextAssembler
from ..gate import Accept, CommitGate, Repair
from ..proposal import Proposal
from ..store import InMemoryStore
from ._common import BANNER, header, to_json


def run_arm(gated: bool) -> dict:
    s = InMemoryStore({"feature_flag": "off"})
    gate = CommitGate(s)
    # Agent A reads the flag...
    ctx_a = ContextAssembler(s).for_agent("agent_a", "writer")
    ctx_a.show("feature_flag")
    # ...Agent B changes it before A commits.
    s.out_of_band("feature_flag", "on")
    out = gate.commit(Proposal("agent_a", "writer", {"feature_flag": "a_wins"},
                               ctx_a.read_set if gated else {}))
    lost_update = isinstance(out, Accept)  # A clobbered B without seeing it
    repaired = isinstance(out, Repair)
    return {"arm": "gated" if gated else "ungated",
            "final": s.get("feature_flag").value,
            "lost_update": lost_update, "repaired": repaired}


def run_demo() -> dict:
    return {"banner": BANNER, "arms": [run_arm(False), run_arm(True)],
            "note": "agent-coherence already prevents this. Shown for completeness."}


def render_terminal(result: dict) -> str:
    lines = header("warmup — lost update via version compare-and-swap (Prop 4.1, classical OCC)")
    for a in result["arms"]:
        if a["lost_update"]:
            lines.append(f"  {a['arm']:8s}: Agent A clobbered Agent B's change "
                         f"(final = {a['final']!r}) — the lost update.")
        else:
            lines.append(f"  {a['arm']:8s}: stale read caught at commit; Repair returned "
                         f"with the fresh value (final = {a['final']!r}).")
    lines.append("")
    lines.append("`agent-coherence` already prevents this. Shown for completeness.")
    lines.append("Credit: optimistic concurrency control, Kung & Robinson 1981.")
    return "\n".join(lines)


def main(fmt: str = "terminal") -> tuple[str, int]:
    result = run_demo()
    if fmt == "json":
        return to_json(result), 0
    return render_terminal(result), 0
