# Memory Agent Integrations

This directory contains integrations for connecting the Memory Agent with other tools and systems.

## Available Integrations

### 1. Claude Code Skill
**Directory:** `claude-code-skill/`

Native skill for Claude Code that enables persistent memory across sessions.

**Features:**
- Automatic skill activation when relevant
- Store and query information
- Upload files (text, images, PDFs)
- Check system status
- Proactive memory suggestions

**Installation:**
```bash
cd claude-code-skill
./install.sh
```

See [claude-code-skill/README.md](claude-code-skill/README.md) for detailed documentation.

### 2. Kiro-CLI Skill
**Directory:** `kiro-cli-skill/`

Command-based skill for Kiro-CLI (legacy Claude Code CLI) users.

**Features:**
- Explicit `/memory` commands
- Full control over storage
- Scriptable and automatable
- Predictable behavior
- Battle-tested design

**Installation:**
```bash
cp kiro-cli-skill/memory.md ~/.config/kiro-cli/skills/memory.md
```

**Usage:**

```bash
/memory ingest "Met with Alice today - Q3 budget approved at $2.4M"
/memory query "What did Alice say about the budget?"
/memory status
```

See [kiro-cli-skill/README.md](kiro-cli-skill/README.md) for complete documentation, examples, and troubleshooting.

## Future Integrations

Potential integrations to build:

- **MCP Server** - Expose memory agent as an MCP server for any Claude-compatible client
- **Obsidian Plugin** - Direct integration with Obsidian for seamless note ingestion
- **Alfred Workflow** - Quick memory queries from macOS Alfred
- **Raycast Extension** - Memory agent access via Raycast
- **VS Code Extension** - Memory agent in your code editor
- **Telegram Bot** - Mobile access to your memory system

## Contributing

To add a new integration:

1. Create a new directory with the integration name
2. Include a README.md with setup instructions
3. Provide example usage and configuration
4. Document any prerequisites or dependencies
5. Submit a PR to the main repository

## Support

For issues or questions:
- Check the main [README.md](../README.md) for memory agent documentation
- Review the [BLOG.md](../BLOG.md) for architecture details
- Open an issue on GitHub
