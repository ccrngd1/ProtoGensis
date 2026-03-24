# Your MCP Tools Have No Firewall. That's a Problem.

*Model Context Protocol gave AI agents real power. AEGIS makes sure they don't misuse it.*

---

**What this project is:** A transparent security proxy that intercepts every MCP tool call and scans it for threats before it reaches your MCP server.
**The problem it solves:** AI agents with MCP tool access have no security layer — a prompt injection or a confused model can execute dangerous commands, and nothing stops it.
**The key insight:** The model is currently the only thing standing between an AI agent and your system — and a model that can be tricked is not a security layer.

---

## The Problem Nobody's Talking About

MCP changed the game. Suddenly, AI agents can execute shell commands, read files, query databases, and call APIs — all through a clean, standardized protocol. Every major AI lab is building MCP integrations. Tool use is exploding.

But here's what's missing: **there's no security layer between the model and the tools.**

When Claude asks to run `execute_command` with the argument `ls -la`, your MCP server dutifully executes it. When a prompt injection tricks Claude into running `ls; rm -rf /`, your MCP server dutifully executes that too.

The model is the firewall. And as anyone in security will tell you, that's not a firewall at all.

## What AEGIS Does

AEGIS is a transparent stdio proxy that sits between your MCP host (Claude, GPT, any LLM) and your MCP server. Every tool call passes through a three-stage security pipeline before reaching the server:

```
MCP Host  →  AEGIS Proxy  →  MCP Server
              │
              ├─ Stage 1: Deep string extraction
              ├─ Stage 2: Content risk scanning
              ├─ Stage 3: YAML policy evaluation
              └─ Tamper-evident audit logging
```

**Stage 1** recursively walks every JSON argument and extracts all string values — no matter how deeply nested. Attackers can't hide payloads inside nested objects.

**Stage 2** runs five specialized scanners against every extracted string:

- **Shell injection** — catches metacharacters (`;`, `|`, `&&`), dangerous commands (`rm -rf`, `dd`, `curl | sh`), and subshell attempts
- **Path traversal** — catches `../` sequences, encoded variants, and access to sensitive paths (`/etc/passwd`, `/root/`)
- **PII detection** — flags SSNs, credit card numbers, emails, and phone numbers before they leak through tool calls
- **Secret detection** — pattern-matches AWS keys (`AKIA...`), GitHub tokens (`ghp_...`), JWTs, and uses Shannon entropy to catch unknown key formats
- **SQL injection** — catches `UNION SELECT`, `DROP TABLE`, `xp_cmdshell`, and other classic payloads

**Stage 3** evaluates findings against a YAML policy using first-match-wins rules. Three actions are available: `allow`, `deny`, or `escalate` (currently treated as deny — human-in-the-loop approval is a future enhancement).

Every decision — allow or deny — gets logged to a tamper-evident audit trail with Ed25519 signatures and SHA-256 hash chaining.

## See It in Action

Install and try it:

```bash
# Check a clean tool call
aegis check '{"name": "read_file", "arguments": {"path": "src/main.py"}}'
# → ALLOW

# Check a shell injection attempt
aegis check '{"name": "execute_command", "arguments": {"command": "ls; rm -rf /"}}'
# → DENY (shell_injection, critical)

# Check a path traversal attempt
aegis check '{"name": "read_file", "arguments": {"path": "../../etc/passwd"}}'
# → DENY (path_traversal, high)

# Check a secret exfiltration attempt
aegis check '{"name": "send_message", "arguments": {"text": "Key: AKIAIOSFODNN7EXAMPLE"}}'
# → DENY (secret_detected, critical)
```

Run it as a proxy in front of any MCP server:

```bash
# Default policy (block high + critical, escalate medium)
aegis run -- python my_mcp_server.py

# Strict policy (deny-by-default, whitelist safe tools)
aegis run --policy strict -- python my_mcp_server.py
```

Verify your audit trail hasn't been tampered with:

```bash
aegis verify ~/.aegis/audit.jsonl
```

## The Policy Engine

AEGIS ships with three built-in profiles, but the real power is custom policies:

```yaml
default_action: allow

rules:
  # Block all shell execution tools
  - name: block_shell
    tool_pattern: '(exec|shell|bash|command)'
    action: deny

  # Escalate file write operations
  - name: escalate_writes
    tool_pattern: '(write|delete|remove)'
    action: escalate

  # Block if secrets detected in any argument
  - name: block_secrets
    threat_types: [secret_detected]
    min_severity: medium
    action: deny

  # Whitelist safe read operations
  - name: allow_reads
    tools: [read_file, list_files, get_time]
    action: allow
```

Rules match on tool names (exact or regex), threat types, and severity levels. First match wins. If nothing matches, the `default_action` applies.

This means you can build policies that are as permissive or restrictive as your use case demands — from "block only critical threats" to "deny everything except a whitelist of safe tools."

## Why This Matters

MCP adoption is accelerating. Claude, GPT, Gemini — they're all getting tool use. And the tools are getting more powerful: file systems, databases, cloud APIs, shell access.

The security model right now is "trust the model." That works until it doesn't. Prompt injections are an unsolved problem. Jailbreaks keep evolving. And even without adversarial attacks, models hallucinate tool calls with wrong arguments.

AEGIS doesn't replace model-level safety. It adds defense in depth — the same principle that makes every other production system secure. Your web app has a WAF even though your code validates input. Your database has access controls even though your API checks permissions. Your MCP tools should have a firewall even though your model tries to be safe.

## The Audit Trail

Every AEGIS decision gets cryptographically signed and hash-chained:

```json
{
  "timestamp": "2026-03-22T10:15:30.123Z",
  "tool_name": "execute_command",
  "decision": "deny",
  "scan_results": [{
    "type": "shell_injection",
    "severity": "critical",
    "message": "Dangerous shell command detected: rm -rf"
  }],
  "prev_hash": "abc123...",
  "entry_hash": "def456...",
  "signature": "789abc..."
}
```

Each entry links to the previous one via SHA-256. Each entry is signed with Ed25519. If anyone tampers with the log — deleting entries, modifying decisions, reordering events — `aegis verify` catches it.

For compliance-heavy environments (healthcare, finance, government), this is table stakes. For everyone else, it's the difference between "we think nothing bad happened" and "we can prove nothing bad happened."

## What's Next

AEGIS is a starting point, not a finished product. The obvious next steps:

- **HTTP/SSE transport** — currently stdio-only; HTTP support would cover remote MCP servers
- **Human-in-the-loop escalation** — the `escalate` action currently defaults to deny; real approval workflows would make medium-risk calls usable
- **Learning mode** — run in observe-only to build a baseline before enforcing policies
- **Rate limiting** — cap tool call frequency to prevent runaway agents
- **Custom scanner plugins** — drop in domain-specific detectors without modifying core

## Try It

AEGIS is open source and available at the [Protogenesis repo](https://github.com). The project is a self-contained Python package with zero heavy dependencies — just `click`, `pyyaml`, and `pynacl`.

```bash
pip install -e .
aegis check '{"name": "execute_command", "arguments": {"command": "echo hello"}}'
```

62 tests. Five scanners. Three policy profiles. One fewer attack surface.

---

*Built during Protogenesis Week 12. AEGIS is named after the mythological shield of Zeus — because your MCP tools deserve better protection than "the model probably won't do that."*
