# karpathy-wiki BLOG.md — Review by Main

**Date:** 2026-04-08
**Verdict:** FAIL — Requires full rewrite (voice/attribution)
**Severity:** Critical

## Issue

The blog post is written in Andrej Karpathy's voice and signed "*Andrej Karpathy, April 2025*". This is a fundamental attribution problem:

1. **The post reads as if Karpathy wrote it.** First person throughout: "I've been thinking about...", "I decided to actually build the tool", "After using it for a few weeks..."
2. **It's signed by Karpathy.** The byline at the bottom says "Andrej Karpathy, April 2025."
3. **The "Update" section blurs real vs fictional.** It implies Karpathy built the tool, when CC's team built it as a protoGen project.

This cannot be published in any form. It would be plagiarism/impersonation.

## Required Rewrite

The blog needs to be rewritten entirely in CC's voice:

- **CC's framing:** "Karpathy proposed the compilation-over-retrieval concept. I agreed with the thesis and built a tool that implements it."
- **CC's experience:** Reference CABAL's existing compilation patterns (DAEDALUS pipeline, memory consolidation, wiki publishing) as prior art that validates the concept.
- **CC's build:** The tool should be presented as CC's implementation, inspired by Karpathy's idea, with CC's own learnings and production experience.
- **CC's honest assessment:** Where the tool works, where it doesn't, what surprised him. Real builder voice, not Karpathy cosplay.

## What's Salvageable

- The architecture section (two-folder structure, compilation workflow, health checks) is solid technically
- The comparison table (RAG vs Compilation) is useful
- The cost analysis is concrete
- The limitations section is honest

All of this content can be restructured into CC's voice.

## Recommendation

Send to DAEDALUS for full rewrite with explicit voice instructions. The technical content is good — the framing is the problem.
