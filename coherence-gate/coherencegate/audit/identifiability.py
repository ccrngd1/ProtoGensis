"""Identifiability audit: Thm 2.1 / 2.3 of arXiv 2610.02036 as a test.

Observation aliasing is the paper's Failure 1: information is MISSING. Two
worlds look identical and need different actions, so no policy (however many
agents, votes, or reasoning passes) can beat 1/k. This is a different failure
from stale reads (which live in the gate as read-set validation).

Ships a Study I-style generator: a 60-event revision log, 3 teams,
commit/revert/re-apply on one parameter, where the final event is one of 3
ops giving 3 distinct heads. The aliased variant redacts the final event with
the same bytes for every truth (exact by construction; a test asserts sha256
equality). The +fact variant appends one authoritative sentence naming the
head. Mock arms are deterministic functions of the prompt bytes, so under
all-truths evaluation the 1/k result is exact. This shows the theorem as
executable mechanism; it is not an LLM measurement.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field

TEAMS = ("alpha", "beta", "gamma")
TRUTH_OPS = ("commit", "revert", "reapply")  # the 3 possible final events


@dataclass
class Task:
    task_id: int
    events: list[str]            # the 59 visible event lines
    final_events: dict[int, str]  # truth -> event-60 line
    heads: dict[int, str]         # truth -> correct head commit id
    candidates: list[str]         # the 3 possible heads, sorted


def _simulate(events: list[str]) -> tuple[list[str], list[str]]:
    """Replay event lines -> (stack, reverted). Head is stack[-1]."""
    stack: list[str] = []
    reverted: list[str] = []
    for line in events:
        parts = line.split()
        op, cid = parts[1], parts[2]
        if op == "commit" or op == "reapply":
            if op == "reapply":
                reverted.remove(cid)
            stack.append(cid)
        elif op == "revert":
            stack.remove(cid)
            reverted.append(cid)
    return stack, reverted


def generate_task(task_id: int, seed: int = 0) -> Task:
    rng = random.Random(seed * 100003 + task_id)
    stack: list[str] = []
    reverted: list[str] = []
    events: list[str] = []
    counter = 0

    def do_commit():
        nonlocal counter
        counter += 1
        cid = f"c{counter:02d}"
        stack.append(cid)
        events.append(f"{rng.choice(TEAMS)} commit {cid} param={rng.randint(1, 99)}")

    def do_revert():
        cid = stack.pop()
        reverted.append(cid)
        events.append(f"{rng.choice(TEAMS)} revert {cid}")

    def do_reapply():
        cid = reverted.pop(rng.randrange(len(reverted)))
        stack.append(cid)
        events.append(f"{rng.choice(TEAMS)} reapply {cid}")

    for _ in range(56):
        ops = [do_commit]
        if len(stack) >= 2:
            ops.append(do_revert)
        if reverted:
            ops.append(do_reapply)
        rng.choice(ops)()
    # force final-event preconditions: >=2 on stack, >=1 reverted
    do_commit()
    do_commit()
    do_revert()
    assert len(events) == 59 and len(stack) >= 2 and reverted

    # the three truths for event 60
    new_cid = f"c{counter + 1:02d}"
    team = rng.choice(TEAMS)
    reapply_cid = reverted[-1]
    final_events = {
        0: f"{team} commit {new_cid} param={rng.randint(1, 99)}",
        1: f"{team} revert {stack[-1]}",
        2: f"{team} reapply {reapply_cid}",
    }
    heads = {0: new_cid, 1: stack[-2], 2: reapply_cid}
    assert len(set(heads.values())) == 3, "the 3 heads must be distinct"
    return Task(task_id=task_id, events=events, final_events=final_events,
                heads=heads, candidates=sorted(heads.values()))


def render_prompt(task: Task, truth: int, variant: str) -> str:
    """Render the context for one (task, truth, variant). variant is one of
    identifiable | aliased | fact. Aliased bytes are identical across truths."""
    lines = [
        "You are tracking one parameter under concurrent team edits.",
        f"Revision log for task {task.task_id:03d} (60 events, 3 teams):",
    ]
    for i, ev in enumerate(task.events, start=1):
        lines.append(f"e{i:02d}: {ev}")
    if variant == "identifiable":
        lines.append(f"e60: {task.final_events[truth]}")
    else:
        lines.append("e60: [REDACTED]")
    if variant == "fact":
        lines.append(f"Authoritative: the current head is {task.heads[truth]}.")
    lines.append("Question: name the current head commit.")
    return "\n".join(lines)


def prompt_sha256(task: Task, truth: int, variant: str) -> str:
    return hashlib.sha256(render_prompt(task, truth, variant).encode()).hexdigest()


# ---------------------------------------------------------------- mock arms
# Every policy is a deterministic function of the prompt bytes alone, so on
# byte-identical aliased prompts its answer cannot depend on the truth.

def _parse(prompt: str) -> tuple[list[str], str | None, str | None]:
    events, final, fact = [], None, None
    for line in prompt.splitlines():
        if line.startswith("e60: "):
            body = line[len("e60: "):]
            final = None if body == "[REDACTED]" else body
        elif line[:1] == "e" and ": " in line[:6]:
            events.append(line.split(": ", 1)[1])
        elif line.startswith("Authoritative: the current head is "):
            fact = line.split()[-1].rstrip(".")
    return events, final, fact


def _candidates(events: list[str]) -> list[str]:
    """The 3 possible heads given the visible 59 events."""
    stack, reverted = _simulate(events)
    counter = max(int(c[1:]) for c in stack + reverted)
    return sorted({f"c{counter + 1:02d}", stack[-2], reverted[-1]})


def policy_competent(prompt: str) -> str:
    """Computes the head from the visible events. If event 60 is redacted and
    no authoritative fact is present, it must still answer; it deterministically
    picks the lexicographically smallest candidate head."""
    events, final, fact = _parse(prompt)
    if fact:
        return fact
    if final is not None:
        stack, _ = _simulate(events + [final])
        return stack[-1]
    return _candidates(events)[0]


def policy_planner_verifier(prompt: str) -> str:
    """Composition of two mock policies: the planner proposes the newest
    plausible candidate; the verifier re-checks it is consistent with the
    visible events (it always is: that's Cor 2.2) and signs off."""
    events, final, fact = _parse(prompt)
    if fact:
        return fact
    if final is not None:
        stack, _ = _simulate(events + [final])
        return stack[-1]
    proposal = _candidates(events)[-1]  # planner: newest id
    verifier_ok = proposal in _candidates(events)  # verifier sees the same bytes
    assert verifier_ok
    return proposal


def policy_majority5(prompt: str) -> str:
    """5 seeded variants vote; majority wins, ties broken by sorted order.
    All five see the same bytes, so the vote cannot add information."""
    events, final, fact = _parse(prompt)
    if fact:
        return fact
    if final is not None:
        stack, _ = _simulate(events + [final])
        return stack[-1]
    cands = _candidates(events)
    digest = hashlib.sha256(prompt.encode()).digest()
    votes = [cands[digest[i] % len(cands)] for i in range(5)]
    tally = sorted(((votes.count(c), c) for c in set(votes)), key=lambda t: (-t[0], t[1]))
    return tally[0][1]


def make_tool_policy(task: Task, truth: int, can_see_final: bool):
    """A policy with a query tool. blind_tool returns only events 1-59;
    reading_tool can read event 60."""
    def policy(prompt: str) -> str:
        events, final, fact = _parse(prompt)
        if fact:
            return fact
        if final is not None:  # the prompt itself shows event 60
            stack, _ = _simulate(events + [final])
            return stack[-1]
        if can_see_final:
            tool_result = task.final_events[truth]  # the tool reads the event
            stack, _ = _simulate(events + [tool_result])
            return stack[-1]
        _ = list(task.events)  # the tool re-reads what the prompt already shows
        return _candidates(events)[0]
    return policy


# ---------------------------------------------------------------- audit
@dataclass
class Fiber:
    sha256: str
    worlds: list[tuple[int, int]]  # (task_id, truth)
    k: int
    intersection_empty: bool
    bound: float


@dataclass
class AuditResult:
    fibers: list[Fiber]
    identifiable: bool
    max_k: int
    worst_bound: float
    n_worlds: int = 0
    aliased_fibers: int = 0


def audit(tasks: list[Task], variant: str) -> AuditResult:
    """Group worlds by rendered-context sha256 into fibers; report k, whether
    the intersection of admissible sets is empty, and the bound 1/k."""
    by_hash: dict[str, list[tuple[int, int]]] = {}
    for task in tasks:
        for truth in (0, 1, 2):
            h = prompt_sha256(task, truth, variant)
            by_hash.setdefault(h, []).append((task.task_id, truth))
    task_by_id = {t.task_id: t for t in tasks}
    fibers = []
    for h, worlds in sorted(by_hash.items()):
        k = len(worlds)
        # admissible set per world is the singleton {correct head}
        admissible = [{task_by_id[tid].heads[truth]} for tid, truth in worlds]
        inter = set.intersection(*admissible)
        fibers.append(Fiber(sha256=h, worlds=worlds, k=k,
                            intersection_empty=not inter, bound=1.0 / k))
    aliased = [f for f in fibers if f.k > 1 and f.intersection_empty]
    max_k = max(f.k for f in fibers)
    return AuditResult(
        fibers=fibers,
        identifiable=not aliased,
        max_k=max_k,
        worst_bound=min(f.bound for f in fibers),
        n_worlds=sum(f.k for f in fibers),
        aliased_fibers=len(aliased),
    )


def evaluate_all_truths(tasks: list[Task], variant: str, arm: str) -> dict:
    """Score an arm's answers against all 3 truths per task (40 x 3 = 120
    episodes). Exact 1/k for deterministic policies on aliased prompts."""
    policies = {
        "competent": lambda t, tr: policy_competent,
        "planner_verifier": lambda t, tr: policy_planner_verifier,
        "majority5": lambda t, tr: policy_majority5,
        "blind_tool": lambda t, tr: make_tool_policy(t, tr, can_see_final=False),
        "reading_tool": lambda t, tr: make_tool_policy(t, tr, can_see_final=True),
    }
    make_policy = policies[arm]
    correct = 0
    total = 0
    for task in tasks:
        for truth in (0, 1, 2):
            prompt = render_prompt(task, truth, variant)
            answer = make_policy(task, truth)(prompt)
            total += 1
            if answer == task.heads[truth]:
                correct += 1
    return {"arm": arm, "variant": variant, "correct": correct, "total": total}


def generate_family(n_tasks: int = 40, seed: int = 0) -> list[Task]:
    return [generate_task(i, seed=seed) for i in range(n_tasks)]
