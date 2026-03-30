# Memory Agent Skill for Claude Code

This skill enables Claude Code to interact with your local persistent memory agent, providing cross-session continuity and knowledge persistence.

## What This Enables

With this skill active, Claude Code can:

✅ **Remember information across sessions** - Information stored today is available tomorrow
✅ **Query persistent knowledge** - Ask about topics from any previous conversation
✅ **Ingest documents automatically** - Upload files for semantic search later
✅ **Track processed files** - See what's been remembered and when
✅ **Consolidate insights** - Find patterns across accumulated knowledge

## Installation

### Prerequisites

1. **Memory agent must be running**
   ```bash
   cd ~/Desktop/ProtoGensis/memory-agent-bedrock
   ./scripts/run-with-watcher.sh
   ```

2. **Verify it's accessible**
   ```bash
   curl http://localhost:8000/status
   ```

3. **jq installed (recommended)**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install jq

   # macOS
   brew install jq
   ```

### Install the Skill

#### Option 1: Use the Install Script

```bash
cd ~/Desktop/ProtoGensis/memory-agent-bedrock/integrations/claude-code-skill
./install.sh
```

#### Option 2: Manual Installation

1. **Find your Claude Code skills directory:**
   - Check `~/.config/claude-code/skills/` (Linux)
   - Check `~/Library/Application Support/Claude Code/skills/` (macOS)
   - Or location specified in your Claude Code settings

2. **Copy the skill file:**
   ```bash
   cp memory.md <skills-directory>/memory.md
   ```

3. **Restart Claude Code or reload skills**

## Usage

Once installed, the skill activates automatically when relevant. You can also invoke it explicitly:

### Store Information

```
"Remember that the Q3 budget was approved at $2.4M"
```

Claude will automatically use the memory skill to store this.

### Query Knowledge

```
"What do you know about the Q3 budget?"
```

Claude will check both current context AND persistent memory.

### Upload Documents

```
"Analyze this research paper and remember the key points"
[Upload paper.pdf]
```

The skill ingests the file and extracts structured information.

### Check Status

```
"What files have you remembered?"
"Show me the memory system status"
```

Displays statistics and processed file list.

## How It Works

```
┌─────────────────┐
│   User Message  │
│   in Claude Code│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Memory Skill   │
│  (Auto-triggered│
│   or explicit)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Bash Tool      │
│  curl commands  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ localhost:8000  │
│  Memory Agent   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   memory.db     │
│   (SQLite)      │
└─────────────────┘
```

## Skill Triggers

The skill automatically activates when:

- User asks to "remember" something
- User asks "what do you know about..."
- User uploads a document worth storing
- User asks about memory system status
- Context suggests persistent storage would be helpful

## Best Practices

### When to Store

**Good candidates for storage:**
- Project decisions and rationale
- Configuration preferences
- Important meeting notes
- Research paper summaries
- Code architecture decisions
- User preferences and workflows

**Not worth storing:**
- Routine conversational exchanges
- Temporary calculations
- Already-documented information
- Overly generic statements

### Querying Strategy

1. **Let Claude decide** - The skill triggers proactively when appropriate
2. **Be specific** - "What did Alice say about the budget?" vs "Tell me about budgets"
3. **Trust citations** - Memory references like `[memory:abc123]` are traceable
4. **Combine sources** - Claude uses both memory AND current conversation

### File Management

- **Supported formats**: .txt, .md, .json, .csv, .log, .yaml, .yml, .png, .jpg, .jpeg, .gif, .webp, .pdf
- **File watching**: Drop files in `~/Desktop/ProtoGensis/memory-agent-bedrock/inbox/` for automatic ingestion
- **Change detection**: Files are re-ingested when modified (every 30 minutes by default)

## Examples

### Long-Running Project

**Session 1 (Monday):**
```
User: I'm starting a new project called "DataPipeline". It needs to handle 1M events/day.

Claude: [Stores project context automatically]
✓ Stored in persistent memory
```

**Session 2 (Wednesday):**
```
User: What were the requirements for DataPipeline?

Claude: [Checks memory automatically]
Based on previous discussion [memory:xyz], DataPipeline needs to handle 1M events/day...
```

### Research Workflow

```
User: Analyze these 3 papers and remember the key findings
[Uploads paper1.pdf, paper2.pdf, paper3.pdf]

Claude: [Ingests each file]
✓ File ingested: paper1.pdf (Summary: ...)
✓ File ingested: paper2.pdf (Summary: ...)
✓ File ingested: paper3.pdf (Summary: ...)

All papers are now stored. I can answer questions about them in any future session.

---

[Next week]

User: What did those LLM papers say about confidence calibration?

Claude: [Queries memory]
Based on the stored research [memory:abc, memory:def], the papers showed...
```

### Knowledge Accumulation

```
[Over several weeks, you've had multiple conversations about:
 - System architecture
 - Budget planning
 - Team decisions
 - Technical research]

User: What are the main themes in my work this quarter?

Claude: [Consolidation + memory query]
Based on your stored memories, three main themes emerge:

1. **Infrastructure Architecture** [memory:..., memory:...]
   Multiple discussions about scaling, database design, and microservices...

2. **Budget & Resources** [memory:..., memory:...]
   Q3 budget approval ($2.4M), headcount planning, vendor selection...

