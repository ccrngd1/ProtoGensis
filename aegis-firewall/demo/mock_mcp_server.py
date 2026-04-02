"""Mock MCP server for testing and demos."""

import sys
import json


def handle_request(request):
    """Handle a JSON-RPC request."""
    method = request.get('method')
    params = request.get('params', {})

    if method == 'tools/list':
        return {
            'jsonrpc': '2.0',
            'id': request.get('id'),
            'result': {
                'tools': [
                    {'name': 'exec', 'description': 'Execute shell command'},
                    {'name': 'read_file', 'description': 'Read file contents'},
                    {'name': 'write_file', 'description': 'Write to file'},
                    {'name': 'list_files', 'description': 'List directory'},
                ]
            }
        }

    elif method == 'tools/call':
        tool_name = params.get('name')
        arguments = params.get('arguments', {})

        # Simulate tool execution
        result = f"[MOCK] Executed {tool_name} with args: {arguments}"

        return {
            'jsonrpc': '2.0',
            'id': request.get('id'),
            'result': {
                'content': [
                    {'type': 'text', 'text': result}
                ]
            }
        }

    else:
        return {
            'jsonrpc': '2.0',
            'id': request.get('id'),
            'error': {
                'code': -32601,
                'message': f'Method not found: {method}'
            }
        }


def main():
    """Main server loop."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            response = handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            error = {
                'jsonrpc': '2.0',
                'id': None,
                'error': {
                    'code': -32700,
                    'message': 'Parse error'
                }
            }
            print(json.dumps(error), flush=True)


if __name__ == '__main__':
    main()
