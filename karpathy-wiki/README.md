# karpathy-wiki

**LLM Knowledge Base CLI implementing Andrej Karpathy's compilation pattern**

A Python CLI tool that turns raw sources (PDFs, markdown, URLs, papers) into a structured, interlinked wiki maintained entirely by an LLM. No manual editing, no vector databases — just compilation, navigation, and continuous refinement.

## What This Is

In April 2025, Andrej Karpathy described his personal knowledge management workflow: an LLM-maintained wiki where raw materials flow into `raw/`, get compiled into structured `wiki/` articles, and continuously improve through Q&A feedback loops. He acknowledged his tooling was "a hacky collection of scripts" and suggested there was room for "an incredible new product."

**karpathy-wiki** is that product.

## Architecture

The system implements Karpathy's core principles:

### 1. **Two-Folder Structure**
- `raw/` — Inbox for unprocessed materials (PDFs, markdown, links, papers, code)
- `wiki/` — Structured, interlinked markdown articles maintained by LLM

### 2. **Plain-Text Index (No Vector DB)**
Unlike RAG systems that embed everything, karpathy-wiki maintains a plain-text `index.md` that the LLM reads and navigates. At query time:
- LLM reads the index
- Identifies relevant articles
- Follows `[[wikilinks]]` to navigate
- Synthesizes an answer

This is closer to how humans use a wiki. It scales to hundreds of articles without expensive embedding infrastructure.

### 3. **Compilation Engine**
Raw sources → structured knowledge:
- LLM reads raw material
- Extracts key concepts
- Creates focused wiki articles
- Generates `[[wikilinks]]` for cross-references
- Updates backlinks and index

### 4. **Q&A Feedback Loop**
Every question makes the system smarter:
- Ask a question
- LLM navigates wiki to answer
- Answer gets saved as a new wiki article
- Future queries benefit from accumulated Q&A

### 5. **Health Checks**
Periodic agent passes audit the wiki:
- Detect contradictions between articles
- Find coverage gaps
- Identify outdated claims
- Flag broken wikilinks
- Suggest articles to merge

### 6. **File Watcher**
Drop files into `raw/` and they're automatically ingested and compiled.

## Installation

### Prerequisites
- Python 3.9+
- AWS account with Bedrock access
- AWS credentials configured (`~/.aws/credentials` or environment variables)

### Install from Source

```bash
git clone https://github.com/yourusername/karpathy-wiki.git
cd karpathy-wiki
pip install -e .
```

### AWS Bedrock Setup

This tool uses Claude 3.5 Sonnet via AWS Bedrock. You need:

1. **Bedrock access** in `us-east-1` (or configure another region in `kb.toml`)
2. **Model access** to `anthropic.claude-3-5-sonnet-20241022-v2:0`
3. **AWS credentials** with `bedrock:InvokeModel` permission

Configure AWS credentials:
```bash
aws configure
# or set environment variables:
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

## Quick Start

### 1. Initialize a Knowledge Base

```bash
mkdir my-kb
cd my-kb
kw init
```

This creates:
```
my-kb/
├── raw/        # Inbox for sources
├── wiki/       # Compiled articles
├── kb.db       # SQLite metadata
└── kb.toml     # Configuration
```

### 2. Ingest Sources

```bash
# Add a PDF
kw ingest paper.pdf

# Add a URL
kw ingest https://arxiv.org/abs/2301.00001

# Add a markdown file
kw ingest notes.md
```

### 3. Compile into Wiki

```bash
# Compile one pending source
kw compile

# Compile all pending sources
kw compile --all
```

The LLM reads each source and creates structured wiki articles with:
- YAML frontmatter (title, tags, sources)
- Cross-referenced `[[wikilinks]]`
- "See Also" sections
- "Sources" sections

### 4. Query the Wiki

```bash
kw query "What is transformer architecture?"
```

The LLM:
1. Reads `wiki/index.md`
2. Navigates to relevant articles
3. Synthesizes an answer
4. Saves the Q&A as a new wiki article

### 5. Check Health

```bash
kw health
```

Runs an audit pass looking for contradictions, gaps, broken links, and outdated information.

### 6. Watch for New Files

```bash
kw watch
```

Automatically ingests and compiles files dropped into `raw/`.

## Commands Reference

### `kw init [PATH]`
Initialize a new knowledge base at PATH (default: current directory).

**Example:**
```bash
kw init ~/my-knowledge-base
```

### `kw ingest <FILE|URL>`
Add a file or URL to the raw/ inbox.

**Supported formats:**
- PDFs (`.pdf`)
- Markdown (`.md`, `.markdown`)
- Text files (`.txt`)
- URLs (http/https)
- GitHub URLs (special handling)

**Examples:**
```bash
kw ingest research-paper.pdf
kw ingest https://example.com/article
kw ingest https://github.com/user/repo
```

### `kw compile [OPTIONS]`
Compile raw sources into wiki articles.

**Options:**
- `--all` — Compile all pending sources
- `--id ID` — Compile specific source by ID

**Examples:**
```bash
kw compile              # Compile oldest pending
kw compile --all        # Compile everything
kw compile --id 5       # Compile source ID 5
```

### `kw query "QUESTION"`
Ask a question and navigate wiki for an answer.

**Options:**
- `--no-save` — Don't save answer as wiki article

**Examples:**
```bash
kw query "What is attention mechanism?"
kw query "Compare GPT-3 and GPT-4" --no-save
```

### `kw health`
Run health check to find quality issues.

Detects:
- Contradictions between articles
- Coverage gaps
- Broken wikilinks
- Outdated claims
- Redundant articles

**Example:**
```bash
kw health
# Generates report in wiki/reports/health-TIMESTAMP.md
```

### `kw watch`
Watch raw/ directory and auto-compile new files.

**Example:**
```bash
kw watch
# Drop files into raw/ and they'll be automatically processed
# Press Ctrl+C to stop
```

### `kw status`
Show knowledge base statistics.

**Example:**
```bash
kw status
# Shows: articles count, pending sources, total words, last compile time
```

### `kw list [OPTIONS]`
List wiki articles with summaries.

**Options:**
- `-n, --limit N` — Show N articles (default: 20)

**Example:**
```bash
kw list
kw list --limit 50
```

## Configuration

Edit `kb.toml` in your knowledge base root:

```toml
[llm]
model = "anthropic.claude-3-5-sonnet-20241022-v2:0"
region = "us-east-1"
max_tokens = 4096
temperature = 1.0

