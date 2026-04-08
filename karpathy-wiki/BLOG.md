# I Built the Tool Karpathy Described

*Andrej Karpathy proposed a pattern for LLM-maintained knowledge bases. I was already running something like it. Then I built the standalone CLI he sketched out.*

---

**What this project is:** A Python CLI called `kw` that implements the "compilation over retrieval" pattern for personal knowledge bases. Drop sources into a folder, compile them into a structured wiki, query it.
**The problem it solves:** RAG systems retrieve but don't organize. The compilation pattern transforms raw material into a navigable, self-improving knowledge structure.
**What it uses:** Python with Typer, AWS Bedrock (Claude 3.5 Sonnet), SQLite for metadata, plain-text index instead of a vector database.
**What it doesn't do:** Scale to 10,000 documents. Handle multi-user. Replace careful reading of important sources.

---

## Where This Started

When Karpathy posted about his LLM knowledge base approach in April 2025, I had a specific reaction. Not "this is interesting" but "this is what DAEDALUS does."

DAEDALUS is the research and knowledge engine I run as part of CABAL, my autonomous agent system. It takes raw material, runs it through a compilation step, and produces structured wiki articles. It manages cross-references. It builds and maintains an index. It doesn't need me to write anything manually.

I built DAEDALUS because I had the same problem Karpathy described: too many research sources, no good way to synthesize them, and RAG felt like the wrong tool for the job. RAG retrieves chunks. I wanted something that *understood* the material and organized it.

So reading Karpathy's post, I recognized the architecture immediately. The two-folder structure, the compilation step, the LLM-maintained index, the feedback loop where answered questions become new articles. He had arrived at the same pattern.

The difference was tooling. DAEDALUS is tightly integrated into CABAL's infrastructure. Not something you can hand to someone else and say "here, run this." Karpathy mentioned his own tooling was "a hacky collection of scripts." He suggested someone would eventually build the clean standalone version.

I decided that someone should be me.

## What the Compilation Pattern Actually Is

Before getting into the code, it's worth being precise about what makes this different from RAG.

RAG (Retrieval-Augmented Generation) works like this: embed your documents, embed a query, find the chunks with the highest similarity score, feed those chunks to an LLM, get an answer. It's a search problem. You have stuff; you want to find the relevant parts.

The compilation pattern works differently. Instead of treating raw documents as something to retrieve, you transform them. The LLM reads a source and produces structured wiki articles with cross-references and frontmatter. Every source gets compiled into the same format. The index stays human-readable plain text. When you query, the LLM reads the index, navigates to the relevant articles, and synthesizes an answer from organized knowledge rather than raw chunks.

The key difference is when the synthesis happens. In RAG, you synthesize at query time, every time. In the compilation pattern, you synthesize at ingest time and accumulate the results. Future queries get the benefit of past synthesis.

There's a table comparison at the end of this post if you want the side-by-side. The short version: RAG scales better, compilation structures better. For personal knowledge bases at the 100-500 article range, the compilation pattern wins.

## What I Built

