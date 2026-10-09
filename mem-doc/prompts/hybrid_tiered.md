# A5 hybrid-tiered prompts (budgeted core + episodic notes + hybrid search)

## Core write (foreground; end of session, transcript still in context)

You maintain a budgeted always-loaded core document (CORE.md, <= 5K tokens).
Keep only the facts every future session needs: current decisions with
rationale, standing preferences, active codes. Rewrite lines in place when the
truth changes. When the core nears its budget, move the least-recently-relevant
lines into today's daily note.

## Episodic note write (end of session)

Append a dated section to today's note (`notes/YYYY-sessionNNN.md`) with what
happened: facts introduced, corrections, lessons. Keep headings and dates: the
episodic index chunks by section, with heading and date attached.

## Search tool

`memory_search(query, k)` runs hybrid BM25 + vector retrieval over episodic
note sections (section-level chunks with headings and dates, not sentences),
with a recency-decay term and deterministic tie-breaks. Cite the section date
when you use a result; prefer the most recent section when two conflict.

## A5-bg ablation (core_writer=background)

The core is written by the A4 extraction path instead of the working agent:
extraction decisions ADD/UPDATE lines in CORE.md with no end-of-session
curation pass. This is the H7 ablation; everything else is identical.
