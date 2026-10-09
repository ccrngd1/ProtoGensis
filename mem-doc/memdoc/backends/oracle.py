"""A*: oracle. Current gold facts for the probe (superseded excluded) in the
system prefix. Ceiling and task-validity check (AC #7)."""

from .base import ContextParts, MemoryBackend, StoreSnapshot


class OracleBackend(MemoryBackend):
    arm_id = "astar"
    name = "oracle"
    write_policy = "n/a"
    read_policy = "oracle"
    inject = "prefix"

    def __init__(self, workdir, tokenizer, config=None):
        super().__init__(workdir, tokenizer, config)
        self._facts = []          # current (non-superseded) FactEvents, in order

    def scripted_apply(self, event, session_idx):
        if event.kind == "correct_explicit" and event.supersedes:
            self._facts = [f for f in self._facts if f.canary != event.supersedes]
        self._facts.append(event)

    def fill_distractors(self, distractor_sessions):
        return None

    def bootstrap(self, session) -> ContextParts:
        """Only the current gold facts needed by this session's probes."""
        probes = getattr(session, "probes", [])
        # The oracle delivers the *current* gold facts only (superseded values
        # excluded): for each non-abstention probe, exactly the fact lines that
        # carry the probe's gold canary. Implicitly invalidated facts are
        # superseded in ground truth, so they are excluded too. Abstention
        # probes get nothing.
        lines = []
        for f in self._facts:
            for p in probes:
                if p.gold != "ABSTAIN" and f.key in p.fact_keys and p.gold == f.canary:
                    if f.text not in lines:
                        lines.append(f.text)
        prefix = "Gold facts for this session:\n" + "\n".join(lines) if lines else ""
        return ContextParts(system_prefix=prefix)

    def store_snapshot(self) -> StoreSnapshot:
        text = "\n".join(f.text for f in self._facts)
        return StoreSnapshot(kind="none", texts={"oracle": text},
                             token_estimate=self.tok.count(text))
