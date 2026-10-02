"""Telecom demo (AC #9): toy price/order/roaming/authority keys, no tau^2
dependency. Arms: unguarded, conventional (current-state preconditions at
call time), coherence (read-set validation + effect monitor). Tasks:
S (stale quote), P (silent revert), A (authority change: a predicted TIE),
plus controls with 0 false rejections in every arm.
"""
from __future__ import annotations

from ..context import ContextAssembler
from ..gate import Accept, CommitGate, Reject, Repair
from ..monitor import EffectMonitor
from ..proposal import Proposal
from ..store import InMemoryStore
from ..topology import Topology
from ._common import BANNER, header, paper_block, table, to_json


def _topology() -> Topology:
    topo = Topology()
    topo.register("support", reads={"price", "order", "roaming", "line_status"},
                  writes={"order", "roaming"})
    return topo


def _gate_for(arm: str, store, monitor=None) -> CommitGate:
    if arm == "coherence":
        return CommitGate(store, topology=_topology(), monitor=monitor)
    if arm == "conventional":
        # current-state policy checks include the role write set, but no
        # read-set validation (empty read sets are passed below)
        return CommitGate(store, topology=_topology(), monitor=None)
    return CommitGate(store, topology=None, monitor=None)  # unguarded


def task_stale_quote(arm: str) -> dict:
    """S: price moves between quote and order. conventional checks the
    CURRENT state at call time (price exists, line active) and still commits
    the stale number; coherence repairs -> re-quotes -> commits the current
    price."""
    s = InMemoryStore({"price": 100, "order": None, "line_status": "active"})
    gate = _gate_for(arm, s)
    ctx = ContextAssembler(s).for_agent("assistant", "support")
    price = ctx.show("price")
    ctx.show("line_status")
    s.out_of_band("price", 140)  # price moves before the order call
    # conventional precondition at call time: line active, price present
    precondition_ok = s.get("line_status").value == "active" and s.get("price").value is not None
    read_set = ctx.read_set if arm == "coherence" else {}
    out = gate.commit(Proposal("assistant", "support",
                               {"order": {"qty": 1, "unit_price": price}}, read_set))
    repaired = False
    if isinstance(out, Repair):
        repaired = True
        ctx2 = ContextAssembler(s).for_agent("assistant", "support")
        price2 = ctx2.show("price")
        out = gate.commit(Proposal("assistant", "support",
                                   {"order": {"qty": 1, "unit_price": price2}}, ctx2.read_set))
    final = s.get("order").value["unit_price"]
    return {"task": "S", "arm": arm, "final_unit_price": final,
            "committed_stale": final == 100, "repaired": repaired,
            "conventional_precondition_passed": precondition_ok,
            "success": final == 140}


def task_silent_revert(arm: str) -> dict:
    """P: a committed roaming enable is silently reverted by the environment.
    Only the coherence arm's effect monitor notices; the agent re-applies."""
    s = InMemoryStore({"roaming": False})
    monitor = EffectMonitor(s) if arm == "coherence" else None
    gate = _gate_for(arm, s, monitor=monitor)
    ctx = ContextAssembler(s).for_agent("assistant", "support")
    ctx.show("roaming")
    gate.commit(Proposal("assistant", "support", {"roaming": True},
                         ctx.read_set if arm == "coherence" else {},
                         postconditions={"roaming": True}))
    s.out_of_band("roaming", False)  # silent revert
    notices = 0
    if monitor is not None:
        monitor.check()  # turn boundary
        pending = monitor.pending_for("assistant")
        notices = len(pending)
        if pending:  # one notice is enough: the agent re-applies
            ctx2 = ContextAssembler(s).for_agent("assistant", "support")
            ctx2.show("roaming")
            gate.commit(Proposal("assistant", "support", {"roaming": True},
                                 ctx2.read_set, postconditions={"roaming": True}))
    holds = s.get("roaming").value is True
    return {"task": "P", "arm": arm, "postcondition_holds": holds,
            "notices": notices, "success": holds}