3. **AI/ML Research** [consolidation:...]
   Consistent focus on LLM capabilities, particularly confidence estimation...
```

## Troubleshooting

### Skill Doesn't Activate

**Check skill is installed:**
```bash
ls ~/.config/claude-code/skills/memory.md
# or your Claude Code skills directory
```

**Verify memory agent is running:**
```bash
curl http://localhost:8000/status
```

**Check Claude Code logs** for skill loading errors

### Connection Errors

**"Cannot connect to localhost:8000"**
```bash
# Check if server is running
ps aux | grep uvicorn | grep -v grep

# Start if not running
cd ~/Desktop/ProtoGensis/memory-agent-bedrock
./scripts/run-with-watcher.sh
```

### Incorrect or Stale Information

**File watcher runs every 30 minutes** by default. To force immediate update:
```bash
# Restart the memory agent (triggers startup consolidation)
cd ~/Desktop/ProtoGensis/memory-agent-bedrock
pkill -f "uvicorn api.main:app"
./scripts/run-with-watcher.sh
```

**Or manually trigger consolidation** in Claude Code:
```
"Trigger memory consolidation"
```

### Memory Seems Wrong

**Check when information was stored:**
```
"Show memory system status"
```

Look at the `last_processed` timestamps to verify freshness.

**Query with specificity:**
```
# Instead of: "What do you know about budgets?"
# Try: "What did Alice say about the Q3 budget in March?"
```

## Configuration

Modify behavior by editing:
`~/Desktop/ProtoGensis/memory-agent-bedrock/.env`

Key settings:
```bash
# Consolidation frequency
CONSOLIDATION_INTERVAL=300              # Check every 5 minutes
DAILY_CONSOLIDATION_INTERVAL=86400      # Force every 24 hours

# File watching
WATCH_DIR=./inbox                       # Auto-ingest directory
WATCH_POLL_INTERVAL=60                  # Check for new files every 1 minute
WATCH_CHANGE_DETECTION_INTERVAL=1800    # Check for changes every 30 minutes
WATCH_RECURSIVE=false                   # Scan subdirectories?

# Consolidation behavior
ENABLE_STARTUP_CONSOLIDATION=true       # Consolidate on startup
ENABLE_DAILY_CONSOLIDATION=true         # Force daily consolidation
MIN_MEMORIES_CONSOLIDATE=5              # Threshold for auto-consolidation
```

After changing `.env`, restart the memory agent.

## Limitations

- **Localhost only** - Memory agent must run on same machine as Claude Code
- **No authentication** - Assumes localhost is trusted environment
- **Storage limits** - Optimal for ~500-650 memories (scales beyond via consolidation)
- **AWS Bedrock required** - Memory agent uses Claude Haiku 4.5 on AWS
- **File size** - Large files (>10MB) may take longer to process

## Security & Privacy

✅ **All data local** - Stored in SQLite on your machine
✅ **No cloud sync** - Memory doesn't leave your system (unless you sync the DB)
✅ **User control** - You decide what gets stored
✅ **Transparent** - Status endpoint shows exactly what's been remembered
✅ **Deletable** - Can manually edit or delete `memory.db`

⚠️ **AWS API calls** - Memory agent calls Claude Haiku on Bedrock (your AWS account)
⚠️ **Localhost trust** - No authentication between Claude Code and memory agent

## Advanced Usage

### Direct API Access

You can also call the memory API directly in bash:

```bash
# Ingest
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"text":"your text","source":"manual"}'

# Query
curl "http://localhost:8000/query?q=your+question"

# Status
curl http://localhost:8000/status | jq .
```

### Programmatic Integration

The skill uses standard HTTP/REST, so you can integrate from any language:

```python
import requests

# Store information
response = requests.post('http://localhost:8000/ingest', json={
    'text': 'Information to remember',
    'source': 'my-script'
})

# Query
response = requests.get('http://localhost:8000/query', params={
    'q': 'what do you know?'
})
print(response.json()['answer'])
```

### Bulk Ingestion

```bash
# Ingest all markdown files in a directory
for file in ~/Documents/notes/*.md; do
    curl -X POST http://localhost:8000/ingest/file \
        -F "file=@$file"
    sleep 1  # Rate limiting
done
```

## Uninstallation

```bash
# Remove skill file
rm ~/.config/claude-code/skills/memory.md

# (Optional) Remove memory data
rm ~/Desktop/ProtoGensis/memory-agent-bedrock/memory.db

# (Optional) Stop memory agent
pkill -f "uvicorn api.main:app"
```

## Support

- **Memory Agent Issues**: See main [README.md](../../README.md)
- **Architecture Details**: See [BLOG.md](../../BLOG.md)
- **API Documentation**: See [API Reference](../../README.md#api-reference)
- **GitHub Issues**: [Report problems](https://github.com/your-repo/issues)

## What's Next

This skill provides the foundation for:
- **Cross-session project continuity**
- **Personal knowledge base** that grows with usage
- **Document semantic search** across all your files
- **Pattern recognition** via consolidation insights
- **Long-term memory** for AI assistants

The more you use it, the more valuable it becomes. The memory system learns and consolidates patterns over time, providing increasingly useful context.

---

**Version:** 1.0.0
**Last Updated:** 2026-03-30
**Requires:** Memory Agent v1.0.0, Claude Code, localhost:8000 accessible
