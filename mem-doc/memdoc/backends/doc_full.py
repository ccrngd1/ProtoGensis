"""A1 doc-full: foreground writes, always-load whole workspace (research §6.1).

Per-run workspace dir with CABAL-shaped files (synthetic layout: AGENTS.md,
MEMORY.md, topic files; no CABAL content, R9). All files enter the system prefix
before a cachePoint. At session end the working agent edits the docs; prompts
in prompts/doc_full_write.md follow the "rewrite facts when the truth changes;
don't append" convention. After each session the workspace is git-committed
(free audit trail + decay data). Should-ship flag edit_mode=diff|rewrite.
"""

import subprocess
from pathlib import Path

from .base import ContextParts, MemoryBackend, StoreSnapshot, WriteReport

AGENTS_SEED = """# AGENTS.md (synthetic workspace)

Conventions for this workspace:
- Record only what the task environment cannot reveal: decisions and rationale,
  preferences, failed approaches, external facts.
- Rewrite facts when the truth changes; don't append corrections after stale text.
- Keep MEMORY.md curated; move long narratives to topic files.
"""

MEMORY_SEED = """# MEMORY.md (synthetic workspace)

Curated long-term memory. One fact per line under the Facts heading.

## Facts
"""


class DocFullBackend(MemoryBackend):
    arm_id = "a1"
    name = "doc_full"
    write_policy = "foreground"
    read_policy = "always_load"
    inject = "prefix"

    def __init__(self, workdir, tokenizer, config=None):
        super().__init__(workdir, tokenizer, config)
        self.ws = Path(workdir) / "workspace_a1"
        self.edit_mode = (config or {}).get("edit_mode", "diff")  # diff | rewrite
        self.git = (config or {}).get("git_commits", True)
        if not self.ws.exists():
            self.ws.mkdir(parents=True)
            (self.ws / "AGENTS.md").write_text(AGENTS_SEED, encoding="utf-8")
            (self.ws / "MEMORY.md").write_text(MEMORY_SEED, encoding="utf-8")
            if self.git:
                self._git("init", "-q")
                self._commit("seed workspace")
        self._pending_edits = 0

    def _git(self, *args):
        subprocess.run(["git", "-c", "user.name=memdoc", "-c", "user.email=memdoc@localhost",
                        *args], cwd=self.ws, capture_output=True, text=True, check=False)

    def _commit(self, msg):
        if self.git:
            self._git("add", "-A")
            self._git("commit", "-q", "-m", msg, "--allow-empty")

    # -- scripted write API (MockAgent ScriptedWriter) -------------------------
    def scripted_apply(self, event, session_idx):
        """introduce/enumerate -> add line; correct_explicit -> rewrite in place;
        invalidate_implicit -> add new statement, remove nothing."""
        mem = self.ws / "MEMORY.md"
        text = mem.read_text(encoding="utf-8")
        if event.kind == "correct_explicit" and event.supersedes:
            lines = text.split("\n")
            replaced = False
            for i, line in enumerate(lines):
                if event.supersedes in line and line.strip().startswith("-"):
                    lines[i] = f"- {event.text}"
                    replaced = True
                    break
            text = "\n".join(lines)
            if not replaced:
                text += f"- {event.text}\n"
        else:
            text += f"- {event.text}\n"
        mem.write_text(text, encoding="utf-8")
        self._pending_edits += 1

    def fill_distractors(self, distractor_sessions):
        """Append distractor lines to topic files until size control takes over."""
        for d in distractor_sessions:
            topic = self.ws / f"notes-{d.id}.md"
            topic.write_text(f"# Session notes {d.id}\n\n" +
                             "\n".join(f"- {ln}" for ln in d.lines) + "\n", encoding="utf-8")
        self._commit("distractor fill")

    # -- read path --------------------------------------------------------------
    def bootstrap(self, session) -> ContextParts:
        parts = []
        for p in sorted(self.ws.glob("*.md")):
            parts.append(f"<file name=\"{p.name}\">\n{p.read_text(encoding='utf-8')}\n</file>")
        return ContextParts(system_prefix="Workspace documents:\n" + "\n".join(parts))

    def on_session_end(self, transcript) -> WriteReport:
        n = self._pending_edits
        self._pending_edits = 0
        self._commit(f"session end: {getattr(transcript, 'session_id', '')}")
        # one end-of-task doc edit, ~600 output tokens (cost model's write term)
        return WriteReport(entries_written=n, output_tokens=600 if n else 0)

    def store_snapshot(self) -> StoreSnapshot:
        texts = {p.name: p.read_text(encoding="utf-8") for p in sorted(self.ws.glob("*.md"))}
        total = sum(self.tok.count(t) for t in texts.values())
        return StoreSnapshot(kind="docs", texts=texts, token_estimate=total)
