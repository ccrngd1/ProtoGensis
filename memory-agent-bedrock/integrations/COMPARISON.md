# Integration Comparison: Claude Code vs Kiro-CLI

Both integrations provide access to the memory agent, but they differ in approach and capabilities.

## Quick Comparison

| Feature | Claude Code Skill | Kiro-CLI Skill |
|---------|------------------|----------------|
| **Activation** | Automatic + Manual | Manual commands only |
| **User Experience** | Natural conversation | Command-based |
| **Proactive** | Yes | No |
| **Installation** | Auto-installer | Manual copy |
| **Format** | Markdown skill | Markdown skill |
| **Commands** | Invisible (automatic) | Explicit `/memory` |

## Claude Code Skill

### Strengths

✅ **Seamless Integration**
- Activates automatically when relevant
- No need to remember special commands
- Natural conversational flow

✅ **Proactive Behavior**
- Suggests storing important information
- Checks memory before answering
- Offers to remember complex decisions

✅ **Better UX**
- User doesn't need to think about memory
- Claude handles all the orchestration
- Feels like natural conversation with persistent memory

✅ **Smart Triggers**
- "Remember that..." → Auto-stores
- "What do you know about..." → Auto-queries
- File uploads → Auto-suggests storage

### Example Flow

```
User: I'm starting a new project called DataPipeline. It needs to handle 1M events/day.

Claude: Got it! I'll remember this for future reference.
[Automatically stores without user needing to say "remember"]

---

[Next session, days later]

User: What were the requirements for DataPipeline again?

Claude: [Automatically checks memory]
Based on our previous discussion, DataPipeline needs to handle 1M events/day...
```

### When to Use

- You want persistent memory without thinking about it
- Natural conversation flow is important
- You're in Claude Code regularly
- You want proactive memory suggestions

## Kiro-CLI Skill

### Strengths

✅ **Explicit Control**
- User decides exactly what gets stored
- Clear command structure
- Predictable behavior

✅ **Batch Operations**
- Easy to script with `/memory` commands
- Can be automated
- Good for programmatic use

✅ **Simple Mental Model**
- "I use `/memory` when I want memory"
- No surprises
- Clear cause and effect

### Example Flow

```
User: /memory ingest "I'm starting a new project called DataPipeline. It needs to handle 1M events/day."

Claude: ✓ Stored in persistent memory
Summary: DataPipeline project requirements - 1M events/day
[...]

---

[Next session, days later]

User: /memory query "What were the requirements for DataPipeline?"

Claude: Based on stored memory [memory:xyz], DataPipeline needs to handle 1M events/day...
```

### When to Use

- You want explicit control over what's stored
- You prefer command-based interfaces
- You're scripting or automating
- You're using Kiro-CLI (legacy)

## Technical Differences

### Claude Code Skill

**Architecture:**
```
User Message
    ↓
Skill triggers (automatic decision)
    ↓
Bash tool (curl)
    ↓
Memory API
```

**Skill Format:**
- Markdown with frontmatter
- Trigger conditions defined
- Proactive behavior encouraged
- Implementation instructions for Claude

**Key File:** `memory.md` (single file)

### Kiro-CLI Skill

**Architecture:**
```
User Command: /memory <action>
    ↓
Skill processes command
    ↓
Bash tool (curl)
    ↓
Memory API
```

**Skill Format:**
- Markdown with frontmatter
- Command-based interface
- Explicit invocation only
- Step-by-step instructions

**Key File:** `kiro-cli-skill.md` (single file)

## Installation Comparison

### Claude Code

```bash
# Automated
cd integrations/claude-code-skill
./install.sh

# Manual
cp claude-code-skill/memory.md ~/.config/claude-code/skills/
```

### Kiro-CLI

```bash
# Manual only
cp kiro-cli-skill.md ~/.config/kiro-cli/skills/memory.md
```

## Usage Comparison

### Storing Information

**Claude Code:**
```
User: Remember that Alice approved the Q3 budget at $2.4M

Claude: [Automatically stores]
✓ I've stored that information for future reference.
```

**Kiro-CLI:**
```
User: /memory ingest "Alice approved the Q3 budget at $2.4M"

Claude: ✓ Stored memory [ID: xyz]
Summary: Alice approved Q3 budget of $2.4M
[...]
```

### Querying Information

**Claude Code:**
```
User: What did Alice say about the budget?

Claude: [Automatically checks memory]
Alice approved the Q3 budget at $2.4M [memory:xyz].
```

**Kiro-CLI:**
```
User: /memory query "What did Alice say about the budget?"

Claude: Alice approved the Q3 budget at $2.4M [memory:xyz].
```

### Checking Status

**Claude Code:**
```
User: What files have you remembered?

Claude: [Automatically uses status endpoint]
Memory System Status:
[...]
```

**Kiro-CLI:**
```
User: /memory status

Claude: Memory System Status:
[...]
```

## Which Should You Use?

### Choose Claude Code Skill If:

- ✅ You use Claude Code regularly
- ✅ You want "memory that just works"
- ✅ Natural conversation is important
- ✅ You like proactive features
- ✅ You want minimal cognitive overhead

### Choose Kiro-CLI Skill If:

- ✅ You're using Kiro-CLI (legacy)
- ✅ You want explicit control
- ✅ You prefer command-based interfaces
- ✅ You're scripting/automating
- ✅ You want predictable behavior

### Use Both?

You can install both! They access the same memory agent, so:
- Use Claude Code skill for natural conversation
- Use Kiro-CLI commands when you want explicit control
- Same underlying data, different interfaces

## Performance

Both integrations have identical performance:
- Same API calls (curl)
- Same response times
- Same memory system
- Same consolidation behavior

The only difference is the user experience layer.

## Future Considerations

### Claude Code Skill
- More sophisticated trigger detection
- Context-aware storage decisions
- Better integration with Claude Code features
- Potential native tool use (no bash)

### Kiro-CLI Skill
- May become legacy as Kiro-CLI is replaced
- Command syntax could be enhanced
- Batch operation support
- Scripting utilities

## Recommendation

**For most users:** Start with the **Claude Code skill**.

It provides better UX and requires less mental overhead. You can always fall back to explicit commands if you need more control.

**For power users:** Install **both**.

Use Claude Code for daily work, and Kiro-CLI commands when you need explicit, scriptable control.

## Migration

If you have the Kiro-CLI skill and want to add Claude Code:

```bash
# Install Claude Code skill
cd integrations/claude-code-skill
./install.sh

# Keep Kiro-CLI skill for explicit commands
# They work together harmoniously
```

Your existing memories work with both - no migration needed!

---

Both integrations are maintained and supported. Choose based on your workflow preferences.
