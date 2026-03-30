# Memory Agent Skill - Example Usage

This document shows example interactions with the memory agent skill in kiro-cli.

## Basic Operations

### Store Information

```
User: /memory ingest "Met with Alice today. She confirmed Q3 budget approval - $2.4M allocated for infrastructure improvements."

Claude: ✓ Stored memory [ID: a3f1c9d2-8e4f-4b5a-9c7d-1f2e3a4b5c6d]
Summary: Alice confirmed Q3 budget approval of $2.4M for infrastructure improvements
Entities: Alice, Q3 budget, infrastructure improvements
Topics: meetings, finance, planning
Importance: 0.82
```

### Query Knowledge

```
User: /memory query "What did Alice say about the budget?"

Claude: Alice confirmed the Q3 budget is approved at $2.4M, specifically allocated for infrastructure improvements [memory:a3f1c9d2]. This approval was mentioned during a recent meeting.
```

### Check System Status

```
User: /memory status

Claude: Memory System Status:
  - Total memories: 47
  - Consolidations: 8
  - Unconsolidated: 2
  - Background consolidation: running
  - Last consolidation: 2026-03-30T17:04:18.529286+00:00

  Processed Files: 12
  - meeting-notes.md (last processed: 2026-03-30T15:30:22, memories: 3)
  - research-paper.pdf (last processed: 2026-03-30T14:20:15, memories: 5)
  - project-plan.txt (last processed: 2026-03-30T13:45:10, memories: 2)
  [... 9 more files]
```

## Advanced Operations

### Upload a PDF

```
User: /memory ingest-file ~/Documents/ai-research/confidence-paper.pdf

Claude: ✓ File ingested: confidence-paper.pdf
Memory ID: 66c359a6-637d-4b36-bfff-6e9c450b546f
Summary: Research paper presents causal evidence that LLMs use internal confidence signals to drive abstention behavior, with experiments across multiple model architectures.
```

### Upload an Image

```
User: /memory ingest-file ~/Pictures/whiteboard-session.jpg

Claude: ✓ File ingested: whiteboard-session.jpg
Memory ID: 9897061b-574e-412d-8404-23feac602b40
Summary: Whiteboard contains system architecture diagram showing three-tier design with API gateway, service layer, and database. Includes handwritten notes about scaling considerations and caching strategy.
```

### Force Consolidation

```
User: /memory consolidate

Claude: ✓ Consolidation complete
Consolidation ID: 3c765a26-1c36-48a9-b616-b2d75e28cb9e
Processed 7 memories

The consolidation found connections between recent meetings, research papers, and project planning notes, generating insights about recurring themes in Q3 priorities.
```

## Complex Queries

### Finding Patterns Across Memories

```
User: /memory query "What are the main themes in my meetings this month?"

Claude: Based on your memories from this month, three main themes emerge:

1. **Budget and Resource Allocation** [memory:a3f1c9d2, memory:b7e4f8a1]
   Alice and the finance team have discussed Q3 budget ($2.4M) and headcount planning across multiple meetings. Infrastructure improvements are a priority.

2. **AI Research and Implementation** [memory:66c359a6, memory:5702a75e]
   Significant attention to LLM capabilities, particularly around confidence estimation and metacognition. Research papers suggest this is informing product decisions.

3. **System Architecture** [consolidation:3c765a26]
   Multiple discussions about scaling, caching strategies, and three-tier architecture design. The whiteboard session [memory:9897061b] captured key architectural decisions.

These themes are interconnected - the budget discussions often reference infrastructure needed for AI system deployment.
```

### Tracking Action Items

```
User: /memory query "What action items came out of meetings with Alice?"

Claude: From meetings with Alice:

1. **Budget Approval Follow-up** [memory:a3f1c9d2]
   - Get written confirmation of $2.4M Q3 allocation
   - Prepare infrastructure improvement proposal
   - Schedule follow-up for early next week

2. **Hiring Timeline** [memory:b7e4f8a1]
   - Review headcount request by Friday
   - Coordinate with HR on candidate pipeline
   - Alice to approve final job descriptions

3. **Architecture Review** [memory:9897061b]
   - Document scaling decisions from whiteboard session
   - Share with engineering team for feedback
   - Schedule technical review meeting
```

