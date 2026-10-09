"""`memdoc tasks validate` (AC #2): exits 0 only if every rule holds.

Rules (each returns a list of violation strings):
  (a) non-recoverability: no gold canary under world/ or in any probe prompt
  (b) cross-session: every probe runs >=1 session after its facts' last event
  (c) category 7: abstention probes have gold ABSTAIN and a near-miss distractor
  (d) categories 2 and 6: >=1 unknown-unknown probe per storyline, with
      stopword-filtered keyword overlap exactly 0 against the fact text
  (e) >=3 enumeration facts across the suite
  (f) every storyline: >=2 sessions before its first probe; 3-4 probes; every
      probe records a dependency depth
"""

from pathlib import Path

from ..text import content_keywords, contains_canary
from .schema import Storyline, load_all


def check_non_recoverability(s: Storyline, tasks_dir) -> list[str]:
    out = []
    world = Path(tasks_dir) / s.id / s.world_dir
    world_texts = {}
    if world.is_dir():
        for p in sorted(world.rglob("*")):
            if p.is_file():
                world_texts[str(p.relative_to(world))] = p.read_text(encoding="utf-8")
    golds = {f.canary for f in s.facts}
    for g in sorted(golds):
        for rel, text in world_texts.items():
            if contains_canary(text, g):
                out.append(f"{s.id}: canary {g} recoverable from world/{rel}")
        for rel in world_texts:
            if g in rel:
                out.append(f"{s.id}: canary {g} appears in world filename {rel}")
    for p in s.probes:
        for g in sorted(golds):
            if contains_canary(p.prompt, g):
                out.append(f"{s.id}/{p.id}: canary {g} appears in the probe prompt")
    return out


def check_cross_session(s: Storyline) -> list[str]:
    out = []
    for p in s.probes:
        last_event = 0
        for f in s.facts:
            if f.key in p.fact_keys:
                last_event = max(last_event, f.session)
        if last_event == 0:
            out.append(f"{s.id}/{p.id}: fact_keys match no fact")
        elif p.session <= last_event:
            out.append(f"{s.id}/{p.id}: probe session {p.session} not after fact session {last_event}")
    return out


def check_abstention(s: Storyline) -> list[str]:
    if s.category != 7:
        return []
    out = []
    abstains = [p for p in s.probes if p.gold == "ABSTAIN"]
    if not abstains:
        out.append(f"{s.id}: category 7 has no ABSTAIN probe")
    if not any(f.near_miss for f in s.facts):
        out.append(f"{s.id}: category 7 has no near-miss distractor fact in memory")
    return out


def check_unknown_unknown(s: Storyline) -> list[str]:
    if s.category not in (2, 6):
        return []
    out = []
    uu = [p for p in s.probes if p.unknown_unknown]
    if not uu:
        out.append(f"{s.id}: category {s.category} storyline has no unknown-unknown probe")
    for p in uu:
        for f in s.facts:
            if f.key in p.fact_keys:
                overlap = content_keywords(p.prompt) & content_keywords(f.text)
                if overlap:
                    out.append(f"{s.id}/{p.id}: unknown-unknown keyword overlap {sorted(overlap)}")
    return out


def check_enumeration(storylines: list[Storyline]) -> list[str]:
    n = sum(1 for s in storylines for f in s.facts if f.kind == "enumerate")
    if n < 3:
        return [f"suite: only {n} enumeration facts; need >=3"]
    return []


def check_structure(s: Storyline) -> list[str]:
    out = []
    if not s.probes or not (3 <= len(s.probes) <= 4):
        out.append(f"{s.id}: {len(s.probes)} probes; need 3-4")
    first_probe = min((p.session for p in s.probes), default=0)
    writes_before = sum(1 for x in s.sessions if x.kind == "write" and x.index < first_probe)
    if writes_before < 2:
        out.append(f"{s.id}: only {writes_before} write sessions before the first probe; need >=2")
    for p in s.probes:
        if p.depth < 1:
            out.append(f"{s.id}/{p.id}: missing dependency depth")
    return out


def min_uu_overlap(storylines: list[Storyline]) -> int:
    """Measured min keyword overlap across all unknown-unknown probes (status.md)."""
    best = None
    for s in storylines:
        for p in s.probes:
            if not p.unknown_unknown:
                continue
            for f in s.facts:
                if f.key in p.fact_keys:
                    n = len(content_keywords(p.prompt) & content_keywords(f.text))
                    best = n if best is None else max(best, n)
    return -1 if best is None else best


def validate(tasks_dir) -> list[str]:
    tasks_dir = Path(tasks_dir)
    storylines = load_all(tasks_dir)
    violations = []
    if len(storylines) < 40:
        violations.append(f"suite: {len(storylines)} storylines; need >=40")
    cats = {}
    for s in storylines:
        cats[s.category] = cats.get(s.category, 0) + 1
    for c in range(1, 9):
        if cats.get(c, 0) < 5:
            violations.append(f"suite: category {c} has {cats.get(c, 0)} storylines; need 5")
    for s in storylines:
        violations += check_non_recoverability(s, tasks_dir)
        violations += check_cross_session(s)
        violations += check_abstention(s)
        violations += check_unknown_unknown(s)
        violations += check_structure(s)
    violations += check_enumeration(storylines)
    return violations
