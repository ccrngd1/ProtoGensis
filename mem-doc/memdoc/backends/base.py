"""MemoryBackend interface (AC #1).

Every arm declares `arm_id`, `name`, `write_policy`, `read_policy`, and `inject`
(prefix | tail | head | none). `memdoc arms list` renders the research §6.1
table from these declared attributes, never hand-written.

Write phase and probe phase use the same backend instance and persisted store.
"""

from dataclasses import dataclass, field


@dataclass
class ContextParts:
    """What the backend contributes to a fresh session's context."""
    system_prefix: str = ""     # before the cachePoint
    head_inject: str = ""       # changes per turn; busts history cache (A4 inject=head)
    tail_inject: str = ""       # appended after the latest user message


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict = field(default_factory=dict)


@dataclass
class TurnInjection:
    head: str = ""
    tail: str = ""
    extraction_calls: int = 0   # model calls the backend spent this turn (A4)
    embedding_calls: int = 0
    retrieval_hits: int = 0


@dataclass
class WriteReport:
    entries_written: int = 0
    entries_updated: int = 0
    entries_deleted: int = 0
    extraction_calls: int = 0
    embedding_calls: int = 0
    output_tokens: int = 0      # write-path output tokens (doc edits, extraction)
    input_tokens: int = 0       # write-path uncached input tokens (extraction prompts)


@dataclass
class StoreSnapshot:
    """Persisted memory state, for write-fidelity checks and size measurement."""
    kind: str                   # docs | entries | transcripts | tiered
    texts: dict = field(default_factory=dict)   # name -> full text
    token_estimate: int = 0


class MemoryBackend:
    """Base class. Arms override the hooks they use."""

    arm_id = ""
    name = ""
    write_policy = ""           # foreground | background | none | n/a
    read_policy = ""            # none | oracle | always_load | catalog | similarity | hybrid_search | agent_search
    inject = "none"             # prefix | tail | head | none

    def __init__(self, workdir, tokenizer, config=None):
        self.workdir = workdir
        self.tok = tokenizer
        self.config = config or {}

    # -- read path -----------------------------------------------------------
    def bootstrap(self, session) -> ContextParts:
        return ContextParts()

    def tools(self) -> list:
        return []

    def on_turn(self, turn) -> TurnInjection:
        return TurnInjection()

    # -- write path ----------------------------------------------------------
    def on_session_end(self, transcript) -> WriteReport:
        return WriteReport()

    # -- introspection -------------------------------------------------------
    def store_snapshot(self) -> StoreSnapshot:
        return StoreSnapshot(kind="none")

    def store_tokens(self) -> int:
        return self.store_snapshot().token_estimate


def arms_table(classes) -> list[dict]:
    """The research §6.1 write-policy / read-policy table, generated from the
    declared attributes (AC #1)."""
    rows = []
    for cls in classes:
        rows.append({
            "id": cls.arm_id,
            "name": cls.name,
            "write_policy": cls.write_policy,
            "read_policy": cls.read_policy,
            "inject": cls.inject,
        })
    return rows
