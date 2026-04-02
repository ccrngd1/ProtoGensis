"""Human-in-the-loop WebSocket server for escalation approval."""

import asyncio
import time
import uuid
from typing import Dict, Any, Optional, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json


class HITLServer:
    """
    Human-in-the-loop approval server.

    Holds escalated tool calls and waits for human approval via WebSocket.
    Supports timeout (defaults to deny).
    """

    def __init__(self, timeout_seconds: int = 300):
        """
        Initialize HITL server.

        Args:
            timeout_seconds: Max time to wait for approval (default 5 min)
        """
        self.timeout_seconds = timeout_seconds
        self.app = FastAPI(title="AEGIS HITL Server")

        # Track pending requests
        self.pending_requests: Dict[str, Dict[str, Any]] = {}

        # Track connected clients
        self.connected_clients: Set[WebSocket] = set()

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup FastAPI routes."""

        @self.app.get("/")
        async def index():
            """Serve a simple approval UI."""
            return HTMLResponse(self._get_ui_html())

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self._handle_websocket(websocket)

        @self.app.get("/health")
        async def health():
            return {"status": "ok", "pending_requests": len(self.pending_requests)}

    async def _handle_websocket(self, websocket: WebSocket):
        """
        Handle WebSocket connection for approval interface.

        Args:
            websocket: WebSocket connection
        """
        await websocket.accept()
        self.connected_clients.add(websocket)

        try:
            # Send current pending requests
            await self._send_pending_requests(websocket)

            # Handle messages
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)

                if message['type'] == 'approve':
                    request_id = message['request_id']
                    await self._approve_request(request_id)
                elif message['type'] == 'deny':
                    request_id = message['request_id']
                    await self._deny_request(request_id)

        except WebSocketDisconnect:
            self.connected_clients.discard(websocket)

    async def _send_pending_requests(self, websocket: WebSocket):
        """
        Send all pending requests to a websocket.

        Args:
            websocket: WebSocket to send to
        """
        for request_id, request_data in self.pending_requests.items():
            if request_data['status'] == 'pending':
                await websocket.send_json({
                    'type': 'new_request',
                    'request_id': request_id,
                    'request': request_data['request'],
                    'decision': request_data['decision'],
                    'timestamp': request_data['timestamp']
                })

    async def _approve_request(self, request_id: str):
        """
        Approve a request.

        Args:
            request_id: Request ID to approve
        """
        if request_id in self.pending_requests:
            self.pending_requests[request_id]['status'] = 'approved'
            self.pending_requests[request_id]['resolved_at'] = time.time()

            # Notify all clients
            await self._broadcast({
                'type': 'request_resolved',
                'request_id': request_id,
                'status': 'approved'
            })

    async def _deny_request(self, request_id: str):
        """
        Deny a request.

        Args:
            request_id: Request ID to deny
        """
        if request_id in self.pending_requests:
            self.pending_requests[request_id]['status'] = 'denied'
            self.pending_requests[request_id]['resolved_at'] = time.time()

            await self._broadcast({
                'type': 'request_resolved',
                'request_id': request_id,
                'status': 'denied'
            })

    async def _broadcast(self, message: Dict[str, Any]):
        """
        Broadcast message to all connected clients.

        Args:
            message: Message dict to broadcast
        """
        disconnected = set()
        for client in self.connected_clients:
            try:
                await client.send_json(message)
            except Exception:
                disconnected.add(client)

        # Remove disconnected clients
        self.connected_clients -= disconnected

    def request_approval(
        self,
        request: Dict[str, Any],
        decision: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> bool:
        """
        Request approval for an escalated tool call (blocking).

        Args:
            request: Original tool call request
            decision: Decision from engine
            timeout: Optional timeout override

        Returns:
            True if approved, False if denied or timeout
        """
        request_id = str(uuid.uuid4())
        timeout = timeout or self.timeout_seconds

        # Store pending request
        self.pending_requests[request_id] = {
            'request': request,
            'decision': decision,
            'status': 'pending',
            'timestamp': time.time(),
            'timeout': timeout
        }

        # Notify connected clients asynchronously
        asyncio.create_task(self._broadcast({
            'type': 'new_request',
            'request_id': request_id,
            'request': request,
            'decision': decision,
            'timestamp': time.time()
        }))

        # Wait for approval with timeout
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time

            if elapsed >= timeout:
                # Timeout - deny by default
                self.pending_requests[request_id]['status'] = 'timeout'
                return False

            status = self.pending_requests[request_id]['status']
            if status == 'approved':
                return True
            elif status in ['denied', 'timeout']:
                return False

            # Sleep briefly
            time.sleep(0.1)

    async def request_approval_async(
        self,
        request: Dict[str, Any],
        decision: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> bool:
        """
        Request approval asynchronously.

        Args:
            request: Original tool call request
            decision: Decision from engine
            timeout: Optional timeout override

        Returns:
            True if approved, False if denied or timeout
        """
        request_id = str(uuid.uuid4())
        timeout = timeout or self.timeout_seconds

        self.pending_requests[request_id] = {
            'request': request,
            'decision': decision,
            'status': 'pending',
            'timestamp': time.time(),
            'timeout': timeout
        }

        await self._broadcast({
            'type': 'new_request',
            'request_id': request_id,
            'request': request,
            'decision': decision,
            'timestamp': time.time()
        })

        start_time = time.time()
        while True:
            elapsed = time.time() - start_time

            if elapsed >= timeout:
                self.pending_requests[request_id]['status'] = 'timeout'
                return False

            status = self.pending_requests[request_id]['status']
            if status == 'approved':
                return True
            elif status in ['denied', 'timeout']:
                return False

            await asyncio.sleep(0.1)

    def _get_ui_html(self) -> str:
        """Get HTML for approval UI."""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>AEGIS HITL Approval</title>
    <style>
        body { font-family: monospace; padding: 20px; background: #1e1e1e; color: #d4d4d4; }
        .request { border: 1px solid #444; padding: 15px; margin: 10px 0; background: #252526; }
        .request h3 { color: #4ec9b0; margin-top: 0; }
        button { padding: 10px 20px; margin: 5px; cursor: pointer; font-size: 14px; }
        .approve { background: #4ec9b0; color: #000; border: none; }
        .deny { background: #f48771; color: #000; border: none; }
        pre { background: #1e1e1e; padding: 10px; overflow: auto; }
        .timestamp { color: #808080; font-size: 12px; }
    </style>
</head>
<body>
    <h1>AEGIS Human-in-the-Loop Approval</h1>
    <div id="requests"></div>

    <script>
        const ws = new WebSocket('ws://' + location.host + '/ws');
        const requestsDiv = document.getElementById('requests');

        ws.onmessage = function(event) {
            const msg = JSON.parse(event.data);

            if (msg.type === 'new_request') {
                addRequest(msg);
            } else if (msg.type === 'request_resolved') {
                removeRequest(msg.request_id);
            }
        };

        function addRequest(msg) {
            const div = document.createElement('div');
            div.className = 'request';
            div.id = 'req-' + msg.request_id;

            const time = new Date(msg.timestamp * 1000).toLocaleString();

            div.innerHTML = `
                <h3>Escalated Request</h3>
                <div class="timestamp">${time}</div>
                <p><strong>Reason:</strong> ${msg.decision.reason}</p>
                <p><strong>Tool:</strong> ${msg.decision.tool_name}</p>
                <p><strong>Severity:</strong> ${msg.decision.policy_decision.max_severity}</p>
                <details>
                    <summary>Full Details</summary>
                    <pre>${JSON.stringify(msg, null, 2)}</pre>
                </details>
                <button class="approve" onclick="approve('${msg.request_id}')">Approve</button>
                <button class="deny" onclick="deny('${msg.request_id}')">Deny</button>
            `;

            requestsDiv.insertBefore(div, requestsDiv.firstChild);
        }

        function removeRequest(requestId) {
            const elem = document.getElementById('req-' + requestId);
            if (elem) elem.remove();
        }

        function approve(requestId) {
            ws.send(JSON.stringify({type: 'approve', request_id: requestId}));
        }

        function deny(requestId) {
            ws.send(JSON.stringify({type: 'deny', request_id: requestId}));
        }
    </script>
</body>
</html>
"""
