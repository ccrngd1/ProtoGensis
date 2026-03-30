# Memory Agent Skill for Kiro-CLI

This skill enables Kiro-CLI (legacy Claude Code CLI) to interact with your local persistent memory agent using explicit `/memory` commands.

> **Note:** If you're using the newer Claude Code, see [`../claude-code-skill/`](../claude-code-skill/) for the recommended integration with automatic activation.

## What This Provides

Command-based interface for Kiro-CLI users:

✅ **Explicit control** - You decide exactly what gets stored
✅ **Clear commands** - `/memory` prefix for all operations
✅ **Scriptable** - Easy to automate and batch
✅ **Predictable** - Clear cause and effect
✅ **Battle-tested** - Original integration design

## Installation

### Prerequisites

1. **Memory agent must be running**
   ```bash
   cd ~/Desktop/ProtoGensis/memory-agent-bedrock
   ./scripts/run-with-watcher.sh
   ```

2. **Verify accessibility**
   ```bash
   curl http://localhost:8000/status
   ```

### Install the Skill

1. **Find your Kiro-CLI skills directory:**
   ```bash
   # Common locations:
   # ~/.config/kiro-cli/skills/
   # ~/.kiro-cli/skills/
   ```

2. **Copy the skill file:**
   ```bash
   cp memory.md ~/.config/kiro-cli/skills/memory.md
   ```

3. **Restart Kiro-CLI**

## Usage

All operations use the `/memory` command prefix:

### Store Information

```bash
/memory ingest "Met with Alice today. Q3 budget approved at $2.4M"
```

**Output:**
```
✓ Stored memory [ID: abc123...]
Summary: Alice confirmed Q3 budget approval of $2.4M
Entities: Alice, Q3 budget
Topics: finance, meetings
Importance: 0.82
```

### Query Memory

```bash
/memory query "What did Alice say about the budget?"
```

**Output:**
```
Alice confirmed the Q3 budget is approved at $2.4M [memory:abc123].
```

### Upload Files

```bash
/memory ingest-file ~/Documents/meeting-notes.pdf
```

**Output:**
```
✓ File ingested: meeting-notes.pdf
Memory ID: xyz789...
Summary: Meeting notes covering budget discussion, project timeline, and action items
```

### Check Status

```bash
/memory status
```

**Output:**
```
Memory System Status:
- Total memories: 42
- Consolidations: 8
- Unconsolidated: 3
- Background consolidation: running
- Last consolidation: 2026-03-30T17:04:18

Processed Files: 12
- meeting-notes.md (last processed: 2026-03-30T15:30:22, memories: 3)
- research-paper.pdf (last processed: 2026-03-30T14:20:15, memories: 5)
[...]
```

### Trigger Consolidation

```bash
/memory consolidate
```

**Output:**
```
✓ Consolidation complete
Consolidation ID: def456...
Processed 7 memories
```

## Command Reference

| Command | Description | Example |
|---------|-------------|---------|
| `/memory ingest "<text>"` | Store text | `/memory ingest "Project deadline: April 15"` |
| `/memory ingest-file <path>` | Upload file | `/memory ingest-file ./report.pdf` |
| `/memory query "<question>"` | Ask question | `/memory query "When is the deadline?"` |
| `/memory status` | System info | `/memory status` |
| `/memory consolidate` | Force consolidation | `/memory consolidate` |

## Supported File Types

- **Text**: .txt, .md, .json, .csv, .log, .yaml, .yml
- **Images**: .png, .jpg, .jpeg, .gif, .webp (analyzed via Claude Haiku vision)
- **Documents**: .pdf (text extraction via PyPDF2)

## Example Workflows

### Research Workflow

```bash
# Ingest papers
/memory ingest-file ~/Papers/metacognition.pdf
/memory ingest-file ~/Papers/llm-scaling.pdf

# Add your notes
/memory ingest "Key insight: confidence signals could improve AI safety"

# Query synthesis
/memory query "How do the papers relate to AI safety?"

# Check what's processed
/memory status
```

### Project Tracking

```bash
# Store project info
/memory ingest "DataPipeline project: handle 1M events/day, Q3 delivery, team of 5"

# Later, recall details
/memory query "What are the DataPipeline requirements?"
/memory query "When is DataPipeline due?"
/memory query "How many people on DataPipeline?"
```

### Meeting Notes

```bash
# Before meeting - recall context
/memory query "What did we discuss with Alice last time?"

# After meeting - store notes
/memory ingest "Meeting with Alice - March 30:
- Q3 budget approved: $2.4M
- Hiring: 3 positions approved
- Next steps: Infrastructure proposal by April 5
- Follow-up: April 7"

# Later - specific recall
/memory query "When is the follow-up with Alice?"
```

## Scripting & Automation

The `/memory` commands work great in scripts:

```bash
#!/bin/bash
# bulk-ingest.sh - Ingest all markdown files

for file in ~/Documents/notes/*.md; do
    echo "Processing: $file"
    /memory ingest-file "$file"
    sleep 1  # Rate limiting
done

/memory status
/memory consolidate
```

## Detailed Examples

