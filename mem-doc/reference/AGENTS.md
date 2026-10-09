# AGENTS.md — operating conventions (synthetic template)

This workspace is a hybrid-tiered memory template: a budgeted always-loaded
core (this file plus SOUL.md, USER.md, MEMORY.md), a one-level catalog of
deeper documents, and an episodic `notes/` tier meant to be indexed by search.

Conventions:

- Record only what the environment cannot reveal: decisions with rationale,
  preferences, failed approaches, external facts.
- Rewrite facts when the truth changes; don't append corrections below stale
  text.
- Keep the core under its token budget (default 5K). When it grows past budget,
  move the least-recently-relevant material into a cataloged doc or a note.
- Every catalog entry carries a `Read If` condition. One catalog level only:
  catalogs never point at other catalogs.
- End every session by appending a dated note to `notes/` and updating MEMORY.md
  if a durable fact changed.
