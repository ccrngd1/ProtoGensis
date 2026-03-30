---
name: memory
description: Interact with the persistent memory agent running locally (ingest, query, status)
version: 1.0.0
author: ProtoGenesis
tags: [memory, persistence, knowledge-base, local-api]
---

# Memory Agent Skill

This skill provides access to a persistent memory system running on localhost:8000. The memory agent stores information as structured records and can be queried using natural language.

## Available Operations

### 1. Ingest Text
Store information in the memory system by sending text content.

### 2. Ingest File
Upload a file (text, image, or PDF) for automatic extraction and storage.

### 3. Query Memory
Ask questions about stored information. The agent synthesizes answers from memories and consolidations.

### 4. Check Status
View system statistics including memory count, consolidation state, and processed files.

### 5. Trigger Consolidation
Manually trigger the consolidation process to find connections and generate insights.

## Usage Examples

**Store information:**
```
/memory ingest "Meeting with Alice on Q3 budget - approved $2.4M allocation"
```

**Upload a file:**
```
/memory ingest-file ./notes/meeting-summary.pdf
```

**Query stored knowledge:**
```
/memory query "What did Alice say about the budget?"
```

**Check system status:**
```
/memory status
```

**Force consolidation:**
```
/memory consolidate
```

## Implementation Instructions

When the user invokes this skill:

1. **Parse the command** - Extract the operation (ingest, ingest-file, query, status, consolidate) and arguments

2. **For `ingest <text>`:**
   - Use curl to POST to `http://localhost:8000/ingest`
   - Send JSON: `{"text": "<user_text>", "source": "kiro-cli"}`
   - Display the returned summary, entities, topics, and importance score
   - Format: "✓ Stored memory [ID: {id}]\nSummary: {summary}\nEntities: {entities}\nTopics: {topics}\nImportance: {importance}"

3. **For `ingest-file <filepath>`:**
   - Verify the file exists
   - Use curl to POST to `http://localhost:8000/ingest/file` with multipart form data
   - Command: `curl -X POST -F "file=@<filepath>" http://localhost:8000/ingest/file`
   - Display the returned summary and metadata
   - Format: "✓ File ingested: {filename}\nSummary: {summary}\nCreated {memory_count} memories"

4. **For `query <question>`:**
   - URL-encode the question
   - Use curl to GET `http://localhost:8000/query?q=<encoded_question>`
   - Display the answer with clean formatting
   - Preserve memory citation links like [memory:id] in the response
   - Format: Show the answer directly, preserving all formatting and citations

5. **For `status`:**
   - Use curl to GET `http://localhost:8000/status`
   - Parse and display in a readable format:
     ```
     Memory System Status:
     - Total memories: {memory_count}
     - Consolidations: {consolidation_count}
     - Unconsolidated: {unconsolidated_count}
     - Background consolidation: {running/stopped}
     - Last consolidation: {timestamp}

     Processed Files: {total_count}
     {for each file: - filename (last processed: timestamp, memories: count)}
     ```

6. **For `consolidate`:**
   - Use curl to POST to `http://localhost:8000/consolidate`
   - Display whether consolidation ran or was skipped
   - Format: "✓ Consolidation complete: {message}" or "⚠ {message}"

## Error Handling

- If the API returns an error, display: "⚠ Memory API Error: {error_detail}"
- If connection fails, display: "⚠ Cannot connect to memory agent at localhost:8000. Is the server running?"
- Suggest running: `cd ~/Desktop/ProtoGensis/memory-agent-bedrock && ./scripts/run-with-watcher.sh`

## Technical Details

- **API Base URL:** `http://localhost:8000`
- **Supported file types:** .txt, .md, .json, .csv, .log, .yaml, .yml, .png, .jpg, .jpeg, .gif, .webp, .pdf
- **Memory agent uses:** Claude Haiku 4.5 on AWS Bedrock
- **Storage:** SQLite database at memory.db

## Notes

- The memory agent runs independently - it maintains state across kiro-cli sessions
- File watcher may be enabled - files in ./inbox are automatically ingested
- Consolidation runs automatically (startup, threshold-based, and daily)
- Queries include both raw memories and synthesized insights
- All timestamps are in UTC with ISO 8601 format

## Quick Reference

```bash
# Basic operations
/memory ingest "text to remember"
/memory query "what do you know about X?"
/memory status

# File operations
/memory ingest-file path/to/document.pdf

# Advanced
/memory consolidate
```