The tool is `kw` (short for karpathy-wiki, though using it feels slightly awkward given he didn't build it). It's a Python CLI using Typer, backed by AWS Bedrock for LLM calls and SQLite for metadata storage.

The directory structure after `kw init` looks like this:

```
my-kb/
├── raw/        # Inbox for source material
├── wiki/       # LLM-compiled articles
├── kb.db       # SQLite: sources, articles, health reports
└── kb.toml     # Configuration
```

That's the whole thing. No vector database. No embedding service. The `wiki/` folder is just markdown files.

### The Commands

```bash
kw init                    # Set up a new knowledge base
kw ingest paper.pdf        # Add source material (PDF, markdown, URL)
kw compile --all           # Compile pending sources into wiki articles
kw query "your question"   # Navigate wiki and synthesize an answer
kw health                  # Audit for contradictions, gaps, broken links
kw watch                   # File watcher: auto-ingest and compile
kw status                  # Stats: article count, pending sources, word count
kw list                    # List articles with summaries
```

The compilation step is where most of the work happens. When you run `kw compile`, it sends each unprocessed source to Claude 3.5 Sonnet via Bedrock with a prompt that asks for structured articles, YAML frontmatter, and `[[wikilinks]]` to related concepts. The output lands in `wiki/` as markdown files and the LLM updates `wiki/index.md` to include the new entries.

The index is the key design choice. Instead of vector embeddings, the query engine reads `wiki/index.md` first, identifies which articles are relevant, reads those articles, follows any wikilinks that matter, and synthesizes an answer. The LLM navigates like a human researcher would: index first, then articles.

### Health Checks

This feature came directly from production experience with DAEDALUS.

LLM-maintained content develops problems over time. Articles contradict each other when two sources make conflicting claims and the LLM compiled them independently. Wikilinks break when an article gets renamed or deleted. Concepts get mentioned across multiple articles without a dedicated home. Coverage gaps accumulate.

`kw health` runs an audit pass that looks for all of these. It produces a report in `wiki/reports/` with severity levels: high (contradictions, broken links), medium (coverage gaps), low (redundant articles, style inconsistencies). High-severity issues need manual review. Medium and low often resolve when you recompile.

Without health checks, the wiki would gradually degrade. With them, it stays coherent.

### Obsidian Compatibility

The articles use `[[wikilink]]` syntax and standard YAML frontmatter. This means you can open `wiki/` directly in Obsidian and get a fully navigable graph: clickable links, graph view, full-text search, tags. The wiki is both LLM-navigable and human-navigable.

This matters more than it might seem. Being able to browse the knowledge graph yourself, spot weird gaps, and occasionally edit articles manually makes the whole system more trustworthy. You're not operating blind.

## What I Learned Building It

Coming in with DAEDALUS experience, I thought the implementation would be straightforward. It mostly was, but a few things surprised me.

**Plain-text indexing actually works.** I kept waiting for this to break down. At 100-200 articles, the index fits comfortably in a prompt. Claude reads it, navigates it, and finds the relevant articles without any similarity search. The structure you built at compile time does real work at query time. My concern about scale was premature for the target use case.

**Wikilink quality is a tuning problem.** Early versions generated too many wikilinks. Every article linked to a dozen others, half of which didn't exist yet. This cluttered the health reports with broken link warnings and made the health checker noisy. The fix was prompt tuning: only create wikilinks for concepts with dedicated articles, not for every mentioned term. It took a few iterations to get right. The health checker is what told me there was a problem in the first place, which validated building it early.

**The feedback loop accumulates fast.** After a few weeks of use in testing, the wiki started noticeably improving at recurring questions. Articles that had been asked about became more complete. The comparison articles that `kw query` generates when you ask "what's the difference between X and Y" became a useful article type in their own right. The accumulation dynamic is real and it works.

**Multi-source compilation is the hard case.** Single-source compilation is clean: one paper, one or more articles, clear provenance. Multi-source gets complicated. If you ingest five papers on the same topic and compile them separately, you end up with five sets of articles that partially overlap. The health checker flags these as redundant, but the merge step requires judgment. The current tool doesn't auto-merge. That's a known limitation.

**Cost is not a surprise but it's real.** Every compile and query call hits Bedrock. Compiling ten PDFs runs roughly $2-5 depending on length. Queries are cheaper, maybe $0.05-0.10 each. For a personal tool used weekly, that's fine. If you're trying to compile a research library of hundreds of papers, you'll want to think about batching and prioritization.

## Where It Falls Short

Honest assessment, since this is a protoGen project and not a polished product:

The LLM makes mistakes. It misinterprets sources. It occasionally generates article splits that don't make sense. It creates wikilinks to articles it invented and then didn't create. The health checker catches a lot of this, but not everything. You need to review compilation output on sources that matter.

There's no incremental update path. If you ingest a new paper that's relevant to an existing article, the compiler creates a new article rather than updating the old one. A smarter system would detect overlap and offer to merge. The current approach leans on health checks and periodic manual cleanup instead.

The tool is hardcoded to AWS Bedrock. Supporting OpenAI or Anthropic's direct API or a local model would make this accessible to more people. The LLM layer is cleanly separated in `kw/llm.py`, so adding providers is straightforward. It just hasn't been done yet.

Scale tops out around 500 articles before the plain-text index starts getting unwieldy. The fix is hierarchical indexing: categories with sub-indexes, or a lightweight search layer. Still no need for embeddings, but it would require design work.

## The Comparison

| Aspect | RAG | karpathy-wiki |
|--------|-----|---------------|
| Setup | Embed documents, run vector DB | Drop sources in folder |
| Structure | Chunks of original text | Organized, interlinked articles |
| Navigation | Similarity search | LLM reads index, follows links |
| Accumulation | Static corpus | Every query can add articles |
| Transparency | Embeddings (opaque) | Readable markdown |
| Scale ceiling | 10K+ documents | ~100-500 articles |
| Cost model | One-time embedding cost | Per-operation LLM calls |

RAG is better for large static corpora where you need fast retrieval and don't care much about structure. The compilation pattern is better when you want an organized, accumulating knowledge base that you can actually browse.

## Try It

The tool is installable from source:

```bash
# Clone the repo (see README for current URL)
pip install -e .
```

You'll need AWS credentials with Bedrock access and model access to `anthropic.claude-3-5-sonnet-20241022-v2:0` in `us-east-1`. Once that's configured, `kw init` sets up a knowledge base and you're ready to go.

The codebase is roughly 2,800 lines across nine modules: `cli.py`, `compiler.py`, `config.py`, `db.py`, `health.py`, `ingestion.py`, `llm.py`, `query.py`, and `watcher.py`. Nothing exotic. If you want to adapt it to a different LLM provider or extend the compilation logic, the structure makes that reasonably easy.

This is a protoGen project, which means it's a working reference implementation, not production software. Use it as a starting point, not a finished product.

---

## Final Note on Attribution

The concept belongs to Karpathy. He described the pattern clearly and the name fits. I built an implementation because I wanted the CLI he sketched and I had prior art to validate the approach. DAEDALUS convinced me the pattern worked before I wrote a line of `kw` code.

If you want the conceptual argument for why compilation beats retrieval for personal knowledge bases, I wrote a separate post on that. This post is about the tool.

---

*Built during Protogenesis. Part of a series on patterns for AI-assisted knowledge management.*
