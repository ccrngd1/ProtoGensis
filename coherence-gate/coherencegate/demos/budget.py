"""Budget demo (AC #8, Amendment 1): information is not ownership (Study IV analogue).

Scripted mock roles. The policy, seeds, quotas, and progress metric are
pre-registered in demos/config/budget.json; the demo reads them from there
and reports whatever they produce. The mock policy works in supersteps: each
round, every role that still has demand reads the same round-start snapshot
(Prop 3.3's mechanism), then proposes exactly one seeded batch of 1-3 calls.
In the visible_state arm the snapshot reaches the role only through
ContextAssembler's rendered text (display-only owned count), and the role's
rule is bounded by that view (Cor 2.2).

Pre-registered result, final per Amendment 1: visible_state stayed in budget
(0/5) only because every scripted agent obeyed a conservative stop rule. The
ledger and escrow held with no such rule. That's the paper's "information is
not ownership" point; the paper's LLM teams overspent at 4/5 (paper result,
not ours).

`visible_state_lax` is EXPLORATORY, added after the pre-registered result
(Amendment 1): same seeds, demands, batch RNG, and superstep as
visible_state, but each role spends its one batch per round whenever
x < limit, skipping the x + batch <= limit check. It is reported in its own
block and never mixed into the pre-registered table or summary.
"""
from __future__ import annotations

import importlib.resources
import json
import random
import re

from ..audit.ownership_lint import lint_static
from ..context import ContextAssembler
from ..gate import Accept, CommitGate, Reject
from ..owners import Escrow, Ledger, Unit
from ..runlog import RunLog, StepClock
from ..store import InMemoryStore
from ._common import BANNER, header, paper_block, table, to_json

MAX_ROUNDS = 30
ROLES = ("planner", "executor", "verifier")
PROGRESS_CAVEAT = ("The progress metric ignores the budget, so non-gate arms can score "
                   "high progress by overspending.")
ACCURATE_CLAIM = (
    "Visible state stayed in budget only because every scripted agent obeyed a "
    "conservative stop rule. The ledger and escrow held with no such rule. That's the "
    "paper's 'information is not ownership' point, and their LLM teams overspent at "
    "4/5 (paper result, not ours).")

# Exploratory arm (Amendment 1): NOT pre-registered, NOT in budget.json's arms,
# never mixed into the pre-registered table or summary.
EXPLORATORY_ARM = "visible_state_lax"
EXPLORATORY_LABEL = "exploratory, added after the pre-registered result"
EXPLORATORY_NOTE = (
    "Same seeds, demands, batch RNG, and superstep as visible_state, but each role "
    "spends its one batch per round whenever x < limit, skipping the "
    "x + batch <= limit check.")


def load_config() -> dict:
    ref = importlib.resources.files("coherencegate.demos") / "config" / "budget.json"
    return json.loads(ref.read_text())


def _make_gate(arm: str, store, config: dict, runlog: RunLog) -> CommitGate:
    limit = config["limit"]
    resource = config["resource"]
    unit = Unit(config["graded_unit"]["kind"], config["graded_unit"]["name"])
    if arm == "ledger":
        return CommitGate(store, invariants=[Ledger(resource, limit, unit)], runlog=runlog)
    if arm == "escrow":
        escrow = Escrow(resource, config["escrow_quotas"], unit, global_limit=limit)
        return CommitGate(store, invariants=[escrow], runlog=runlog)
    if arm == "wrong_unit_ledger":
        wrong = Unit(config["wrong_unit"]["kind"], config["wrong_unit"]["name"])
        # the guard owns write_file; run_calls draws sail past it
        return CommitGate(store, invariants=[Ledger(wrong.name, limit, wrong)], runlog=runlog)
    return CommitGate(store, runlog=runlog)  # ordinary / visible_state: no owner


_OWNED_RE = re.compile(r"\(owned\) ([^\s]+) used = (\d+)")


def displayed_count(rendered: str, resource: str) -> int:
    """Parse a resource's displayed owned count out of rendered context text.

    The mock visible_state role gets its view of the budget this way: from
    the text ContextAssembler rendered, not from the store (AC #8)."""
    for m in _OWNED_RE.finditer(rendered):
        if m.group(1) == resource:
            return int(m.group(2))
    raise ValueError(f"no displayed count for {resource!r} in rendered context")


