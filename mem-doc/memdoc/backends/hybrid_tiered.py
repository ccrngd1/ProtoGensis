"""A5 hybrid-tiered: CABAL as it really runs (budgeted core + episodic search).

A budgeted core (default <=5K tokens, foreground-written, always-loaded in the
prefix) + an episodic tier of session notes indexed as section-level chunks with
headings and dates (research §6.2), not sentences. Tool memory_search = hybrid
BM25 + vector with a recency-decay term, deterministic tie-break by entry id.

Flag core_writer=foreground|background is the H7 ablation (A5-bg: the core is
written by the A4 extraction path instead of the working agent).
"""

from pathlib import Path

from .base import ContextParts, MemoryBackend, StoreSnapshot, ToolSpec, TurnInjection, WriteReport
from .embedders import HashingEmbedder
from .store_sqlite import EntryStore

CORE_BUDGET_TOKENS = 5000
RECENCY_DECAY = 0.01   # per session of age, subtracted from the fused score
FUSE_VEC, FUSE_BM25 = 0.5, 0.5


class HybridTieredBackend(MemoryBackend):
    arm_id = "a5"
    name = "hybrid_tiered"
    write_policy = "foreground"
    read_policy = "hybrid_search"
    inject = "prefix"
    core_writer = "foreground"

    def __init__(self, workdir, tokenizer, config=None):
        super().__init__(workdir, tokenizer, config)
        cfg = config or {}
        self.k = cfg.get("k", 5)
        self.core_budget = cfg.get("core_budget", CORE_BUDGET_TOKENS)
        self.embedder = cfg.get("embedder") or HashingEmbedder()
        self.ws = Path(workdir) / f"workspace_{self.arm_id}"
        self.notes = self.ws / "notes"
        if not self.ws.exists():
            self.notes.mkdir(parents=True)
            (self.ws / "CORE.md").write_text(
                "# CORE.md (budgeted always-loaded core)\n\n## Facts\n", encoding="utf-8")
        self.index = EntryStore(Path(workdir) / f"episodic_{self.arm_id}.sqlite")
        self.embedding_calls = 0
        self.retrieval_hits = 0
        self.last_retrieval_hits = 0
        self._writes = 0
        self._session_idx = 0

    # -- write path ---------------------------------------------------------------
    def _core_apply(self, event):
        core = self.ws / "CORE.md"
        text = core.read_text(encoding="utf-8")
        if event.kind == "correct_explicit" and event.supersedes:
            lines = text.split("\n")
            for i, line in enumerate(lines):
                if event.supersedes in line and line.strip().startswith("-"):
                    lines[i] = f"- {event.text}"
                    break
            else:
                lines.append(f"- {event.text}")
            text = "\n".join(lines)
        else:
            text += f"- {event.text}\n"
        core.write_text(text, encoding="utf-8")

    def _episodic_append(self, event, session_idx):
        note = self.notes / f"session-{session_idx:03d}.md"
        header = f"# Session {session_idx:03d} notes\n" if not note.exists() else ""
        section = f"\n## entry s{session_idx} {event.key} (session {session_idx})\n{event.text}\n"
        with open(note, "a", encoding="utf-8") as fh:
            fh.write(header + section)
        # index the section-level chunk with heading and date/session attached
        chunk = f"[session {session_idx}] {event.key}: {event.text}"
        self.index.add(event.key, chunk, session_idx, self.embedder.embed(chunk))
        self.embedding_calls += 1

    def scripted_apply(self, event, session_idx):
        self._session_idx = max(self._session_idx, session_idx)
        self._core_apply(event)
        self._episodic_append(event, session_idx)
        self._writes += 1

    def fill_distractors(self, distractor_sessions):
        """Distractors land in the episodic tier only; the core stays budgeted."""
        rows = []
        for d in distractor_sessions:
            note = self.notes / f"note-{d.id}.md"
            note.write_text(f"# {d.id}\n\n" + "\n".join(f"- {ln}" for ln in d.lines) + "\n",
                            encoding="utf-8")
            chunk = f"[{d.id}] " + " ".join(d.lines)
            rows.append((d.id, chunk, 0, self.embedder.embed(chunk)))
            self.embedding_calls += 1
        self.index.add_many(rows)

    # -- read path -----------------------------------------------------------------
    def bootstrap(self, session) -> ContextParts:
        core = (self.ws / "CORE.md").read_text(encoding="utf-8")
        return ContextParts(system_prefix=f"<core>\n{core}\n</core>")

    def tools(self):
        return [ToolSpec(name="memory_search",
                         description="hybrid BM25+vector search over episodic notes",
                         input_schema={"query": "string", "k": "int"})]

    def memory_search(self, query: str, k=None):
        """Hybrid: normalized vector + BM25 fusion - recency decay; ties by id."""
        k = k or self.k
        qv = self.embedder.embed(query)
        self.embedding_calls += 1
        vec_hits = {e["id"]: (s, e) for s, e in self.index.similar(qv, k * 4)}
        bm_hits = {e["id"]: (s, e) for s, e in self.index.bm25(query, k * 4)}
        max_bm = max((s for s, _ in bm_hits.values()), default=0.0) or 1.0
        fused = []
        for eid in sorted(set(vec_hits) | set(bm_hits)):
            vs = vec_hits.get(eid, (0.0, None))[0]
            bs = bm_hits.get(eid, (0.0, None))[0] / max_bm
            e = (vec_hits.get(eid) or bm_hits.get(eid))[1]
            age = max(0, self._session_idx - e["session"])
            score = FUSE_VEC * vs + FUSE_BM25 * bs - RECENCY_DECAY * age
            fused.append((-score, eid, e))
        fused.sort(key=lambda t: (t[0], t[1]))
        hits = [(-s, e) for s, eid, e in fused[:k]]
        self.last_retrieval_hits = len(hits)
        self.retrieval_hits += len(hits)
        return hits

    def on_session_end(self, transcript) -> WriteReport:
        n = self._writes
        self._writes = 0
        return WriteReport(entries_written=n, output_tokens=600 if n else 0)

    def core_tokens(self) -> int:
        return self.tok.count((self.ws / "CORE.md").read_text(encoding="utf-8"))

    def store_snapshot(self) -> StoreSnapshot:
        texts = {"CORE.md": (self.ws / "CORE.md").read_text(encoding="utf-8")}
        for p in sorted(self.notes.glob("*.md")):
            texts[f"notes/{p.name}"] = p.read_text(encoding="utf-8")
        total = sum(self.tok.count(t) for t in texts.values())
        return StoreSnapshot(kind="tiered", texts=texts, token_estimate=total)


class HybridTieredBgBackend(HybridTieredBackend):
    """A5-bg (should-ship): core written by the background extraction path (H7).

    The extraction path has no end-of-session curation: corrections ADD a new
    line instead of rewriting in place unless the extractor finds the exact
    superseded value (same rule as A4's UPDATE)."""

    arm_id = "a5bg"
    name = "hybrid_tiered_bg"
    write_policy = "background"
    core_writer = "background"

    def _core_apply(self, event):
        core = self.ws / "CORE.md"
        text = core.read_text(encoding="utf-8")
        if event.kind == "correct_explicit" and event.supersedes and event.supersedes in text:
            # background extractor UPDATE: same as A4's supersession rule
            lines = text.split("\n")
            for i, line in enumerate(lines):
                if event.supersedes in line and line.strip().startswith("-"):
                    lines[i] = f"- {event.text}"
                    break
            text = "\n".join(lines)
            core.write_text(text, encoding="utf-8")
        else:
            core.write_text(text + f"- {event.text}\n", encoding="utf-8")
