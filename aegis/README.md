# AEGIS - MCP Pre-Execution Firewall

**A transparent stdio proxy firewall for Model Context Protocol (MCP) tool calls**

AEGIS intercepts and evaluates MCP tool calls before they reach the server, blocking malicious or risky operations through a three-stage security pipeline.

## Architecture

```
┌─────────────┐                          ┌─────────────┐
│  MCP Host   │                          │ MCP Server  │
│  (Claude)   │                          │   Process   │
└──────┬──────┘                          └──────▲──────┘
       │                                        │
       │ JSON-RPC                               │ JSON-RPC
       │ (stdio)                                │ (stdio)
       │                                        │
       ▼                                        │
┌──────────────────────────────────────────────┴──────┐
│                    AEGIS PROXY                      │
│                                                      │
│  ┌────────────────────────────────────────────┐    │
│  │   Stage 1: Deep String Extraction          │    │
│  │   Recursive walk of all JSON arguments     │    │
│  └────────────────┬───────────────────────────┘    │
│                   ▼                                  │
│  ┌────────────────────────────────────────────┐    │
│  │   Stage 2: Content Risk Scanners           │    │
│  │   • Shell Injection                         │    │
│  │   • Path Traversal                          │    │
│  │   • PII Detection                           │    │
│  │   • Secret Detection (entropy + patterns)   │    │
│  │   • SQL Injection                           │    │
│  └────────────────┬───────────────────────────┘    │
│                   ▼                                  │
│  ┌────────────────────────────────────────────┐    │
│  │   Stage 3: YAML Policy Engine               │    │
│  │   First-match-wins rule evaluation          │    │
│  │   Actions: allow / deny / escalate          │    │
│  └────────────────┬───────────────────────────┘    │
│                   ▼                                  │
│  ┌────────────────────────────────────────────┐    │
│  │   Ed25519-Signed Audit Trail                │    │
│  │   SHA-256 hash-chained, tamper-evident      │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
│  Decision: ALLOW → Forward to server                │
│           DENY → Return error to host              │
│           ESCALATE → Require approval (→ deny)     │
└──────────────────────────────────────────────────────┘
```

## Features

- **Transparent Interception**: Stdio-based JSON-RPC proxy works with any MCP server
- **Three-Stage Pipeline**: Extract → Scan → Policy evaluation
- **Multiple Threat Detectors**:
  - Shell injection (metacharacters, dangerous commands)
  - Path traversal (directory traversal, sensitive paths)
  - PII detection (SSN, email, credit cards, phone numbers)
  - Secret detection (API keys, tokens, high-entropy strings)
  - SQL injection (union, drop table, xp_cmdshell)
- **YAML Policy Engine**: Flexible, first-match-wins rules
- **Tamper-Evident Audit**: Ed25519 signatures + SHA-256 hash chaining
- **Built-in Profiles**: default, strict (deny-by-default), permissive

## Installation

```bash
cd /root/projects/protoGen/aegis
pip install -e .
```

## Quick Start

### Run MCP Server Through AEGIS

```bash
# Use default policy
aegis run -- python my_mcp_server.py

# Use strict policy (deny-by-default)
aegis run --policy strict -- python my_mcp_server.py

# Custom policy file
aegis run --policy /path/to/custom.yaml -- python my_mcp_server.py

# Enable verbose logging
aegis run --verbose -- python my_mcp_server.py
```

### Dry-Run Check (No Server)

```bash
# Check if a tool call would be allowed
aegis check '{"name": "execute_command", "arguments": {"command": "ls -la"}}'

# Check malicious call
aegis check '{"name": "execute_command", "arguments": {"command": "rm -rf /"}}'

# Verbose output
aegis check --verbose '{"name": "read_file", "arguments": {"path": "../../etc/passwd"}}'
```

### Verify Audit Chain Integrity

```bash
aegis verify ~/.aegis/audit.jsonl
```

## Policy Configuration

### Built-in Profiles

**default.yaml** - Balanced security
```yaml
default_action: allow
rules:
  - name: block_critical_threats
    min_severity: critical
    action: deny
  - name: block_high_threats
    min_severity: high
    action: deny
  - name: escalate_medium_threats
    min_severity: medium
    action: escalate
```

**strict.yaml** - Deny-by-default
```yaml
default_action: deny
rules:
  - name: deny_all_threats
    threat_types:
      - shell_injection
      - path_traversal
      - pii_detected
      - secret_detected
      - sql_injection
    action: deny
  - name: allow_safe_tools
    tools:
      - get_time
      - get_weather
    action: allow
```

**permissive.yaml** - Minimal restrictions
```yaml
default_action: allow
rules:
  - name: block_critical_only
    min_severity: critical
    threat_types:
      - shell_injection
      - sql_injection
    action: deny
```

### Custom Policy Rules

Rules support multiple matching criteria:

- `tools`: List of exact tool names
- `tool_pattern`: Regex pattern for tool names
- `threat_types`: List of threat types to match
- `min_severity`: Minimum severity level (low, medium, high, critical)

**First matching rule wins!**

