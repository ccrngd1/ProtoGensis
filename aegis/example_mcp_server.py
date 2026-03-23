#!/usr/bin/env python3
"""
Example MCP server for testing AEGIS proxy.

This is a minimal MCP server that responds to JSON-RPC tool calls.
Run it through AEGIS:
    aegis run -- python example_mcp_server.py
"""

import json
import sys


def handle_tool_call(request):
    """Handle a tools/call request."""
    method = request.get('method')
    params = request.get('params', {})
    request_id = request.get('id')

    if method == 'tools/call' or method == 'call_tool':
        tool_name = params.get('name', 'unknown')
        arguments = params.get('arguments', {})

        # Simulate tool execution
        result = {
            'content': [
                {
                    'type': 'text',
                    'text': f'Executed {tool_name} with args: {arguments}'
                }
            ]
        }

        response = {
            'jsonrpc': '2.0',
            'id': request_id,
            'result': result
        }
    else:
        # Unknown method
        response = {
            'jsonrpc': '2.0',
            'id': request_id,
            'error': {
                'code': -32601,
                'message': f'Method not found: {method}'
            }
        }

    return response


def main():
    """Main server loop - reads JSON-RPC from stdin, writes to stdout."""
    print('[Server] Example MCP Server starting...', file=sys.stderr)

    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = handle_tool_call(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            continue
        except Exception as e:
            print(f'[Server] Error: {e}', file=sys.stderr)


if __name__ == '__main__':
    main()
