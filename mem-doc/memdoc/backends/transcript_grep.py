"""A6 transcript-grep: no write policy, agent search over raw transcripts.

Raw session transcripts are saved to disk. Tools: grep(pattern, path_glob) and
read(path, offset, limit). The prefix holds only a one-line note saying where
transcripts live.
"""

import re
from pathlib import Path

from .base import ContextParts, MemoryBackend, StoreSnapshot, ToolSpec, WriteReport


class TranscriptGrepBackend(MemoryBackend):
    arm_id = "a6"
    name = "transcript_grep"
    write_policy = "none"
    read_policy = "agent_search"
    inject = "none"

    def __init__(self, workdir, tokenizer, config=None):
        super().__init__(workdir, tokenizer, config)
        self.tdir = Path(workdir) / "transcripts_a6"
        self.tdir.mkdir(parents=True, exist_ok=True)
        self._counter = 0

    # ScriptedWriter: A6 just logs the transcript line for every event kind.
    def scripted_apply(self, event, session_idx):
        p = self.tdir / f"session-{session_idx:03d}.txt"
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(event.text + "\n")

    def fill_distractors(self, distractor_sessions):
        for i, d in enumerate(distractor_sessions):
            p = self.tdir / f"distractor-{d.id}.txt"
            p.write_text("\n".join(d.lines) + "\n", encoding="utf-8")

    def bootstrap(self, session) -> ContextParts:
        return ContextParts(system_prefix=(
            "Raw session transcripts live under transcripts/; use grep and read."))

    def tools(self):
        return [
            ToolSpec(name="grep", description="search transcripts",
                     input_schema={"pattern": "string", "path_glob": "string"}),
            ToolSpec(name="read", description="read a transcript file",
                     input_schema={"path": "string", "offset": "int", "limit": "int"}),
        ]

    def grep(self, pattern: str, path_glob: str = "*.txt"):
        """Deterministic grep over transcripts; returns matching lines in path order."""
        out = []
        try:
            rx = re.compile(pattern, re.IGNORECASE)
        except re.error:
            rx = re.compile(re.escape(pattern), re.IGNORECASE)
        for p in sorted(self.tdir.glob(path_glob)):
            for line in p.read_text(encoding="utf-8").splitlines():
                if rx.search(line):
                    out.append(line)
        return out

    def read(self, path: str, offset: int = 0, limit: int = 50):
        p = self.tdir / path
        if not p.exists():
            return []
        return p.read_text(encoding="utf-8").splitlines()[offset:offset + limit]

    def transcript_count(self) -> int:
        return len(list(self.tdir.glob("*.txt")))

    def on_session_end(self, transcript) -> WriteReport:
        return WriteReport()

    def store_snapshot(self) -> StoreSnapshot:
        texts = {p.name: p.read_text(encoding="utf-8") for p in sorted(self.tdir.glob("*.txt"))}
        total = sum(self.tok.count(t) for t in texts.values())
        return StoreSnapshot(kind="transcripts", texts=texts, token_estimate=total)
