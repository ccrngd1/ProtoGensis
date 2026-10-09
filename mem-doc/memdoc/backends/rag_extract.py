"""A4 rag-extract: background LLM extraction with supersession; top-5 at tail.

After each user turn an extraction call (a separate, costed model call;
Mem0-style prompt in prompts/rag_extract.md) proposes ADD/UPDATE/DELETE/NOOP
against the top-k most similar existing entries. Entries carry session
timestamps. Top-5 entries inject at the tail of the latest user message
(inject=tail; inject=head exists for `demo cache`). Tool memory_search(query, k).

A3 rag-naive is the extract=False flag: raw turn chunks embedded, top-5 at tail,
no search tool. Labeled "weak baseline" wherever it appears.

In mock mode the ScriptedWriter stands in for the extraction model: it applies
the same ADD/UPDATE decisions the prompt asks for, and the runner charges one
extraction call per write event (research §5.3 #4).
"""

from pathlib import Path

from .base import ContextParts, MemoryBackend, StoreSnapshot, ToolSpec, TurnInjection, WriteReport
from .embedders import HashingEmbedder
from .store_sqlite import EntryStore


class RagExtractBackend(MemoryBackend):
    arm_id = "a4"
    name = "rag_extract"
    write_policy = "background"
    read_policy = "similarity"
    inject = "tail"
    extract = True

    def __init__(self, workdir, tokenizer, config=None):
        super().__init__(workdir, tokenizer, config)
        cfg = config or {}
        self.k = cfg.get("k", 5)
        self.inject = cfg.get("inject", type(self).inject)
        self.embedder = cfg.get("embedder") or HashingEmbedder()
        self.store = EntryStore(Path(workdir) / f"store_{self.arm_id}.sqlite")
        self.embedding_calls = 0
        self.extraction_calls = 0
        self.retrieval_hits = 0
        self.last_retrieval_hits = 0

    # -- write path -------------------------------------------------------------
    def scripted_apply(self, event, session_idx):
        """Mem0-style ADD/UPDATE with supersession; one costed extraction call."""
        self.extraction_calls += 1
        vec = self.embedder.embed(event.text)
        self.embedding_calls += 1
        if self.extract and event.kind == "correct_explicit" and event.supersedes:
            for e in self.store.all_entries():
                if event.supersedes in e["text"]:
                    self.store.update(e["id"], event.text, session_idx, vec)
                    return
        self.store.add(event.key, event.text, session_idx, vec)

    def fill_distractors(self, distractor_sessions):
        rows = []
        for d in distractor_sessions:
            for line in d.lines:
                rows.append((d.id, line, 0, self.embedder.embed(line)))
                self.embedding_calls += 1
        self.store.add_many(rows)

    # -- read path ----------------------------------------------------------------
    def bootstrap(self, session) -> ContextParts:
        return ContextParts()

    def tools(self):
        if not self.extract:
            return []  # A3: no search tool
        return [ToolSpec(name="memory_search", description="search memory entries",
                         input_schema={"query": "string", "k": "int"})]

    def memory_search(self, query: str, k=None):
        qv = self.embedder.embed(query)
        self.embedding_calls += 1
        hits = self.store.similar(qv, k or self.k)
        self.last_retrieval_hits = len(hits)
        self.retrieval_hits += len(hits)
        return hits

    def on_turn(self, turn) -> TurnInjection:
        """Top-k most similar entries to the turn text, injected tail (or head)."""
        qv = self.embedder.embed(getattr(turn, "text", str(turn)))
        self.embedding_calls += 1
        hits = self.store.similar(qv, self.k)
        self.last_retrieval_hits = len(hits)
        self.retrieval_hits += len(hits)
        snippet = "\n".join(f"[memory] {e['text']}" for _, e in hits)
        if self.inject == "head":
            return TurnInjection(head=snippet, embedding_calls=1, retrieval_hits=len(hits))
        return TurnInjection(tail=snippet, embedding_calls=1, retrieval_hits=len(hits))

    def on_session_end(self, transcript) -> WriteReport:
        n = self.extraction_calls
        self.extraction_calls = 0
        # extraction calls are model calls and are costed: ~2.5K in / 200 out each
        return WriteReport(entries_written=self.store.count(), extraction_calls=n,
                           input_tokens=2500 * n, output_tokens=200 * n)

    def store_snapshot(self) -> StoreSnapshot:
        entries = self.store.all_entries()
        text = "\n".join(e["text"] for e in entries)
        return StoreSnapshot(kind="entries", texts={"entries": text},
                             token_estimate=self.tok.count(text))


class RagNaiveBackend(RagExtractBackend):
    """A3 (should-ship): A4 with extract=False. The brief's original design,
    kept as a labeled weak baseline."""

    arm_id = "a3"
    name = "rag_naive"
    write_policy = "background"
    read_policy = "similarity"
    inject = "tail"
    extract = False

    def scripted_apply(self, event, session_idx):
        # raw turn chunks embedded; no extraction LLM, no supersession
        vec = self.embedder.embed(event.text)
        self.embedding_calls += 1
        self.store.add(event.key, event.text, session_idx, vec)

    def on_session_end(self, transcript) -> WriteReport:
        return WriteReport(entries_written=self.store.count())
