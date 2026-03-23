"""Stdio JSON-RPC proxy for MCP tool call interception."""

import asyncio
import json
import sys
from typing import Optional, TextIO
from pathlib import Path
from .decision import DecisionEngine
from .policy import PolicyEngine, get_builtin_policy_path
from .audit import AuditLogger


class MCPProxy:
    """Transparent stdio proxy that intercepts MCP tool calls."""

    def __init__(
        self,
        server_command: list[str],
        policy_profile: str = 'default',
        audit_file: Optional[Path] = None,
        verbose: bool = False
    ):
        """
        Initialize MCP proxy.

        Args:
            server_command: Command to launch MCP server (e.g., ['python', 'server.py'])
            policy_profile: Built-in policy profile or path to custom YAML
            audit_file: Path to audit log file
            verbose: Enable verbose logging
        """
        self.server_command = server_command
        self.verbose = verbose

        # Initialize policy engine
        if Path(policy_profile).exists():
            policy_path = Path(policy_profile)
        else:
            policy_path = get_builtin_policy_path(policy_profile)

        policy_engine = PolicyEngine(policy_path)
        self.decision_engine = DecisionEngine(policy_engine)

        # Initialize audit logger
        if audit_file is None:
            audit_file = Path.home() / '.aegis' / 'audit.jsonl'

        self.audit_logger = AuditLogger(audit_file)

        # Process handles
        self.server_process: Optional[asyncio.subprocess.Process] = None

    async def start(self) -> None:
        """Start the MCP server subprocess and begin proxying."""
        # Launch MCP server subprocess
        self.server_process = await asyncio.create_subprocess_exec(
            *self.server_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        if self.verbose:
            print(f"[AEGIS] Started MCP server: {' '.join(self.server_command)}", file=sys.stderr)

        # Start bidirectional forwarding tasks
        await asyncio.gather(
            self._forward_host_to_server(),
            self._forward_server_to_host(),
            self._forward_server_stderr(),
        )

    async def _forward_host_to_server(self) -> None:
        """Forward messages from MCP host to server, intercepting tool calls."""
        while True:
            try:
                # Read JSON-RPC message from host (stdin)
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )

                if not line:
                    break

                # Parse JSON-RPC message
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    # Pass through non-JSON lines
                    if self.server_process and self.server_process.stdin:
                        self.server_process.stdin.write(line.encode())
                        await self.server_process.stdin.drain()
                    continue

                # Check if this is a tools/call request
                if self._is_tool_call(message):
                    decision = await self._intercept_tool_call(message)

                    if decision == 'deny':
                        # Send error response back to host
                        error_response = self._create_error_response(
                            message,
                            -32000,
                            "Tool call denied by AEGIS firewall"
                        )
                        print(json.dumps(error_response), flush=True)
                        continue

                    elif decision == 'escalate':
                        # For now, treat escalate as deny
                        # In production, this would prompt for human approval
                        error_response = self._create_error_response(
                            message,
                            -32000,
                            "Tool call requires escalation (treated as deny)"
                        )
                        print(json.dumps(error_response), flush=True)
                        continue

                # Allow: forward to server
                if self.server_process and self.server_process.stdin:
                    self.server_process.stdin.write(line.encode())
                    await self.server_process.stdin.drain()

            except Exception as e:
                if self.verbose:
                    print(f"[AEGIS] Error in host->server forward: {e}", file=sys.stderr)
                break

    async def _forward_server_to_host(self) -> None:
        """Forward messages from MCP server to host."""
        if not self.server_process or not self.server_process.stdout:
            return

        while True:
            try:
                line = await self.server_process.stdout.readline()
                if not line:
                    break

                # Forward to host stdout
                sys.stdout.buffer.write(line)
                sys.stdout.flush()

            except Exception as e:
                if self.verbose:
                    print(f"[AEGIS] Error in server->host forward: {e}", file=sys.stderr)
                break

    async def _forward_server_stderr(self) -> None:
        """Forward server stderr to our stderr."""
        if not self.server_process or not self.server_process.stderr:
            return

        while True:
            try:
                line = await self.server_process.stderr.readline()
                if not line:
                    break

                sys.stderr.buffer.write(line)
                sys.stderr.flush()

            except Exception:
                break

    def _is_tool_call(self, message: dict) -> bool:
        """Check if message is a tools/call request."""
        return (
            message.get('method') == 'tools/call' or
            (message.get('method') == 'call_tool' and 'params' in message)
        )

    async def _intercept_tool_call(self, message: dict) -> str:
        """
        Intercept and evaluate tool call.

        Returns:
            Decision: 'allow', 'deny', or 'escalate'
        """
        # Extract tool call info from JSON-RPC params
        params = message.get('params', {})

        tool_call = {
            'name': params.get('name', 'unknown'),
            'arguments': params.get('arguments', {}),
        }

        # Run decision pipeline
        decision, scan_results = self.decision_engine.decide(tool_call)

        # Log to audit trail
        self.audit_logger.log_decision(
            tool_call,
            decision,
            scan_results,
            metadata={'message_id': message.get('id')}
        )

        if self.verbose:
            print(f"[AEGIS] Tool: {tool_call['name']}, Decision: {decision.upper()}", file=sys.stderr)
            if scan_results:
                print(f"[AEGIS] Threats detected: {len(scan_results)}", file=sys.stderr)
                for result in scan_results:
                    print(f"[AEGIS]   - {result['type']}: {result['message']}", file=sys.stderr)

        return decision

    def _create_error_response(self, request: dict, code: int, message: str) -> dict:
        """Create JSON-RPC error response."""
        return {
            'jsonrpc': '2.0',
            'id': request.get('id'),
            'error': {
                'code': code,
                'message': message,
            }
        }
