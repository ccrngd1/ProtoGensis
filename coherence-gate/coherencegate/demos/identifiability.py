"""Identifiability demo (AC #9): the aliasing probe as an arm table.

Observation aliasing is Failure 1: information is MISSING from the context.
Every deterministic arm on the aliased variant lands at exactly chance under
all-truths evaluation; one authoritative sentence (or a tool that can read
the event) restores full score. This shows Thm 2.1/2.3 as executable
mechanism; it is not an LLM measurement.
"""
from __future__ import annotations

from ..audit.identifiability import audit, evaluate_all_truths, generate_family
from ._common import BANNER, header, paper_block, table, to_json

ARMS = ("competent", "planner_verifier", "majority5", "blind_tool")


def run_demo(n_tasks: int = 40, seed: int = 0) -> dict:
    family = generate_family(n_tasks=n_tasks, seed=seed)
    rows = []
    for arm in ARMS:
        for variant in ("identifiable", "aliased"):
            r = evaluate_all_truths(family, variant, arm)
            rows.append(r)
    rows.append(evaluate_all_truths(family, "aliased", "reading_tool"))
    rows.append(evaluate_all_truths(family, "fact", "competent"))
    audit_aliased = audit(family, "aliased")
    audit_fact = audit(family, "fact")
    return {
        "banner": BANNER,
        "n_tasks": n_tasks,
        "episodes_per_variant": n_tasks * 3,
        "arms": rows,
        "audit": {
            "aliased": {"identifiable": audit_aliased.identifiable,
                        "max_k": audit_aliased.max_k,
                        "bound": round(audit_aliased.worst_bound, 6),
                        "aliased_fibers": audit_aliased.aliased_fibers},
            "fact": {"identifiable": audit_fact.identifiable,
                     "max_k": audit_fact.max_k,
                     "bound": round(audit_fact.worst_bound, 6),
                     "aliased_fibers": audit_fact.aliased_fibers},
        },
    }


def render_terminal(result: dict) -> str:
    lines = header("identifiability — the aliasing probe (Study I analogue)")
    lines.append(f"{result['n_tasks']} tasks x 3 truths = "
                 f"{result['episodes_per_variant']} episodes per variant "
                 "(all-truths evaluation; exact 1/k for deterministic policies).")
    lines.append("")
    rows = [{"arm": r["arm"], "variant": r["variant"],
             "score": f"{r['correct']}/{r['total']}"} for r in result["arms"]]
    lines.extend(table(rows, ["arm", "variant", "score"]))
    a = result["audit"]["aliased"]
    lines.append("")
    lines.append(f"Audit (aliased): identifiable={a['identifiable']}, k={a['max_k']}, "
                 f"bound 1/k = {a['bound']:.4f}, aliased fibers {a['aliased_fibers']}")
    f = result["audit"]["fact"]
    lines.append(f"Audit (+fact):   identifiable={f['identifiable']}, k={f['max_k']}, "
                 f"bound = {f['bound']:.4f}")
    lines.append("")
    lines.append("The mock arms SHOW the theorem; the paper's arms MEASURED it on a model.")
    lines.extend(paper_block(
        "arXiv 2610.02036 Study I, gpt-6-sol",
        ["identifiable 40/40 in every arm",
         "aliased: low/med/high effort 12/17/14; planner+verifier 13; "
         "5-vote majority 13/39; blind tool 13",
         "reading tool 40/40; one authoritative sentence 40/40"]))
    return "\n".join(lines)


def main(n_tasks: int = 40, fmt: str = "terminal") -> tuple[str, int]:
    result = run_demo(n_tasks=n_tasks)
    if fmt == "json":
        return to_json(result), 0
    return render_terminal(result), 0