See [`EXAMPLE_USAGE.md`](EXAMPLE_USAGE.md) for comprehensive usage examples including:
- Basic operations
- Complex queries
- Workflow patterns
- Integration with regular conversation
- Tips for effective usage

## Testing

Run the test suite to verify everything works:

```bash
./test-skill.sh
```

This tests all 5 operations against your running memory agent.

## Architecture

```
Kiro-CLI User
      ↓
"/memory <command>"
      ↓
Skill parses command
      ↓
Bash tool (curl)
      ↓
localhost:8000 (Memory Agent API)
      ↓
memory.db (SQLite)
```

## Comparison with Claude Code Skill

| Feature | Kiro-CLI | Claude Code |
|---------|----------|-------------|
| Activation | Manual commands | Automatic + manual |
| Syntax | `/memory <cmd>` | Natural conversation |
| Control | Explicit | Claude decides |
| Best for | Scripting, power users | Daily conversation |

See [`../COMPARISON.md`](../COMPARISON.md) for detailed comparison.

## Troubleshooting

### "Command not found: /memory"

**Check skill is installed:**
```bash
ls ~/.config/kiro-cli/skills/memory.md
```

**Verify location:**
Different systems use different paths. Check your Kiro-CLI config.

### "Cannot connect to memory agent"

**Check if running:**
```bash
curl http://localhost:8000/status
```

**Start if needed:**
```bash
cd ~/Desktop/ProtoGensis/memory-agent-bedrock
./scripts/run-with-watcher.sh
```

### "File upload failed"

**Verify file exists:**
```bash
ls -la /path/to/file
```

**Check file type:**
Only supported extensions work (see list above)

**Check file size:**
Very large files (>10MB) may timeout

### "Incorrect or stale information"

**File watcher runs every 30 minutes** by default for change detection.

**Force update:**
```bash
# Restart memory agent (triggers startup consolidation)
cd ~/Desktop/ProtoGensis/memory-agent-bedrock
pkill -f "uvicorn api.main:app"
./scripts/run-with-watcher.sh
```

**Or manually consolidate:**
```bash
/memory consolidate
```

## Configuration

Modify memory agent behavior in:
`~/Desktop/ProtoGensis/memory-agent-bedrock/.env`

Relevant settings:
```bash
# How often to check for consolidation
CONSOLIDATION_INTERVAL=300

# Minimum memories to trigger consolidation
MIN_MEMORIES_CONSOLIDATE=5

# Force consolidation daily
DAILY_CONSOLIDATION_INTERVAL=86400

# File watching
WATCH_DIR=./inbox
WATCH_POLL_INTERVAL=60
```

After changing `.env`, restart the memory agent.

## API Reference

Behind the scenes, the skill uses these API endpoints:

**Ingest text:**
```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"text":"...","source":"kiro-cli"}'
```

**Ingest file:**
```bash
curl -X POST http://localhost:8000/ingest/file \
  -F "file=@/path/to/file"
```

**Query:**
```bash
curl "http://localhost:8000/query?q=<encoded_question>"
```

**Status:**
```bash
curl http://localhost:8000/status
```

**Consolidate:**
```bash
curl -X POST http://localhost:8000/consolidate
```

## Limitations

- **Manual invocation only** - No automatic activation
- **Localhost only** - Memory agent must run on same machine
- **No authentication** - Trusts localhost environment
- **Storage limits** - Optimal for ~500-650 memories (scales via consolidation)
- **AWS Bedrock required** - Memory agent uses Claude Haiku 4.5

## Migration to Claude Code

If you're moving from Kiro-CLI to Claude Code:

1. **Install Claude Code skill:**
   ```bash
   cd ../claude-code-skill
   ./install.sh
   ```

2. **Keep using Kiro-CLI commands if you want:**
   Both skills work with the same memory agent!

3. **Benefits of Claude Code skill:**
   - Automatic activation
   - Natural conversation
   - Proactive suggestions
   - No commands to remember

## Advanced Usage

### Batch Operations

```bash
# Ingest multiple files
for file in documents/*.pdf; do
    /memory ingest-file "$file"
done

# Force consolidation after batch
/memory consolidate
```

### Filtered Queries

```bash
# Time-based
/memory query "What did I work on last week?"

# Person-based
/memory query "All discussions with Alice"

# Topic-based
/memory query "Find all budget-related information"
```

### Status Monitoring

```bash
# Watch consolidation progress
watch -n 60 '/memory status'

# Check periodically in scripts
if /memory status | grep -q "unconsolidated: 0"; then
    echo "All memories consolidated"
fi
```

## Support

- **Memory Agent Issues**: See main [../../README.md](../../README.md)
- **Architecture Details**: See [../../BLOG.md](../../BLOG.md)
- **API Documentation**: [API Reference](../../README.md#api-reference)
- **Skill Comparison**: [../COMPARISON.md](../COMPARISON.md)

## Files in This Directory

- `memory.md` - The skill definition file (install this)
- `README.md` - This documentation
- `EXAMPLE_USAGE.md` - Comprehensive usage examples
- `test-skill.sh` - Automated test suite

---

**Version:** 1.0.0
**Status:** Stable (legacy)
**Recommended for:** Kiro-CLI users, scripting, explicit control
**Alternative:** Claude Code skill for automatic activation
