"""Arm definitions and programmatic aggregation.

A1: single best model at effort E.
A2: best-of-N on the same model. Primary selection is programmatic:
    majority vote on the extracted answer (GPQA, math); public-test filtering
    then first-passing for code (tie-break: majority on output signature).
    No LLM selector in the primary path.
A3: 7-persona panel on the same model (prompt diversity only); same
    programmatic aggregation. An optional LLM-aggregator variant runs only if
    config names an aggregator that passes the rule-4 check.
A4a/A4b: cross-family panel + strong/weak aggregator. The aggregator sees the
    problem plus all panel responses and must output a final answer in the
    required format, graded programmatically. Records chain via
    parent_record_ids; arm cost = sum of parent costs + aggregator cost.

Post hoc majority vote for every panel is computed from existing records with
zero extra calls (majority_vote / select_code_response).
"""

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Proposal:
    """One panel member's response, typically backed by an existing record."""
    record_id: str
    model_id: str
    extracted_answer: str | None
    response_text: str = ""
    public_pass: bool | None = None       # code only
    output_signature: str = ""            # code only
    correct: bool | None = None


# ----------------------------------------------------------- majority voting

def majority_vote(proposals: list) -> tuple:
    """Majority vote on extracted answers (GPQA letters / normalized math).

    Returns (winning_answer or None, details). None answers do not vote.
    Ties break toward the answer appearing EARLIEST in the proposal order
    (deterministic, seed-independent).
    """
    votes = [p.extracted_answer for p in proposals if p.extracted_answer is not None]
    if not votes:
        return None, {"reason": "no extractable answers", "votes": {}}
    counts = Counter(votes)
    top = max(counts.values())
    tied = [a for a, c in counts.items() if c == top]
    if len(tied) == 1:
        winner = tied[0]
    else:
        winner = next(v for v in votes if v in tied)
    return winner, {
        "votes": dict(counts),
        "n_proposals": len(proposals),
        "n_voted": len(votes),
        "tie": len(tied) > 1,
    }


def select_code_response(proposals: list) -> tuple:
    """Programmatic code selection: filter to public-test passers, take the
    first passing proposal; tie-break (several passers) by majority on the
    public-test output signature. Falls back to signature majority over all
    proposals when none pass.

    Returns (selected Proposal or None, details).
    """
    passers = [p for p in proposals if p.public_pass]
    pool = passers if passers else [p for p in proposals if p.extracted_answer]
    if not pool:
        return None, {"reason": "no code extracted from any proposal"}
    sig_counts = Counter(p.output_signature for p in pool if p.output_signature)
    if sig_counts:
        top_sig, top_n = sig_counts.most_common(1)[0]
        if top_n > 1:
            for p in pool:
                if p.output_signature == top_sig:
                    return p, {"strategy": "signature-majority",
                               "n_passers": len(passers), "sig_votes": dict(sig_counts)}
    return pool[0], {"strategy": "first-passing" if passers else "first-extractable",
                     "n_passers": len(passers)}


# ----------------------------------------------------------------- personas

def load_personas(personas_dir) -> list:
    """The 7 April personas (prompt diversity only)."""
    personas = []
    for path in sorted(Path(personas_dir).glob("*.json")):
        d = json.loads(path.read_text())
        personas.append({
            "id": d["id"],
            "name": d["name"],
            "system_prompt": d["system_prompt"],
        })
    if len(personas) != 7:
        raise ValueError(f"expected 7 personas in {personas_dir}, found {len(personas)}")
    return personas


# ------------------------------------------------------- aggregator prompting

ANSWER_FORMATS = {
    "gpqa": 'End your response with a line of the form "Answer: X" where X is one of A, B, C, D.',
    "math": "Give the final answer inside \\boxed{}.",
    "code": "Give the complete final solution in a single ```python code block.",
}


def build_aggregator_prompt(task_set: str, problem_prompt: str, proposals: list) -> str:
    """The aggregator sees the problem plus all panel responses and must output
    a final answer in the required format (graded programmatically)."""
    parts = [
        "You are the aggregator for a panel of AI models. Below is a problem "
        "and the panel's candidate responses. Weigh them critically - panel "
        "members can be confidently wrong - and produce the single best final "
        "answer. You may side with a minority or derive a fresh answer if the "
        "panel is wrong.",
        "",
        "=== PROBLEM ===",
        problem_prompt.strip(),
        "",
    ]
    for i, p in enumerate(proposals, 1):
        parts += [
            f"=== PANEL RESPONSE {i} ===",
            p.response_text.strip() or "(empty response)",
            "",
        ]
    parts += [
        "=== YOUR TASK ===",
        "Give your final answer now. " + ANSWER_FORMATS[task_set],
    ]
    return "\n".join(parts)


@dataclass
class ArmSpec:
    arm: str                       # a1 | a2 | a3 | a4a | a4b
    model_id: str | None = None    # a1/a2/a3: the single model used
    n: int = 1                     # a2: N
    panel: list = field(default_factory=list)       # a4: panel profile ids
    aggregator: str | None = None  # a4: aggregator profile id
    aggregator_exempt_from_b: bool = False          # a4b weak-by-design


def arm_cost_usd(parent_costs: list, aggregator_cost: float | None = 0.0) -> float | None:
    """Arm cost = sum of parent costs + aggregator cost.

    None means UNKNOWN price and propagates: if any component is None the arm
    cost is None (never silently $0). Pass aggregator_cost=0.0 for
    programmatic (no-LLM) aggregation."""
    total = 0.0
    for c in list(parent_costs) + [aggregator_cost]:
        if c is None:
            return None
        total += c
    return total
