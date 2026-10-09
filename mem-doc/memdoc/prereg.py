"""Preregistration (AC #10): H1-H7 hard-coded, hash-locked before any run.

Hypothesis statements are verbatim from research §8. The analysis plan and the
cause-code taxonomy (AC #9) are part of the hashed content. PREREGISTRATION.md
is generated from this module; PREREG.lock holds the sha256 of the canonical
JSON. Never edit hypothesis text after lock; amendments go in an append-only
"## Amendments" section outside the hashed content.

Hypotheses are evaluated only on live run logs. On mock logs the report prints
"hypotheses not evaluated: mock run".
"""

import hashlib
import json
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
LOCK_PATH = PKG_ROOT / "PREREG.lock"
MD_PATH = PKG_ROOT / "PREREGISTRATION.md"

AMENDMENTS_MARKER = "## Amendments"


@dataclass(frozen=True)
class Hypothesis:
    id: str
    statement: str
    metric: str
    arms: tuple
    categories: tuple
    sizes: tuple
    comparison: str
    threshold: str
    test: str


HYPOTHESES = (
    Hypothesis(
        id="H1",
        statement=("H1 (size crossover): A1 ≥ A4 at 5K; A1 < A2 ≈ A5 at 100K. A1's cost "
                   "crosses A4's between 4K and 9K tokens (§5)."),
        metric="success rate; cached $ per session (memory overhead)",
        arms=("a1", "a2", "a4", "a5"),
        categories=(1, 2, 3, 4, 5, 6, 7, 8),
        sizes=(5000, 100000),
        comparison="A1 vs A4 at 5K (>=); A1 vs A2 and A5 at 100K (<); cost crossover in [4000, 9000]",
        threshold="'≈' preregistered as |diff| <= 5 pts",
        test="exact McNemar on paired pass/fail; seeded bootstrap 95% CI for the cost crossover",
    ),
    Hypothesis(
        id="H2",
        statement=("H2 (rationale): on categories 2 and 6, doc arms (A1/A2/A5) beat A4 by "
                   "≥10 pts."),
        metric="success rate",
        arms=("a1", "a2", "a5", "a4"),
        categories=(2, 6),
        sizes=(25000,),
        comparison="each of A1, A2, A5 vs A4",
        threshold=">= 10 pts",
        test="exact McNemar; seeded bootstrap 95% CI on the difference",
    ),
    Hypothesis(
        id="H3",
        statement=("H3 (supersession): the stale-answer rate is highest for A3/A6, lower for "
                   "A4 (with supersession), and lowest for A1/A2 *if* write fidelity ≥ 90%."),
        metric="stale-answer rate; write fidelity (condition)",
        arms=("a3", "a6", "a4", "a1", "a2"),
        categories=(3, 4),
        sizes=(25000,),
        comparison="ordering A3/A6 > A4 > A1/A2, conditional on A1/A2 write fidelity >= 90%",
        threshold="strict ordering; condition write fidelity >= 90% else condition-not-met",
        test="exact McNemar on paired stale/not-stale; ordering reported descriptively",
    ),
    Hypothesis(
        id="H4",
        statement="H4 (implicit conflict): no arm exceeds 60% on category 4 (STALE base rate).",
        metric="success rate",
        arms=("a0", "astar", "a1", "a2", "a4", "a5", "a6"),
        categories=(4,),
        sizes=(25000,),
        comparison="max over arms (A* excluded as ceiling) vs 60%",
        threshold="<= 60%",
        test="seeded bootstrap 95% CI on each arm's category-4 success rate",
    ),
    Hypothesis(
        id="H5",
        statement=("H5 (hybrid): A5 has the best success rate overall, and costs ≤ 1.5× A2 "
                   "per successful task."),
        metric="overall success rate; $ per successful task",
        arms=("a5", "a1", "a2", "a4", "a6"),
        categories=(1, 2, 3, 4, 5, 6, 7, 8),
        sizes=(25000,),
        comparison="A5 vs every other non-oracle arm; A5 cost vs 1.5x A2 cost",
        threshold="best overall; cost ratio <= 1.5",
        test="exact McNemar vs each arm; seeded bootstrap 95% CI on the cost ratio",
    ),
    Hypothesis(
        id="H6",
        statement=("H6 (silent failure): the silent-failure share is ≥2× higher for A3/A4 "
                   "than for A1/A2."),
        metric="silent-failure share of failed probes",
        arms=("a3", "a4", "a1", "a2"),
        categories=(1, 2, 3, 4, 5, 6, 7, 8),
        sizes=(25000,),
        comparison="pooled silent share A3/A4 vs 2x pooled silent share A1/A2",
        threshold=">= 2x",
        test="seeded bootstrap 95% CI on the ratio of shares",
    ),
    Hypothesis(
        id="H7",
        statement=("H7 (write policy): holding read policy constant (A5 core written in the "
                   "foreground vs by background extraction, as an ablation), foreground writes "
                   "beat background writes on categories 2 and 6. This is the testable form of "
                   "the §4.3 production example."),
        metric="success rate",
        arms=("a5", "a5bg"),
        categories=(2, 6),
        sizes=(25000,),
        comparison="A5 (core_writer=foreground) vs A5-bg (core_writer=background)",
        threshold="A5 > A5-bg",
        test="exact McNemar on paired pass/fail",
    ),
)

