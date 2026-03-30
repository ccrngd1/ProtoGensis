---
name: memory
description: Interact with the local persistent memory agent (ingest, query, status)
triggers:
  - User asks to remember something
  - User asks what you know about a topic
  - User asks to check memory status
  - User asks to store information persistently
  - User uploads a file and wants it remembered
  - User asks about previously discussed topics
---

# Memory Agent Skill

This skill connects Claude Code to a persistent memory system running locally on `localhost:8000`.

## When to Use This Skill

Use this skill proactively when:
- User asks you to "remember" or "store" information
- User asks "what do you know about X?" and persistent memory would be helpful
- User wants to recall information from previous sessions
- User uploads files that should be stored long-term
- User asks about memory system status
- Natural conversation suggests persistent context would help

## Available Operations

### 1. Ingest Text
Store user-provided information in persistent memory.

**When:** User asks to remember something or shares important information worth storing.

**How:** Use Bash tool with curl:
```bash
curl -s -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"text":"<TEXT_TO_STORE>","source":"claude-code"}' | jq .
```

**Output:** Display the summary, entities, topics, and importance score in a friendly format.

### 2. Ingest File
Upload a file (text, image, or PDF) for automatic extraction and storage.

**When:** User provides a file path and wants its contents stored in memory.

**How:** Use Bash tool with curl:
```bash
curl -s -X POST http://localhost:8000/ingest/file \
  -F "file=@<FILE_PATH>" | jq .
```

**Supported formats:** .txt, .md, .json, .csv, .log, .yaml, .yml, .png, .jpg, .jpeg, .gif, .webp, .pdf

**Output:** Show filename, summary, and number of memories created.

### 3. Query Memory
Ask questions about stored information across all sessions.

**When:**
- User asks about topics that might be in memory
- You need context from previous conversations
- User wants to recall specific information

**How:** Use Bash tool with curl (URL-encode the question):
```bash
QUESTION="<USER_QUESTION>"
ENCODED=$(echo "$QUESTION" | jq -sRr @uri)
curl -s "http://localhost:8000/query?q=$ENCODED" | jq -r '.answer'
```

**Output:** Display the answer directly, preserving all formatting and memory citations like `[memory:id]`.

### 4. Check Status
View memory system statistics and processed files.

**When:**
- User asks about memory system status
- You want to show what's been stored
- Debugging or verification needed

**How:** Use Bash tool with curl:
```bash
curl -s http://localhost:8000/status | jq .
```

**Output:** Format in a readable way:
- Total memories and consolidations
- Unconsolidated count
- Background consolidation status
- Last consolidation time
- List of processed files with timestamps

### 5. Trigger Consolidation
Manually force the consolidation process to find patterns and generate insights.

**When:** User explicitly asks, or after ingesting multiple related items.

**How:** Use Bash tool with curl:
```bash
curl -s -X POST http://localhost:8000/consolidate | jq .
```

**Output:** Show whether consolidation ran successfully or was skipped (with reason).

## Error Handling

If the API is unreachable:
1. Check if server is running: `curl -s http://localhost:8000/status`
2. If not running, inform user and suggest:
   ```bash
   cd ~/Desktop/ProtoGensis/memory-agent-bedrock
   ./scripts/run-with-watcher.sh
   ```
3. Do not repeatedly retry failed connections

If API returns an error:
- Display the error message clearly
- Suggest relevant troubleshooting steps
- Do not expose raw stack traces to user

## Best Practices

### When to Store Information

**DO store:**
- User explicitly asks to remember something
- Important facts, decisions, or action items mentioned
- Key insights from uploaded documents
- Configuration preferences user wants to persist
- Project context that spans multiple sessions

**DON'T store:**
- Routine conversational exchanges
- Temporary working data
- Information already in the current conversation context
- Overly generic statements without specific context

### Proactive Usage

Be proactive but not intrusive:
- ✅ "I can store this in persistent memory for future reference. Would you like me to?"
- ✅ After helping with a complex task: "Should I remember the key decisions we made?"
- ✅ When user mentions forgetting something: Check memory first
- ❌ Don't store every message automatically
- ❌ Don't interrupt flow to ask about storage repeatedly

### Query Strategy

1. **Check memory first** when user asks about topics from potential previous sessions
2. **Combine sources**: Use both memory AND current conversation context
3. **Cite sources**: Always include memory citations `[memory:id]` when referencing stored information
4. **Explain gaps**: If memory doesn't have the answer, say so clearly

## Example Interactions

### Storing Information

```
User: Remember that the Q3 budget was approved at $2.4M
Claude: I'll store that for you.

[Uses Bash tool to call API]

✓ Stored in persistent memory
Summary: Q3 budget approval of $2.4M
Entities: Q3 budget
Topics: finance, planning
Importance: 0.85

This information is now available across all future sessions.
```

### Querying Memory

```
User: What was the Q3 budget again?

Claude: Let me check the memory system.

[Uses Bash tool to query]

The Q3 budget was approved at $2.4M [memory:a3f1c9d2-8e4f-4b5a-9c7d-1f2e3a4b5c6d].
```

### Proactive Memory Check