def run_arm(arm: str, seed: int, config: dict, policy: str = "preregistered") -> dict:
    """One (arm, seed) run of the superstep policy.

    Each round, every role that still has demand (and hasn't stopped) reads
    the same round-start snapshot and proposes exactly ONE seeded batch
    against it. All of a round's decisions are made before any of its commits
    land: turns within a round are concurrent, so no decision can see another
    role's same-round spending (Cor 2.2). In visible_state the snapshot
    reaches the role only as display-only text via ContextAssembler, and the
    conservative reading applies: a role whose rule fails stops for good.

    policy="preregistered" is the pre-registered policy (final per
    Amendment 1). policy="lax" is EXPLORATORY, added after the pre-registered
    result: every role sees x through ContextAssembler exactly as
    visible_state does, but spends its one batch per round whenever
    x < limit, skipping the x + batch <= limit check. Seeds, demands, batch
    RNG, and the superstep are unchanged.
    """
    from ..proposal import Proposal

    rng = random.Random(seed)
    ranges = config["policy"]["demand_ranges"]
    lo_b, hi_b = config["policy"]["batch_range"]
    limit = config["limit"]
    resource = config["resource"]
    demands = {role: rng.randint(*ranges[role]) for role in ROLES}

    store = InMemoryStore()
    assembler = ContextAssembler(store)
    runlog = RunLog(clock=StepClock(), run_id=f"budget-{arm}-{seed}", arm=arm, seed=seed)
    gate = _make_gate(arm, store, config, runlog)
    sees_state = arm == "visible_state" or policy == "lax"

    committed = {role: 0 for role in ROLES}
    stopped = {role: False for role in ROLES}  # rule failed, or owner exhausted
    refusals = 0
    reads: list[dict] = []  # decisions against displayed counts
    for _ in range(MAX_ROUNDS):
        active = [r for r in ROLES if committed[r] < demands[r] and not stopped[r]]
        if not active:
            break
        # decision phase: every active role reads the SAME round-start
        # snapshot and decides its one batch; no commit lands until every
        # decision in the round is made.
        decisions: list[tuple[str, int]] = []
        for role in active:
            batch = min(rng.randint(lo_b, hi_b), demands[role] - committed[role])
            if sees_state:
                ctx = assembler.for_agent(role, role)
                ctx.show_owned(resource, limit)
                prompt = ctx.render()
                x = displayed_count(prompt, resource)
                runlog.emit("read", agent=role,
                            displayed_owned={resource: x}, rendered=prompt)
                if policy == "lax":
                    proposed = x < limit  # exploratory: skips the batch check
                else:
                    proposed = x + batch <= limit
                reads.append({"role": role, "displayed": x, "batch": batch,
                              "proposed": proposed, "prompt": prompt})
                if not proposed:
                    # The displayed count never decreases, so under either
                    # rule a role that sees no room never will again.
                    stopped[role] = True
                    continue
            decisions.append((role, batch))
        # commit phase
        for role, batch in decisions:
            out = gate.commit(Proposal(role, role, draws={resource: batch}))
            if isinstance(out, Accept):
                committed[role] += batch
            elif isinstance(out, Reject):
                refusals += 1  # a refusal ends the role's turn for the round
                if out.headroom == 0:
                    stopped[role] = True  # owner is exhausted for this role

    total = store.draw_total(resource)
    partials = [min(committed[r], demands[r]) / demands[r] for r in ROLES]
    result = {
        "arm": arm,
        "seed": seed,
        "demands": demands,
        "total_calls": total,
        "over_budget": total > limit,
        "refusals": refusals,
        "progress": round(sum(partials) / len(partials), 4),
    }
    if sees_state:
        result["reads"] = reads
    return result


