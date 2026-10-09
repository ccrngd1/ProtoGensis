"""A2 doc-catalog: foreground writes, Operator-style catalog + on-demand reads.

Prefix = Operator guidance text (adapted, BSD-3, attributed; see
prompts/doc_catalog_guidance.md) + catalog.md (entries: path, covers, read_if),
one level only (2607.17598). Tool read_doc(path). Foreground writes must also
update the catalog entry.
"""

from pathlib import Path

from .base import ContextParts, MemoryBackend, StoreSnapshot, ToolSpec, WriteReport

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def _guidance() -> str:
    p = PROMPTS_DIR / "doc_catalog_guidance.md"
    return p.read_text(encoding="utf-8")


class DocCatalogBackend(MemoryBackend):
    arm_id = "a2"
    name = "doc_catalog"
    write_policy = "foreground"
    read_policy = "catalog"
    inject = "prefix"

    def __init__(self, workdir, tokenizer, config=None):
        super().__init__(workdir, tokenizer, config)
        self.ws = Path(workdir) / "workspace_a2"
        self.docs = self.ws / "docs"
        if not self.ws.exists():
            self.docs.mkdir(parents=True)
            (self.ws / "catalog.md").write_text(
                "# Partition Catalog\n\n## Tree\n", encoding="utf-8")
        self._opened_docs = 0
        self._writes = 0

    # -- catalog helpers --------------------------------------------------------
    def _catalog_path(self):
        return self.ws / "catalog.md"

    def _append_catalog_entry(self, relpath: str, covers: str, read_if: str):
        cat = self._catalog_path()
        text = cat.read_text(encoding="utf-8")
        entry = (f"- `{relpath}`\n  - Description: {covers}\n  - Read If: {read_if}\n")
        if f"- `{relpath}`" not in text:
            cat.write_text(text + entry, encoding="utf-8")

    # -- scripted write API -------------------------------------------------------
    def scripted_apply(self, event, session_idx):
        """One topic doc per fact key; corrections rewrite the line in place.
        The catalog entry's read_if carries the fact's own content keywords (the
        writer knew the topic); unknown-unknown probes share none of them."""
        relpath = f"docs/{event.key}.md"
        p = self.ws / relpath
        if event.kind == "correct_explicit" and event.supersedes and p.exists():
            lines = p.read_text(encoding="utf-8").split("\n")
            for i, line in enumerate(lines):
                if event.supersedes in line:
                    lines[i] = f"- {event.text}"
                    break
            else:
                lines.append(f"- {event.text}")
            p.write_text("\n".join(lines), encoding="utf-8")
        else:
            header = f"# {event.key}\n\n" if not p.exists() else ""
            with open(p, "a", encoding="utf-8") as fh:
                if header:
                    fh.write(header)
                fh.write(f"- {event.text}\n")
        covers = " ".join(sorted(self._keywords(event.text))[:6])
        self._append_catalog_entry(relpath, f"facts about {covers}",
                                   f"working on {covers}")
        self._writes += 1

    @staticmethod
    def _keywords(text):
        from ..text import content_keywords
        from ..text import CANARY_PATTERNS
        kws = content_keywords(text)
        # canary values never belong in the catalog (they'd leak into the prefix)
        for pat in CANARY_PATTERNS.values():
            kws -= set(x.lower() for x in pat.findall(text))
        return kws

    def fill_distractors(self, distractor_sessions):
        for d in distractor_sessions:
            relpath = f"docs/notes-{d.id}.md"
            (self.ws / relpath).write_text(
                f"# notes {d.id}\n\n" + "\n".join(f"- {ln}" for ln in d.lines) + "\n",
                encoding="utf-8")
            self._append_catalog_entry(relpath, f"routine upkeep session {d.id}",
                                       f"reviewing upkeep batch {d.id}")

    # -- read path -----------------------------------------------------------------
    def bootstrap(self, session) -> ContextParts:
        prefix = (_guidance() + "\n\n" +
                  self._catalog_path().read_text(encoding="utf-8"))
        return ContextParts(system_prefix=prefix)

    def tools(self):
        return [ToolSpec(name="read_doc", description="read a cataloged document",
                         input_schema={"path": "string"})]

    def read_doc(self, relpath: str) -> str:
        p = self.ws / relpath
        if not p.exists():
            return ""
        self._opened_docs += 1
        return p.read_text(encoding="utf-8")

    def catalog_entries(self):
        """[(path, read_if)] parsed from catalog.md, for the mock tool policy."""
        out = []
        path, read_if = None, ""
        for line in self._catalog_path().read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("- `"):
                path = s[3:s.index("`", 3)]
            elif s.startswith("- Read If:") and path:
                out.append((path, s[len("- Read If:"):].strip()))
                path = None
        return out

    def on_session_end(self, transcript) -> WriteReport:
        n = self._writes
        self._writes = 0
        return WriteReport(entries_written=n, output_tokens=600 if n else 0)

    def store_snapshot(self) -> StoreSnapshot:
        texts = {"catalog.md": self._catalog_path().read_text(encoding="utf-8")}
        for p in sorted(self.docs.glob("*.md")):
            texts[f"docs/{p.name}"] = p.read_text(encoding="utf-8")
        total = sum(self.tok.count(t) for t in texts.values())
        return StoreSnapshot(kind="docs", texts=texts, token_estimate=total)
