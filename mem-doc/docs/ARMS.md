# Arms (research §6.1)

Generated layout from `memdoc arms list --format md`:

| id | name | write policy | read policy | inject |
|---|---|---|---|---|
| a0 | none | none | none | none |
| astar | oracle | n/a | oracle | prefix |
| a1 | doc_full | foreground | always_load | prefix |
| a2 | doc_catalog | foreground | catalog | prefix |
| a3 | rag_naive (weak baseline) | background | similarity | tail |
| a4 | rag_extract | background | similarity | tail |
| a5 | hybrid_tiered | foreground | hybrid_search | prefix |
| a5bg | hybrid_tiered_bg | background | hybrid_search | prefix |
| a6 | transcript_grep | none | agent_search | none |

Factor coverage:

- **Write policy:** A1/A2/A5 (foreground) vs A3/A4/A5-bg (background) vs A6/A0 (none).
- **Read policy:** A1 (always-load) vs A2 (catalog) vs A3/A4 (similarity) vs A5
  (hybrid search over an episodic tier) vs A6 (agent search).
- **A5** combines a budgeted foreground core with hybrid episodic search —
  the layout a tiered production system actually runs.
- **A3** is A4 with `extract=False`: raw chunks, top-5 at tail, no search tool.
  It is the brief's original design, kept as a labeled **weak baseline** (Trap 8).
- **A5-bg** is A5 with `core_writer=background`: the H7 ablation.

Arm prompts live in `prompts/`:

- `prompts/doc_full_write.md` — A1's end-of-session write prompt (CABAL-style
  AGENTS.md conventions; synthetic workspace).
- `prompts/doc_catalog_guidance.md` — A2's guidance, adapted from Operator
  Memory (BSD-3, attributed; see `THIRD_PARTY_NOTICES.md`).
- `prompts/rag_extract.md` — A4's Mem0-style extraction prompt (ADD/UPDATE/
  DELETE/NOOP with supersession).
- `prompts/hybrid_tiered.md` — A5's core/notes/search prompts and the A5-bg
  ablation note.
