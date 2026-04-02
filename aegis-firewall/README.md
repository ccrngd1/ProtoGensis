# AEGIS Firewall

> **A security firewall for AI agent tool execution with Model Context Protocol (MCP) support**

AEGIS is a transparent security layer that sits between AI agents and tool execution, blocking dangerous operations before they can cause harm. It provides comprehensive threat detection, policy-based access control, cryptographic audit trails, and human-in-the-loop approval workflows.

## Why AEGIS?

AI agents with tool-calling capabilities are powerful but dangerous. A single prompt injection can result in commands like `rm -rf /` or credential exfiltration actually executing on your system. AEGIS stops these attacks before they reach your tools.

**Key Features:**
- 🛡️ **Five Security Scanners**: Shell injection, path traversal, SQL injection, PII detection, secret scanning
- 📋 **YAML Policy Engine**: Flexible rules with allow/deny/escalate actions
- 🔐 **Cryptographic Audit Trail**: Ed25519 signatures + SHA-256 hash chain
- 👤 **Human-in-the-Loop**: WebSocket interface for escalation approval
- 🚦 **Rate Limiting**: Sliding window per agent/tool combination
- 🔍 **Response Scanning**: Outbound secret redaction and prompt injection detection
- 🔌 **Transparent Proxy**: Drop-in replacement for MCP stdio servers

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        AI Agent/LLM                         │
└─────────────────────┬───────────────────────────────────────┘
                      │ JSON-RPC (stdio)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                     AEGIS Firewall                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. String Extractor (Deep nested traversal)        │  │
│  └──────────────────┬───────────────────────────────────┘  │
│                     ▼                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  2. Security Scanners (Parallel)                     │  │
│  │     • Shell Injection    • Path Traversal            │  │
│  │     • SQL Injection      • PII Detector              │  │
│  │     • Secret Scanner                                 │  │
│  └──────────────────┬───────────────────────────────────┘  │
│                     ▼                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  3. Policy Engine (First-match-wins)                │  │
│  │     Rule evaluation → Allow/Deny/Escalate           │  │
│  └──────────────────┬───────────────────────────────────┘  │
│                     ▼                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  4. Decision + Audit Logging                         │  │
│  │     Ed25519 sign + SHA-256 chain → JSONL            │  │
│  └──────────────────┬───────────────────────────────────┘  │
│                     ▼                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  5. Rate Limiter (Sliding window)                   │  │
│  └──────────────────┬───────────────────────────────────┘  │
│                     ▼                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  6. HITL Server (If escalated)                      │  │
│  │     WebSocket → Human approval → Timeout=deny       │  │
│  └──────────────────┬───────────────────────────────────┘  │
└─────────────────────┼───────────────────────────────────────┘
                      │ JSON-RPC (stdio)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                      MCP Server                             │
│              (Your actual tool implementation)              │
└─────────────────────────────────────────────────────────────┘
```

## Installation

```bash
# Clone repository
git clone https://github.com/your-org/aegis-firewall.git
cd aegis-firewall

# Install dependencies
pip install -r requirements.txt

# Or install as package
pip install -e .
```

## Quick Start

1. **Create a configuration file** (`config.yaml`):

```yaml
policy_file: policies/standard.yaml
audit_log: audit.jsonl
mcp_server_command:
  - python
  - -m
  - your_mcp_server
rate_limiting:
  default_limit: 100
  window_seconds: 60
hitl_timeout: 300
response_scanning: true
```

2. **Run AEGIS**:

```bash
aegis run config.yaml
```

The HITL (Human-in-the-Loop) interface will be available at `http://localhost:8000`.

3. **Your AI agent connects to AEGIS** instead of directly to your MCP server. All tool calls are now protected!

## Policy Configuration

AEGIS includes three built-in policy profiles:

### Permissive (`policies/permissive.yaml`)
- Allows most operations
- Only blocks high-severity threats
- Good for development/testing

### Standard (`policies/standard.yaml`)
- Balanced security for production
- Blocks dangerous operations (shell injection, path traversal, SQL injection)
- Escalates PII and secrets for human review
- **Recommended for most use cases**

### Strict (`policies/strict.yaml`)
- Maximum security
- Escalates most operations for approval
- Blocks all shell execution and file modifications
- Good for high-security environments

### Custom Policies

Create your own YAML policy:

```yaml
name: custom_policy
description: My custom security policy
default_action: deny  # deny, allow, or escalate

rules:
  - name: block_shell_commands
    tools:
      - exec
      - shell
      - run_command
    action: deny
    reason: Shell execution not allowed

  - name: escalate_file_writes
    tools:
      - write_file
      - delete_file
    action: escalate
    reason: File modification requires approval

  - name: allow_readonly
    tools:
      - read_file
      - list_directory
      - search
    action: allow
    reason: Read-only operations are safe

  - name: block_high_severity
    tools: '*'
    min_severity: high
    action: deny
    reason: High severity threat detected
```

**Rule Evaluation:**
- Rules are evaluated in order (first-match-wins)
- Each rule can match on: tool name, severity threshold, threat types, agent ID
- Actions: `allow`, `deny`, or `escalate`

## Security Scanners

### 1. Shell Injection Scanner
Detects:
- Shell metacharacters (`;`, `|`, `&`, `$`, etc.)
- Command substitution (`$(...)`, backticks)
- Dangerous commands (`rm`, `wget`, `sudo`, etc.)
- Environment variable expansion

### 2. Path Traversal Scanner
Detects:
- Directory traversal patterns (`../`, `..\\`)
- URL-encoded traversal (`%2e%2e%2f`)
- Sensitive paths (`/etc/passwd`, `/.ssh/`, etc.)
- Null byte injection
- Absolute path usage (configurable)

