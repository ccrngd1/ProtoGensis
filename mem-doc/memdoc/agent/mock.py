"""MockAgent (DETERMINISTIC): the offline stand-in for a model (R1).

It exercises every arm's write path, read path, injection position, and token
flow. It is NOT a model of LLM competence; its outputs are "context delivery
(mechanism)", never accuracy. Rules are fixed in config/demo_crossover.toml and
covered by .mastercontrol/preregistration.md.

- ScriptedWriter: applies the storyline's FactEvent stream through each arm's
  own write API, same information for every arm. introduce -> add;
  correct_explicit -> doc arms rewrite in place, A4 UPDATE, A6 logs transcript;
  invalidate_implicit -> add new statement, remove nothing; enumerate -> one
  entry/line per item. Optional p_forget (default 0.0) is a seeded write-skip
  sweep, labeled exploratory wherever shown.
- Tool policy (probe phase): A2 opens every doc whose read_if shares >=1 content
  keyword with the probe prompt; A6 greps each probe content keyword; A4/A5 call
  memory_search with the probe prompt. Unknown-unknown probes therefore miss
  mechanically when the prompt reveals nothing (research §4.1 made explicit).
- ContextReader: collects canary-shaped tokens of the probe's answer type from
  assembled context; none -> ABSTAIN. Picks by (1) keyword overlap of the
  containing line with the probe; (2) explicit supersession marker; (3) later
  visible date; (4) earlier position. Ties break by canary string order.
"""

import random
import re

from ..text import CANARY_PATTERNS, content_keywords, find_canaries

SUPERSESSION_MARKERS = ("corrected", "reversed", "no longer", "supersedes",
                        "correction", "retired", "now binds", "now holds",
                        "now captures", "now serves", "now receives", "now takes")

_SESSION_RE = re.compile(r"\[session (\d+)\]|\(session (\d+)\)|session[- ](\d+)", re.IGNORECASE)


class ScriptedWriter:
    """Applies FactEvents through each backend's write API, uniformly."""

    def __init__(self, p_forget: float = 0.0, seed: int = 0):
        self.p_forget = p_forget
        self._rng = random.Random(("memdoc-forget", seed).__repr__())

    def apply_session(self, backend, storyline, session_idx):
        for event in storyline.facts:
            if event.session != session_idx:
                continue
            if self.p_forget > 0.0 and self._rng.random() < self.p_forget:
                continue  # seeded write skip (exploratory)
            apply = getattr(backend, "scripted_apply", None)
            if apply:
                apply(event, session_idx)


class ToolPolicy:
    """Deterministic probe-phase tool use per arm."""

    @staticmethod
    def gather(backend, probe) -> list[str]:
        """Context lines the tools deliver for this probe, in delivery order."""
        kws = content_keywords(probe.prompt)
        arm = backend.arm_id
        lines: list[str] = []
        if arm == "a2":
            for path, read_if in backend.catalog_entries():
                if kws & content_keywords(read_if):
                    lines.extend(backend.read_doc(path).splitlines())
        elif arm == "a6":
            for kw in sorted(kws):
                lines.extend(backend.grep(kw))
        elif arm in ("a3",):
            pass  # A3 has no search tool; tail injection only (on_turn)
        elif hasattr(backend, "memory_search"):
            for _, e in backend.memory_search(probe.prompt):
                lines.append(e["text"])
        return lines


class ContextReader:
    """Picks the answer from assembled context lines; deterministic."""

    @staticmethod
    def answer(context_lines, probe) -> str:
        pattern = CANARY_PATTERNS[probe.canary_type]
        kws = content_keywords(probe.prompt)
        candidates = []  # (canary, line, position = (line idx, char offset))
        for li, line in enumerate(context_lines):
            for m in pattern.finditer(line):
                candidates.append((m.group(1), line, (li, m.start())))
        if not candidates:
            return "ABSTAIN"

        def session_of(line):
            m = _SESSION_RE.search(line)
            if not m:
                return -1
            return int(next(g for g in m.groups() if g))

        best = None
        for canary, line, pos in candidates:
            overlap = len(kws & content_keywords(line))
            marker = any(m in line.lower() for m in SUPERSESSION_MARKERS)
            sess = session_of(line)
            key = (-overlap, 0 if marker else 1, -sess, pos, canary)
            if best is None or key < best[0]:
                best = (key, canary)
        return best[1]


class MockAgent:
    """Bundles the three deterministic components."""

    def __init__(self, p_forget: float = 0.0, seed: int = 0):
        self.writer = ScriptedWriter(p_forget=p_forget, seed=seed)
        self.tools = ToolPolicy()
        self.reader = ContextReader()