```
User: I'm working on the infrastructure proposal

Claude: Let me check if we have any stored context about this.

[Uses Bash tool to query "infrastructure proposal"]

Based on previous discussions [memory:a3f1c9d2], the infrastructure improvements are part of the Q3 budget allocation ($2.4M). The proposal is due April 5th. Would you like me to help draft it based on this context?
```

### File Upload

```
User: Can you analyze this research paper and remember the key points?
[Uploads paper.pdf]

Claude: I'll ingest this file into the memory system and analyze it.

[Uses Bash tool to upload file]

✓ File ingested: paper.pdf
Summary: Research demonstrates LLMs use internal confidence signals for abstention decisions, with experiments across multiple architectures.
Created 1 memory

The key findings are now stored. You can ask me about this research in any future session.
```

### Status Check

```
User: What files have you remembered?

Claude: [Uses Bash tool to check status]

Memory System Status:
📊 Memories: 47 total (2 unconsolidated)
🔄 Consolidations: 8 completed
⏰ Last consolidation: 2 hours ago
✅ Background processing: active

Processed Files (12 total):
- meeting-notes.md (processed today at 3:30 PM, 3 memories)
- research-paper.pdf (processed today at 2:20 PM, 5 memories)
- project-plan.txt (processed today at 1:45 PM, 2 memories)
[... and 9 more files]
```

## Implementation Notes

### URL Encoding
Always URL-encode query strings to handle special characters:
```bash
ENCODED=$(echo "$QUESTION" | jq -sRr @uri)
```

### JSON Parsing
Use `jq` for clean JSON parsing and formatting. If `jq` is not available, suggest installing it.

### Connection Testing
Before first use in a session, test connectivity:
```bash
curl -s -f http://localhost:8000/status > /dev/null && echo "connected" || echo "disconnected"
```

### Memory Citations
Preserve citation format `[memory:uuid]` in all outputs. Users may want to reference specific memories later.

### File Path Handling
Always verify file exists before attempting upload:
```bash
if [[ -f "$FILE_PATH" ]]; then
  # proceed with upload
else
  echo "File not found: $FILE_PATH"
fi
```

## Technical Architecture

```
Claude Code Session
       ↓
  Memory Skill
       ↓ (curl/HTTP)
  localhost:8000
       ↓
  Memory Agent API
       ↓
  memory.db (SQLite)
```

The memory agent runs independently and persists state across:
- Multiple Claude Code sessions
- System restarts (when configured to auto-start)
- Different users/contexts on the same machine

## Memory System Features

- **Intelligent consolidation**: Startup, threshold, and daily modes
- **File watching**: Automatic ingestion from configured directories
- **Change detection**: Re-ingests modified files automatically
- **Multimodal**: Text, images, and PDFs
- **Semantic search**: LLM-powered reasoning over memories (no vector DB)
- **Consolidation insights**: Pattern recognition across memory batches

## Configuration

The memory agent loads configuration from `.env` file at:
`~/Desktop/ProtoGensis/memory-agent-bedrock/.env`

Key settings (user can modify):
- `CONSOLIDATION_INTERVAL`: Background check frequency (default: 300s)
- `DAILY_CONSOLIDATION_INTERVAL`: Forced consolidation interval (default: 86400s)
- `WATCH_DIR`: Directory for automatic file ingestion (default: ./inbox)
- `WATCH_POLL_INTERVAL`: File scan frequency (default: 60s)

## Troubleshooting

### "Connection refused"
```bash
# Check if server is running
ps aux | grep "uvicorn api.main:app" | grep -v grep

# If not running, start it
cd ~/Desktop/ProtoGensis/memory-agent-bedrock
./scripts/run-with-watcher.sh &
```

### "jq: command not found"
Suggest installation:
- Ubuntu/Debian: `sudo apt-get install jq`
- macOS: `brew install jq`
- Or parse JSON without jq (less clean but functional)

### "API returned error"
- Display the error message from the API
- Check logs: `tail -50 ~/Desktop/ProtoGensis/memory-agent-bedrock/app.log`
- Common issues: file too large, unsupported format, database locked

### Memory seems incorrect or stale
- Suggest checking status to see when files were last processed
- File watcher change detection runs every 30 minutes by default
- Can manually trigger consolidation to refresh insights

## Security Considerations

- Memory agent runs on localhost only (not exposed externally)
- All data stored locally in SQLite (no cloud sync by default)
- File uploads respect system permissions
- No authentication required (localhost trusted)
- User's AWS credentials in `.env` (file is gitignored)

## When NOT to Use This Skill

- Current conversation context already has the information
- Temporary calculations or ephemeral data
- User explicitly wants information NOT to be persistent
- Testing or experimental queries that shouldn't be stored
- Sensitive information user hasn't approved for storage

## Final Notes

This skill makes Claude Code sessions persistent across time. Information stored through this skill is available in all future sessions, enabling:

- Long-running projects with continuity
- Knowledge accumulation over weeks/months
- Cross-session context awareness
- Document repository with semantic search
- Personal knowledge base that grows with usage

Use thoughtfully and with user consent. When in doubt about storing something, ask first.