### 3. SQL Injection Scanner
Detects:
- SQL keywords (`UNION`, `SELECT`, `DROP`, etc.)
- Comment injection (`--`, `/*`, `#`)
- Classic patterns (`' OR 1=1`, `' OR '1'='1`)
- Stacked queries

### 4. PII Detector
Detects:
- Social Security Numbers
- Credit card numbers (with Luhn validation)
- Email addresses
- Phone numbers
- IP addresses (configurable sensitivity)

### 5. Secret Scanner
Detects:
- AWS access keys and secrets
- GitHub tokens
- JWT tokens
- Private keys
- API keys and tokens
- High-entropy strings (potential secrets)

## Audit Trail

AEGIS creates a tamper-evident audit log with:
- **Ed25519 signatures**: Each entry is cryptographically signed
- **SHA-256 hash chain**: Each entry links to the previous entry's hash
- **JSONL format**: One JSON object per line for easy parsing

### Verify Audit Log

```bash
# Verify integrity
aegis verify audit.jsonl

# View statistics
aegis stats audit.jsonl
```

### Example Audit Entry

```json
{
  "timestamp": 1234567890.123,
  "event_type": "decision",
  "decision": {
    "action": "deny",
    "reason": "Shell injection attempt blocked",
    "tool_name": "exec"
  },
  "previous_hash": "abc123...",
  "entry_hash": "def456...",
  "signature": "789ghi...",
  "verify_key": "jkl012..."
}
```

## Human-in-the-Loop (HITL)

When a tool call is escalated, it's held for human approval via a web interface:

1. Navigate to `http://localhost:8000` (or custom port)
2. See pending escalations with full context
3. Approve or deny each request
4. Configurable timeout (default: 5 minutes → deny)

The HITL server uses WebSocket for real-time updates across multiple clients.

## Rate Limiting

Sliding window rate limiter tracks calls per (agent_id, tool_name):

```yaml
rate_limiting:
  default_limit: 100        # calls per window
  window_seconds: 60        # 60 second window
  per_tool_limits:
    exec: 10                # Restrict dangerous tools
    write_file: 50
```

When limit is exceeded, the call is denied with `retry_after` seconds.

## Response Scanning

AEGIS can scan tool responses for:
- **Secret leakage**: Redacts AWS keys, tokens, JWTs before returning to agent
- **Prompt injection**: Detects attempts to inject commands in responses

Enable in config:
```yaml
response_scanning: true
```

## Extending AEGIS

### Add a Custom Scanner

```python
from typing import List, Dict, Any

class MyCustomScanner:
    def scan(self, strings: List[str]) -> Dict[str, Any]:
        findings = []

        for s in strings:
            if "forbidden_pattern" in s:
                findings.append({
                    "type": "custom_threat",
                    "text": s[:100],
                    "severity": "high"
                })

        return {
            "detected": len(findings) > 0,
            "severity": "high" if findings else "none",
            "findings": findings,
            "scanner": "my_custom_scanner"
        }
```

Register in decision engine:
```python
from aegis.engine import DecisionEngine

engine = DecisionEngine('policy.yaml')
engine.scanners['custom'] = MyCustomScanner()
```

### Add Custom Policy Rules

Policies support:
- `tools`: List of tool names or `'*'` for all
- `min_severity`: Minimum severity threshold (`none`, `low`, `medium`, `high`)
- `threat_types`: Specific scanner names to match
- `agents`: Whitelist/blacklist of agent IDs

## Testing

Run the test suite:

```bash
pytest tests/ -v
```

Run demo attack scenarios:

```bash
python demo/run_all_demos.py
```

Individual demos:
```bash
python demo/attack_shell_injection.py
python demo/attack_path_traversal.py
python demo/attack_pii_leak.py
python demo/attack_secret_exfiltration.py
```

## Performance

AEGIS adds minimal latency:
- String extraction: ~1ms for typical payloads
- Scanner suite: ~5-10ms for all 5 scanners
- Policy evaluation: <1ms
- Audit logging: ~1-2ms
- **Total overhead: ~10-15ms per tool call**

## Security Best Practices

1. **Use the Standard or Strict policy** in production
2. **Monitor the audit log** regularly for suspicious patterns
3. **Set appropriate rate limits** based on your use case
4. **Keep secrets secure**: Store the Ed25519 signing key safely
5. **Review escalations promptly**: Don't let them timeout
6. **Update policies** as you learn about your agent's behavior

## Troubleshooting

### "Permission denied" errors
- Check that the MCP server command is correct
- Verify file permissions for audit log path

### HITL interface not loading
- Check that port 8000 is not in use
- Try a different port: `aegis run config.yaml --hitl-port 8080`

### False positives in scanners
- Adjust scanner sensitivity in config
- Create policy exceptions for trusted tools
- Use the permissive profile for development

## Contributing

Contributions welcome! Areas for improvement:
- Additional scanners (XSS, LDAP injection, etc.)
- Machine learning-based anomaly detection
- Integration with SIEM systems
- Performance optimizations

## License

MIT License - see LICENSE file

## Citation

If you use AEGIS in research, please cite:

```
@software{aegis_firewall,
  title = {AEGIS: Security Firewall for AI Agent Tool Execution},
  year = {2025},
  url = {https://github.com/your-org/aegis-firewall}
}
```

## Acknowledgments

Built on top of:
- FastAPI for HITL server
- PyNaCl for Ed25519 signatures
- PyYAML for policy configuration
- pytest for testing

## See Also

- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE: Common Weakness Enumeration](https://cwe.mitre.org/)