def task_authority_change(arm: str) -> dict:
    """A: the agent tries to write a key outside its write set. Conventional
    policy checks catch this too -> predicted TIE between conventional and
    coherence."""
    s = InMemoryStore({"account_owner": "alice"})
    gate = _gate_for(arm, s)
    if arm == "unguarded":
        out = gate.commit(Proposal("assistant", "unregistered_role",
                                   {"account_owner": "mallory"}, {}))
        blocked = isinstance(out, Reject)
    else:
        # both conventional and coherence enforce the role write set
        out = gate.commit(Proposal("assistant", "support",
                                   {"account_owner": "mallory"}, {}))
        blocked = isinstance(out, Reject) and out.reason == "authority"
    return {"task": "A", "arm": arm, "blocked": blocked,
            "success": blocked if arm != "unguarded" else not blocked}


def task_control(arm: str) -> dict:
    """Control: a plain fresh-state commit. 0 false rejections in every arm."""
    s = InMemoryStore({"price": 100, "order": None})
    gate = _gate_for(arm, s)
    ctx = ContextAssembler(s).for_agent("assistant", "support")
    price = ctx.show("price")
    out = gate.commit(Proposal("assistant", "support",
                               {"order": {"qty": 1, "unit_price": price}},
                               ctx.read_set if arm == "coherence" else {}))
    return {"task": "control", "arm": arm,
            "false_rejection": not isinstance(out, Accept),
            "success": isinstance(out, Accept)}


def run_demo() -> dict:
    arms = ("unguarded", "conventional", "coherence")
    results = []
    for arm in arms:
        results.append(task_stale_quote(arm))
        results.append(task_silent_revert(arm))
        results.append(task_authority_change(arm))
        results.append(task_control(arm))
    a_tie = (next(r for r in results if r["task"] == "A" and r["arm"] == "conventional")["blocked"]
             == next(r for r in results if r["task"] == "A" and r["arm"] == "coherence")["blocked"]
             is True)
    return {"banner": BANNER, "results": results, "authority_tie": a_tie,
            "false_rejections": sum(1 for r in results
                                    if r["task"] == "control" and r["false_rejection"])}


def render_terminal(result: dict) -> str:
    lines = header("telecom — stale quote, silent revert, authority (tau^2-style)")
    rows = []
    for r in result["results"]:
        detail = ""
        if r["task"] == "S":
            detail = f"final unit_price {r['final_unit_price']}" + \
                     (" (repaired, re-quoted)" if r["repaired"] else
                      " (committed stale)" if r["committed_stale"] else "")
        elif r["task"] == "P":
            detail = f"roaming holds: {r['postcondition_holds']}, notices {r['notices']}"
        elif r["task"] == "A":
            detail = "blocked" if r["blocked"] else "not blocked"
        elif r["task"] == "control":
            detail = "false rejection" if r["false_rejection"] else "accepted"
        rows.append({"task": r["task"], "arm": r["arm"],
                     "ok": "yes" if r["success"] else "NO", "detail": detail})
    lines.extend(table(rows, ["task", "arm", "ok", "detail"]))
    lines.append("")
    if result["authority_tie"]:
        lines.append("Task A is a predicted TIE: conventional = coherence. "
                     "Conventional authority checks already own this state; "
                     "the gate adds nothing here, as predicted.")
    lines.append(f"Controls: {result['false_rejections']} false rejections across all arms.")
    lines.extend(paper_block(
        "arXiv 2610.02036 Study V, tau^2-bench Telecom, gpt-6-sol",
        ["silent reverts: reward 0.00 / 0.07 / 1.00 (15/15) for unguarded / "
         "conventional / coherence",
         "conventional checks committed the stale quote 10/10",
         "predicted tie on policy-precondition cases: conventional = coherence",
         "no false rejections on controls"]))
    return "\n".join(lines)


def main(fmt: str = "terminal") -> tuple[str, int]:
    result = run_demo()
    if fmt == "json":
        return to_json(result), 0
    return render_terminal(result), 0