ANALYSIS_PLAN = {
    "pairing": "paired by storyline x seed",
    "pass_fail_test": "exact two-sided McNemar on discordant pairs (binomial)",
    "ci": "seeded bootstrap 95% CI, 10000 resamples",
    "bootstrap_seed": 20261009,
    "alpha": 0.05,
    "correction": "Holm across H1-H7",
    "evaluation": "hypotheses are evaluated only on live run logs; mock logs print "
                  "'hypotheses not evaluated: mock run'",
    "not_tested": "arms not built (A3, A5-bg) make dependent comparisons NOT_TESTED, "
                  "never silently dropped",
}

# AC #9 cause taxonomy. Visible = cause locatable by inspecting the persisted
# store alone; silent = everything else. Part of the hashed content.
CAUSE_TAXONOMY = {
    "write_miss": {"description": "fact never stored", "class": "visible"},
    "stale_in_store": {"description": "superseded value still stored as current", "class": "visible"},
    "retrieval_miss": {"description": "stored, not delivered to context", "class": "silent"},
    "catalog_miss": {"description": "stored in a doc the agent never opened", "class": "silent"},
    "rank_stale": {"description": "both values delivered, stale one first or chosen", "class": "silent"},
    "applied_wrong": {"description": "correct fact in context, wrong answer", "class": "silent"},
}

# Deterministic cause-assignment rule (AC #9), applied to every failed probe in
# this order; the first matching clause is the cause. Inputs are logged state
# only: store snapshot, per-call context log, and the answer.
CAUSE_ASSIGNMENT_RULE = (
    "For a failed probe, assign the first matching cause in this order: "
    "(1) gold != ABSTAIN and the gold canary is absent from the store snapshot -> write_miss; "
    "(2) the superseded canary is stored as current (present and not marked superseded), "
    "the answer equals the superseded canary, and the gold canary was not delivered to "
    "context -> stale_in_store; "
    "(3) gold stored but not delivered to context: read_policy == catalog -> catalog_miss, "
    "otherwise -> retrieval_miss; "
    "(4) gold and superseded canary both delivered and the answer equals the superseded "
    "canary -> rank_stale; "
    "(5) otherwise (gold delivered, wrong answer; includes answering instead of ABSTAIN) "
    "-> applied_wrong."
)


