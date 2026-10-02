"""Single-agent demo (AC #9): the second predicted TIE.

With one agent and full state, the gate changes no outcome and makes 0
rejections (Cor 4.2: a component is needed only where its map can lose
information). The tool tells you when you don't need it.
"""
from __future__ import annotations

from ..context import ContextAssembler
from ..gate import Accept, CommitGate
from ..monitor import EffectMonitor
from ..proposal import Proposal
from ..store import InMemoryStore
from ..topology import Topology
from ._common import BANNER, header, table, to_json

STEPS = [("counter", 1), ("counter", 2), ("flag", True), ("counter", 3), ("flag", False)]


def run_arm(gated: bool) -> dict:
    s = InMemoryStore({"counter": 0, "flag": False})
    topo = Topology()
    topo.register("solo", reads={"counter", "flag"}, writes={"counter", "flag"})
    monitor = EffectMonitor(s) if gated else None
    gate = CommitGate(s, topology=topo if gated else None, monitor=monitor)
    rejections = 0
    repairs = 0
    for key, value in STEPS:
        ctx = ContextAssembler(s).for_agent("solo", "solo")
        ctx.show(key)  # full state is always fresh: no other writer exists
        out = gate.commit(Proposal("solo", "solo", {key: value},
                                   ctx.read_set if gated else {}))
        if not isinstance(out, Accept):
            rejections += 1
    notices = len(monitor.check()) if monitor else 0
    return {"arm": "gated" if gated else "ungated",
            "final_counter": s.get("counter").value,
            "final_flag": s.get("flag").value,
            "rejections": rejections, "repairs": repairs, "notices": notices}


def run_demo() -> dict:
    ungated = run_arm(gated=False)
    gated = run_arm(gated=True)
    tie = (ungated["final_counter"] == gated["final_counter"]
           and ungated["final_flag"] == gated["final_flag"]
           and gated["rejections"] == 0 and gated["notices"] == 0)
    return {"banner": BANNER, "arms": [ungated, gated], "tie": tie}


def render_terminal(result: dict) -> str:
    lines = header("single-agent — the gate when you don't need it")
    rows = [{"arm": a["arm"], "final counter": a["final_counter"],
             "final flag": a["final_flag"], "rejections": a["rejections"],
             "notices": a["notices"]} for a in result["arms"]]
    lines.extend(table(rows, ["arm", "final counter", "final flag",
                              "rejections", "notices"]))
    lines.append("")
    if result["tie"]:
        lines.append("Predicted TIE: with one agent and full state the gate changes "
                     "no outcome and makes 0 rejections (Cor 4.2: needed only where "
                     "its map can lose information). It tells you when you don't need it.")
    return "\n".join(lines)


def main(fmt: str = "terminal") -> tuple[str, int]:
    result = run_demo()
    if fmt == "json":
        return to_json(result), 0
    return render_terminal(result), 0