## Error Handling

### Server Not Running

```
User: /memory query "test"

Claude: ⚠ Cannot connect to memory agent at localhost:8000. Is the server running?

To start the memory agent:
  cd ~/Desktop/ProtoGensis/memory-agent-bedrock
  ./scripts/run-with-watcher.sh
```

### Invalid File Path

```
User: /memory ingest-file /nonexistent/file.pdf

Claude: ⚠ File not found: /nonexistent/file.pdf

Please check the file path and try again.
```

## Workflow Examples

### Research Workflow

```
# 1. Ingest research papers
/memory ingest-file ~/Downloads/metacognition-paper.pdf
/memory ingest-file ~/Downloads/llm-scaling-laws.pdf

# 2. Add your own notes
/memory ingest "Key insight: confidence signals could be used for AI safety - models that 'know what they don't know' are more reliable"

# 3. Query for synthesis
/memory query "How do the recent papers on metacognition relate to AI safety?"

# 4. Check what's been processed
/memory status
```

### Meeting Notes Workflow

```
# Before meeting
/memory query "What did we discuss in the last meeting with Alice?"

# After meeting - store notes
/memory ingest "Meeting with Alice - March 30, 2026
- Q3 budget approved: $2.4M
- Hiring: 3 positions approved for engineering
- Next steps: Prepare infrastructure proposal by April 5
- Follow-up scheduled for April 7"

# Later - recall specific details
/memory query "When is the follow-up meeting with Alice?"
```

### Document Management Workflow

```
# Point file watcher at your notes directory
# (Configure in .env: WATCH_DIR=~/Documents/notes)

# Files are automatically ingested when created/modified
# Check what's been processed:
/memory status

# Query across all your notes:
/memory query "What projects am I currently working on?"
/memory query "Find all mentions of budget planning"
/memory query "What were the key decisions from last quarter?"
```

## Integration with Regular Conversation

The memory skill works alongside normal Claude conversation:

```
User: I'm trying to remember what Alice said about the Q3 budget. Can you help?

Claude: I'll check the memory system.
/memory query "Alice Q3 budget"

Based on the memory system, Alice confirmed the Q3 budget approval at $2.4M, specifically allocated for infrastructure improvements [memory:a3f1c9d2]. This was discussed in a recent meeting.

Would you like me to look up any other details from that conversation?

User: Yes, what were the next steps?

Claude: The next steps from that meeting were:
1. Get written confirmation of the $2.4M allocation
2. Prepare an infrastructure improvement proposal
3. Schedule a follow-up meeting early next week

Is there anything specific about the infrastructure proposal you'd like to work on?
```

## Tips for Effective Usage

1. **Be descriptive when ingesting** - Include context like dates, people, and key topics
2. **Use consistent naming** - Helps with queries later (e.g., always "Alice" not "alice" or "A.")
3. **Regular consolidation** - Run `/memory consolidate` after ingesting several related items
4. **Check status periodically** - See what's been processed and when
5. **Query broadly first** - Start with open-ended questions, then narrow down
6. **Leverage file watching** - Let the system automatically track your documents
7. **Include action items** - Store next steps and deadlines explicitly

## Advanced: Combining with Other Skills

```
# Research and document workflow
User: Find research papers on LLM metacognition

Claude: [searches web/arxiv]
Found 3 relevant papers. Let me download and ingest them.

[downloads papers]
/memory ingest-file ./paper1.pdf
/memory ingest-file ./paper2.pdf
/memory ingest-file ./paper3.pdf

Papers ingested. Would you like a summary of the key findings?

User: Yes, and create a markdown summary document

Claude: /memory query "summarize key findings from LLM metacognition papers"

[Creates markdown document based on query results]
I've created research-summary.md with the consolidated findings.
```

---

**Note:** This is an example usage document. Actual kiro-cli interactions may vary based on your specific implementation and configuration.