def canonical_json() -> str:
    payload = {
        "hypotheses": [asdict(h) for h in HYPOTHESES],
        "analysis_plan": ANALYSIS_PLAN,
        "cause_taxonomy": CAUSE_TAXONOMY,
        "cause_assignment_rule": CAUSE_ASSIGNMENT_RULE,
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def prereg_hash() -> str:
    return hashlib.sha256(canonical_json().encode("utf-8")).hexdigest()


def render_markdown() -> str:
    """Generated PREREGISTRATION.md (hashed content only; amendments live below
    the marker and are never hashed)."""
    lines = [
        "# MemDoc Preregistration",
        "",
        "Generated from `memdoc/prereg.py`. The sha256 of the canonical JSON of the",
        "hypotheses, analysis plan, and cause taxonomy below is locked in `PREREG.lock`.",
        "Hypothesis text is never edited after lock; amendments are appended under",
        f"`{AMENDMENTS_MARKER}` and are outside the hashed content.",
        "",
        f"**Prereg hash:** `{prereg_hash()}`",
        "",
        "## Hypotheses (verbatim from research §8)",
        "",
    ]
    for h in HYPOTHESES:
        lines += [f"### {h.id}", "", h.statement, "",
                  f"- metric: {h.metric}",
                  f"- arms: {', '.join(h.arms)}",
                  f"- categories: {', '.join(str(c) for c in h.categories)}",
                  f"- sizes: {', '.join(str(s) for s in h.sizes)}",
                  f"- comparison: {h.comparison}",
                  f"- threshold: {h.threshold}",
                  f"- test: {h.test}", ""]
    lines += ["## Analysis plan", ""]
    for k in sorted(ANALYSIS_PLAN):
        lines.append(f"- **{k}:** {ANALYSIS_PLAN[k]}")
    lines += ["", "## Cause-code taxonomy (AC #9)", ""]
    for k in CAUSE_TAXONOMY:  # insertion order = preregistered order
        c = CAUSE_TAXONOMY[k]
        lines.append(f"- `{k}` ({c['class']}): {c['description']}")
    lines += ["", "**Assignment rule:** " + CAUSE_ASSIGNMENT_RULE]
    lines += ["", "Each hypothesis is reported as SUPPORTED, NOT_SUPPORTED, or NOT_TESTED",
              "(with the reason). Hypotheses are evaluated only on live run logs.", ""]
    return "\n".join(lines)


def write_lock():
    LOCK_PATH.write_text(prereg_hash() + "\n", encoding="utf-8")


def write_markdown():
    existing_amendments = ""
    if MD_PATH.exists():
        text = MD_PATH.read_text(encoding="utf-8")
        idx = text.find(AMENDMENTS_MARKER)
        if idx != -1:
            existing_amendments = "\n" + text[idx:]
    MD_PATH.write_text(render_markdown() + existing_amendments, encoding="utf-8")


def verify(lock_path=None) -> tuple[bool, str]:
    path = Path(lock_path) if lock_path else LOCK_PATH
    if not path.exists():
        return False, f"PREREG.lock not found at {path}"
    locked = path.read_text(encoding="utf-8").strip()
    current = prereg_hash()
    if locked == current:
        return True, f"prereg hash matches lock: {current}"
    return False, f"prereg hash MISMATCH: lock={locked} current={current}"


def verify_history(repo_dir=None, lock_relpath=None, results_relpath=None) -> tuple[bool, str]:
    """Check git order: the lock must be committed before any results commit.

    (i) lock committed, no results commits -> pass
    (ii) a results commit precedes the lock's first commit -> fail
    (iii) lock not committed yet -> fail with a clear message
    """
    repo = Path(repo_dir) if repo_dir else PKG_ROOT
    lock_rel = lock_relpath or "PREREG.lock"
    results_rel = results_relpath or "results"

    def first_commit_time(path_in_repo):
        r = subprocess.run(
            ["git", "log", "--follow", "--diff-filter=A", "--format=%ct", "--", path_in_repo],
            cwd=repo, capture_output=True, text=True)
        times = [int(x) for x in r.stdout.split() if x.strip()]
        return min(times) if times else None

    lock_t = first_commit_time(lock_rel)
    if lock_t is None:
        return False, ("PREREG.lock is not committed yet: commit the lock before any "
                       "results commit (prereg verify --history fails until then)")
    r = subprocess.run(["git", "log", "--format=%ct", "--", results_rel],
                       cwd=repo, capture_output=True, text=True)
    result_times = [int(x) for x in r.stdout.split() if x.strip()]
    # Ignore commits that only touch results/.gitkeep (the placeholder).
    if result_times:
        r2 = subprocess.run(["git", "log", "--format=%H %ct", "--", results_rel],
                            cwd=repo, capture_output=True, text=True)
        real_times = []
        for line in r2.stdout.splitlines():
            h, t = line.split()
            files = subprocess.run(
                ["git", "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", h,
                 "--", results_rel],
                cwd=repo, capture_output=True, text=True).stdout.split()
            if any(not f.endswith(".gitkeep") for f in files):
                real_times.append(int(t))
        result_times = real_times
    if not result_times:
        return True, "lock committed; no results commits (pass)"
    earliest = min(result_times)
    if earliest < lock_t:
        return False, "a results commit precedes the PREREG.lock commit (fail)"
    return True, "lock commit precedes all results commits (pass)"