Example custom policy:

```yaml
default_action: allow

rules:
  # Deny any shell execution
  - name: block_shell
    tool_pattern: '(exec|shell|bash|command)'
    action: deny

  # Escalate file operations for approval
  - name: escalate_file_ops
    tool_pattern: '(write|delete|remove)'
    action: escalate

  # Deny if secrets detected
  - name: block_secrets
    threat_types: [secret_detected]
    min_severity: medium
    action: deny

  # Allow safe read operations
  - name: allow_reads
    tools: [read_file, list_files]
    action: allow
```

## Audit Trail

AEGIS maintains a tamper-evident audit log at `~/.aegis/audit.jsonl`:

```json
{
  "timestamp": "2026-03-22T10:15:30.123Z",
  "tool_name": "execute_command",
  "decision": "deny",
  "scan_results": [
    {
      "type": "shell_injection",
      "severity": "critical",
      "message": "Dangerous shell command detected: rm -rf"
    }
  ],
  "prev_hash": "abc123...",
  "entry_hash": "def456...",
  "signature": "789abc...",
  "verify_key": "012def..."
}
```

Each entry:
- Links to previous entry via `prev_hash` (hash chaining)
- Is signed with Ed25519 (`signature` + `verify_key`)
- Can be verified for integrity with `aegis verify`

## Testing

```bash
cd /root/projects/protoGen/aegis

# Install dev dependencies
pip install -e '.[dev]'

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_scanners.py -v

# Run with coverage
pytest tests/ --cov=aegis --cov-report=term-missing
```

## Demo Scenarios

Three attack demonstration scripts are included:

### 1. Shell Injection Attack

```bash
python demos/demo_shell_injection.py
```

Demonstrates blocking of:
- Command separators (`;`, `|`, `&`)
- Dangerous commands (`rm -rf`, `dd`, `curl | sh`)

### 2. Path Traversal Attack

```bash
python demos/demo_path_traversal.py
```

Demonstrates blocking of:
- Directory traversal (`../`, `..\\`)
- Sensitive paths (`/etc/passwd`, `/root/`)
- URL-encoded traversal

### 3. Secret Exfiltration Attack

```bash
python demos/demo_secret_exfil.py
```

Demonstrates detection of:
- AWS keys (`AKIA...`)
- GitHub tokens (`ghp_...`)
- JWT tokens
- High-entropy strings (potential API keys)
- PII (SSN, credit cards, emails)

## Development

### Project Structure

```
aegis/
├── pyproject.toml          # Package configuration
├── README.md               # This file
├── aegis/
│   ├── cli.py             # CLI interface (Click)
│   ├── proxy.py           # Stdio JSON-RPC proxy
│   ├── extractor.py       # Deep string extraction
│   ├── scanners/          # Content risk scanners
│   │   ├── shell.py       # Shell injection
│   │   ├── path.py        # Path traversal
│   │   ├── pii.py         # PII detection
│   │   ├── secrets.py     # Secret detection
│   │   └── sql.py         # SQL injection
│   ├── policy.py          # YAML policy engine
│   ├── decision.py        # Decision pipeline
│   └── audit.py           # Audit logger
├── policies/              # Built-in policies
│   ├── default.yaml
│   ├── strict.yaml
│   └── permissive.yaml
├── demos/                 # Attack demonstrations
└── tests/                 # Comprehensive test suite
```

### Adding New Scanners

1. Create scanner class in `aegis/scanners/`
2. Implement `scan(text: str) -> Optional[dict]` method
3. Return dict with `type`, `severity`, `pattern`, `message`
4. Add to `scanners/__init__.py`
5. Add to `DecisionEngine.scanners` list
6. Write tests in `tests/test_scanners.py`

Example:

```python
class CustomScanner:
    def scan(self, text: str) -> Optional[dict]:
        if 'malicious_pattern' in text:
            return {
                'type': 'custom_threat',
                'severity': 'high',
                'pattern': 'malicious_pattern',
                'message': 'Custom threat detected'
            }
        return None
```

## Acceptance Criteria ✓

- [x] Shell injection with `; rm -rf /` is denied
- [x] Clean tool call passes through and is logged
- [x] Path traversal `../../etc/passwd` is caught
- [x] High-entropy API key pattern is caught
- [x] 100 sequential calls produce valid Ed25519 sigs + hash links
- [x] YAML policy deny list blocks specific tool names
- [x] `aegis check` shows DENIED output for malicious JSON

## Security Considerations

- **Stdio-only**: Currently supports stdio transport (not HTTP/SSE)
- **Escalation**: Currently treats escalate as deny (human approval not implemented)
- **Bypass**: Attackers with direct server access can bypass AEGIS
- **False Positives**: Legitimate use of metacharacters may be blocked
- **Performance**: Adds latency to every tool call (typically <10ms)

## License

Built during Protogenesis Week 12 - AEGIS Firewall Project

## References

- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [mcpwall](https://github.com/anthropics/mcpwall) - Original inspiration
- [Ed25519 Signatures](https://ed25519.cr.yp.to/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