def _summarize(arm: str, runs: list[dict]) -> dict:
    calls = sorted(r["total_calls"] for r in runs)
    return {
        "arm": arm,
        "over_budget": sum(1 for r in runs if r["over_budget"]),
        "runs": len(runs),
        "calls_median": calls[len(calls) // 2],
        "calls_range": f"{calls[0]}-{calls[-1]}",
        "refusals": sum(r["refusals"] for r in runs),
        "progress_mean": round(sum(r["progress"] for r in runs) / len(runs), 4),
    }


def run_demo(seeds: list[int] | None = None, arms: list[str] | None = None) -> dict:
    config = load_config()
    seeds = seeds if seeds is not None else config["seeds"]
    arms = arms if arms is not None else config["arms"]
    results = {arm: [run_arm(arm, seed, config) for seed in seeds] for arm in arms}
    summary = [_summarize(arm, results[arm]) for arm in arms]

    lint = None
    if "wrong_unit_ledger" in arms:
        lint_result = lint_static({
            "guard": {"unit": config["wrong_unit"], "limit": config["limit"]},
            "task": {"graded_unit": config["graded_unit"]},
        })
        lint = [f["message"] for f in lint_result.findings]

    # Exploratory arm (Amendment 1): kept out of `summary`/`runs`, reported
    # under its own top-level key with the required label. Run once with the
    # pre-registered seeds; whatever it produces is reported, no tuning.
    exploratory = None
    if "visible_state" in arms:
        lax_runs = [run_arm(EXPLORATORY_ARM, seed, config, policy="lax")
                    for seed in seeds]
        exploratory = {
            "label": EXPLORATORY_LABEL,
            "note": EXPLORATORY_NOTE,
            "summary": [_summarize(EXPLORATORY_ARM, lax_runs)],
            "runs": {EXPLORATORY_ARM: lax_runs},
        }

    return {"banner": BANNER, "config_seeds": seeds, "limit": config["limit"],
            "summary": summary, "runs": results, "lint": lint,
            "exploratory": exploratory}


def _summary_rows(summary: list[dict]) -> list[dict]:
    return [{"arm": s["arm"],
             "over budget (of %d)" % s["runs"]: f"{s['over_budget']}/{s['runs']}",
             "calls (median, range)": f"{s['calls_median']} ({s['calls_range']})",
             "refusals": s["refusals"],
             "progress (mean partial)": f"{s['progress_mean']:.3f}"}
            for s in summary]


def render_terminal(result: dict) -> str:
    lines = header("budget — information is not ownership (Study IV analogue)")
    lines.append(f"Shared limit: {result['limit']} run calls across the team; "
                 f"seeds {result['config_seeds']} (pre-registered).")
    lines.append("")
    rows = _summary_rows(result["summary"])
    lines.extend(table(rows, list(rows[0].keys())))
    lines.append("")
    lines.append(PROGRESS_CAVEAT)
    lines.append("")
    lines.append(ACCURATE_CLAIM)
    if result["lint"]:
        lines.append("")
        lines.extend(f"LINT: {msg}" for msg in result["lint"])
    lines.append("")
    lines.append("Gate arms (ledger, escrow) are 0/N by construction; the informative "
                 "rows are the non-gate arms and progress.")
    if result.get("exploratory"):
        exp = result["exploratory"]
        lines.append("")
        lines.append(f"--- exploratory arm ({exp['label']}) ---")
        lines.append(exp["note"])
        exp_rows = _summary_rows(exp["summary"])
        lines.extend(table(exp_rows, list(exp_rows[0].keys())))
    lines.extend(paper_block(
        "arXiv 2610.02036 Study IV, gpt-6-sol",
        ["ordinary 5/5 over (57-72 calls)",
         "visible_state 4/5 over (median 70 -> 29 calls)",
         "ledger 0/5, stopping at exactly 20 (1-32 surplus attempts rejected, mean 10.4)",
         "quota_escrow 0/5, mean partial 0.960 and 4/5 strict, vs ledger 0.874 and 2/5 strict "
         "(descriptive; confounded attestation gates)"]))
    return "\n".join(lines)


def render_markdown(result: dict) -> str:
    lines = ["# Budget demo", "", BANNER, "",
             "| Arm | Runs over budget | Calls (median, range) | Refusals | Progress (mean partial) |",
             "|---|---|---|---|---|"]
    for s in result["summary"]:
        lines.append(f"| {s['arm']} | {s['over_budget']}/{s['runs']} | "
                     f"{s['calls_median']} ({s['calls_range']}) | {s['refusals']} | "
                     f"{s['progress_mean']:.3f} |")
    lines += ["", PROGRESS_CAVEAT, "", ACCURATE_CLAIM]
    if result["lint"]:
        lines += [""] + [f"- LINT: {m}" for m in result["lint"]]
    if result.get("exploratory"):
        exp = result["exploratory"]
        lines += ["", f"## Exploratory arm ({exp['label']})", "", exp["note"], "",
                  "| Arm | Runs over budget | Calls (median, range) | Refusals | Progress (mean partial) |",
                  "|---|---|---|---|---|"]
        for s in exp["summary"]:
            lines.append(f"| {s['arm']} | {s['over_budget']}/{s['runs']} | "
                         f"{s['calls_median']} ({s['calls_range']}) | {s['refusals']} | "
                         f"{s['progress_mean']:.3f} |")
    return "\n".join(lines)


def main(seeds=None, arms=None, fmt="terminal") -> tuple[str, int]:
    result = run_demo(seeds, arms)
    if fmt == "json":
        return to_json(result), 0
    if fmt == "md":
        return render_markdown(result), 0
    return render_terminal(result), 0
