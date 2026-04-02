"""MCP stdio proxy for transparent JSON-RPC interception."""

import json
import sys
import subprocess
import select
import re
from typing import Dict, Any, Optional, Callable
from ..scanners import SecretScanner


class MCPProxy:
    """
    Transparent proxy for MCP stdio protocol.

    Intercepts JSON-RPC messages, applies security checks,
    and forwards to actual MCP server.
    """

    def __init__(
        self,
        server_command: list,
        decision_callback: Callable[[str, Dict[str, Any]], Dict[str, Any]],
        escalation_callback: Optional[Callable] = None,
        response_scan: bool = True
    ):
        """
        Initialize MCP proxy.

        Args:
            server_command: Command to start MCP server (e.g., ['python', 'server.py'])
            decision_callback: Function to check tool calls
                              (tool_name, arguments) -> decision dict
            escalation_callback: Optional callback for escalations
            response_scan: Whether to scan responses for secrets
        """
        self.server_command = server_command
        self.decision_callback = decision_callback
        self.escalation_callback = escalation_callback
        self.response_scan = response_scan

        self.server_process: Optional[subprocess.Popen] = None
        self.secret_scanner = SecretScanner() if response_scan else None

    def start(self):
        """Start the MCP server subprocess."""
        self.server_process = subprocess.Popen(
            self.server_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

    def run(self):
        """
        Main proxy loop.

        Reads from stdin, intercepts tool calls, forwards to server,
        scans responses, and writes to stdout.
        """
        if not self.server_process:
            self.start()

        try:
            while True:
                # Check if server is still running
                if self.server_process.poll() is not None:
                    break

                # Read from stdin (client -> proxy)
                line = sys.stdin.readline()
                if not line:
                    break

                # Parse JSON-RPC message
                try:
                    message = json.loads(line.strip())
                except json.JSONDecodeError:
                    # Not JSON, forward as-is
                    self._forward_to_server(line)
                    continue

                # Check if this is a tool call
                if self._is_tool_call(message):
                    decision = self._check_tool_call(message)

                    if decision['action'] == 'deny':
                        # Send error response to client
                        error_response = self._create_error_response(
                            message,
                            decision['reason']
                        )
                        print(json.dumps(error_response), flush=True)
                        continue
                    elif decision['action'] == 'escalate':
                        # Handle escalation
                        if self.escalation_callback:
                            approved = self.escalation_callback(message, decision)
                            if not approved:
                                error_response = self._create_error_response(
                                    message,
                                    "Request escalated and denied"
                                )
                                print(json.dumps(error_response), flush=True)
                                continue
                    # If allow or escalate+approved, forward to server

                # Forward to server
                self._forward_to_server(line)

                # Read response from server
                response_line = self.server_process.stdout.readline()
                if not response_line:
                    break

                # Scan response if enabled
                if self.response_scan:
                    response_line = self._scan_response(response_line)

                # Forward to client
                print(response_line, end='', flush=True)

        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        """Stop the MCP server subprocess."""
        if self.server_process:
            self.server_process.terminate()
            self.server_process.wait(timeout=5)

    def _is_tool_call(self, message: Dict[str, Any]) -> bool:
        """
        Check if message is a tool call.

        Args:
            message: JSON-RPC message

        Returns:
            True if this is a tools/call request
        """
        return (
            message.get('method') == 'tools/call' or
            (isinstance(message.get('params'), dict) and
             'name' in message['params'])
        )

    def _check_tool_call(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check a tool call with decision engine.

        Args:
            message: JSON-RPC message

        Returns:
            Decision dict
        """
        params = message.get('params', {})
        tool_name = params.get('name', 'unknown')
        arguments = params.get('arguments', {})

        decision = self.decision_callback(tool_name, arguments)
        return decision

    def _forward_to_server(self, line: str):
        """
        Forward a line to the MCP server.

        Args:
            line: Line to forward
        """
        if self.server_process and self.server_process.stdin:
            self.server_process.stdin.write(line)
            self.server_process.stdin.flush()

    def _scan_response(self, response_line: str) -> str:
        """
        Scan response for secrets and redact if found.

        Args:
            response_line: Response from server

        Returns:
            Potentially redacted response
        """
        try:
            response = json.loads(response_line.strip())

            # Extract result content
            result = response.get('result', {})
            content = result.get('content', [])

            # Scan for secrets
            modified = False
            for item in content:
                if isinstance(item, dict) and 'text' in item:
                    text = item['text']
                    scanner_result = self.secret_scanner.scan([text])

                    if scanner_result['detected']:
                        # Redact secrets
                        item['text'] = self._redact_secrets(text, scanner_result)
                        modified = True

            if modified:
                return json.dumps(response) + '\n'

        except (json.JSONDecodeError, KeyError):
            pass

        return response_line

    def _redact_secrets(self, text: str, scan_result: Dict[str, Any]) -> str:
        """
        Redact secrets from text.

        Args:
            text: Original text
            scan_result: Scanner result with findings

        Returns:
            Redacted text
        """
        # For now, simple redaction - could be smarter
        redacted = text

        # Pattern-based redaction
        patterns = {
            'aws_access_key': (r'AKIA[0-9A-Z]{16}', '[REDACTED_AWS_KEY]'),
            'github_token': (r'ghp_[0-9a-zA-Z]{36}', '[REDACTED_GITHUB_TOKEN]'),
            'jwt': (r'eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*', '[REDACTED_JWT]'),
        }

        for pattern_name, (regex, replacement) in patterns.items():
            redacted = re.sub(regex, replacement, redacted)

        return redacted

    def _create_error_response(self, request: Dict[str, Any], reason: str) -> Dict[str, Any]:
        """
        Create JSON-RPC error response.

        Args:
            request: Original request
            reason: Error reason

        Returns:
            Error response dict
        """
        return {
            'jsonrpc': '2.0',
            'id': request.get('id'),
            'error': {
                'code': -32000,
                'message': 'Tool call blocked by AEGIS firewall',
                'data': {'reason': reason}
            }
        }
