# A1 doc-full write prompt (end of session; transcript still in context)

You maintain this workspace's Markdown documents (AGENTS.md, MEMORY.md, topic
files). The whole workspace is always loaded at session start. Before the
session ends, update the documents with what this session established, using the
`str_replace` and `write_file` tools.

Conventions (CABAL-style AGENTS.md conventions, synthetic workspace):

- Record only what the task environment cannot reveal: decisions **with their
  rationale**, preferences, failed approaches and why they failed, external
  facts, codes and identifiers you were given.
- **Rewrite facts when the truth changes; don't append.** If a line in
  MEMORY.md is now wrong, replace that line in place with the current truth.
  Never leave a superseded value standing next to its correction.
- One fact per line under the `## Facts` heading in MEMORY.md.
- Keep MEMORY.md curated. Long narratives go to topic files; MEMORY.md keeps the
  distilled line.
- Do not restate what `ls` or `grep` on the environment would reveal.