[paths]
raw = "raw"
wiki = "wiki"
db = "kb.db"

[compile]
auto_index_update = true
max_articles_per_source = 5
```

## How It Works vs RAG

Traditional RAG (Retrieval-Augmented Generation):
1. Embed all documents
2. Query → embed query
3. Vector similarity search
4. Feed top-K chunks to LLM

**karpathy-wiki (Compilation Pattern):**
1. LLM compiles sources into structured articles
2. Maintains plain-text index
3. Query → LLM reads index
4. LLM navigates relevant articles
5. LLM synthesizes answer

**Why compilation is better:**
- **Structure**: Raw text becomes organized knowledge
- **Navigation**: LLM follows cross-references like humans do
- **Accumulation**: Every query improves the wiki
- **Transparency**: All knowledge is readable markdown
- **No embeddings**: Simpler, no vector DB needed

The system works at ~100-500 article scale. For larger scale, you'd add smarter indexing (categories, search) but still avoid vector embeddings.

## Obsidian Compatibility

All wiki articles use:
- Standard markdown
- `[[wikilink]]` syntax for cross-references
- YAML frontmatter

You can open `wiki/` directly in Obsidian and get:
- Clickable wikilinks
- Graph view of connections
- Full-text search
- Tags

The wiki is both LLM-navigable and human-navigable.

## Feedback Loop in Action

Traditional RAG: Query → retrieve → answer → done.

**karpathy-wiki**: Query → navigate → answer → **save as article** → enrich wiki.

Example:
1. You ask: "What's the difference between BERT and GPT?"
2. LLM reads index, navigates to BERT and GPT articles
3. LLM synthesizes comparison
4. Comparison saved as new article: `comparison-bert-vs-gpt.md`
5. Future queries about "BERT vs GPT" find this article

The system learns from your questions.

## Development

### Run Tests

```bash
pytest tests/
```

All Bedrock calls are mocked for testing.

### Project Structure

```
karpathy-wiki/
├── kw/
│   ├── cli.py          # Typer CLI commands
│   ├── config.py       # Configuration management
│   ├── db.py           # SQLite operations
│   ├── llm.py          # AWS Bedrock integration
│   ├── ingestion.py    # File and URL processing
│   ├── compiler.py     # Compilation engine
│   ├── query.py        # Q&A navigation
│   ├── health.py       # Health check agent
│   └── watcher.py      # File watcher
├── tests/              # Pytest tests
├── README.md           # This file
├── BLOG.md             # Medium post about the project
└── pyproject.toml      # Python package config
```

## Limitations

- **Scale**: Works at ~100-500 articles. Beyond that, needs smarter indexing.
- **Cost**: Every compile/query calls Claude. Watch your AWS bill.
- **Accuracy**: LLM can make mistakes. Health checks help but aren't perfect.
- **Obsidian**: Only basic wikilink support. No fancy plugins.

## FAQ

**Q: Do I need to manually edit wiki articles?**
A: No. The LLM maintains everything. You only drop sources in `raw/`.

**Q: What if the LLM makes mistakes?**
A: Run `kw health` to detect issues. You can also manually edit articles if needed (they're just markdown).

**Q: Can I use a different LLM?**
A: Currently hardcoded to Bedrock. You could modify `kw/llm.py` to support other providers (OpenAI, Anthropic API, etc).

**Q: How much does this cost?**
A: Depends on usage. Compiling 10 PDFs might cost $1-5. Queries are cheaper. Monitor your Bedrock usage.

**Q: Why not use embeddings?**
A: Embeddings optimize for similarity search. This system optimizes for structure and navigation. Different goals.

**Q: Is this production-ready?**
A: It's a proof of concept. Use at your own risk. Good for personal knowledge bases. Not hardened for multi-user production.

## Acknowledgments

- **Andrej Karpathy** for describing the pattern in his April 2025 post
- **Anthropic** for Claude, which powers the compilation and navigation
- **AWS Bedrock** for providing model access

## License

MIT

## Contributing

This is a ProtoGen project — built to demonstrate the pattern. If you want to productionize it:
- Add better error handling
- Support more LLM providers
- Add authentication for multi-user
- Improve indexing for scale
- Add a web UI

Pull requests welcome.
