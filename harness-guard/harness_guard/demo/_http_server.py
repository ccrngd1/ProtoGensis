"""Minimal HTTP harness server shared by the demo harnesses.

Uses the stdlib ``http.server`` (no framework dependency). Understands the two
HTTP request shapes the adapters emit:

* OpenAI tool-calling: ``POST /v1/dispatch`` with ``messages[].tool_calls`` and an
  optional top-level ``authorization``.
* AgentCore InvokeHarness: ``POST /invoke-harness`` with ``toolUse`` and an optional
  top-level ``authorization``.

Both are normalized to ``(name, arguments, params)`` and passed to the harness's
``dispatch`` callable. ``params`` carries ``_authorization`` so the hardened
harness can verify provenance exactly as it does over stdio.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

Dispatch = Callable[[str, dict, dict], dict]


def _extract_call(path: str, body: dict) -> tuple[str, dict, dict]:
    """Return (name, arguments, params) from an HTTP request body."""
    authorization = body.get("authorization")
    if path.startswith("/invoke-harness"):
        tool_use = body.get("toolUse", {}) or {}
        name = tool_use.get("name", "")
        arguments = tool_use.get("input", {}) or {}
    else:  # /v1/dispatch (OpenAI shape)
        messages = body.get("messages", []) or []
        tool_calls = []
        for msg in messages:
            if msg.get("tool_calls"):
                tool_calls = msg["tool_calls"]
        name, arguments = "", {}
        if tool_calls:
            fn = tool_calls[-1].get("function", {})
            name = fn.get("name", "")
            arguments = fn.get("arguments", {}) or {}
    params = {"name": name, "arguments": arguments, "_authorization": authorization}
    return name, arguments, params


def make_handler(dispatch: Dispatch, server_name: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence
            return

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                self._send(400, {"error": {"message": "parse error"}})
                return
            name, arguments, params = _extract_call(self.path, body)
            result = dispatch(name, arguments, params)
            self._send(200, {"result": result})

        def do_GET(self):
            self._send(200, {"server": server_name, "status": "ok"})

        def _send(self, code: int, obj: dict):
            payload = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return Handler


def make_wsgi_app(dispatch: Dispatch, server_name: str):
    """Kept for API symmetry; returns a ready-to-serve HTTPServer factory."""
    def serve(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
        return ThreadingHTTPServer((host, port), make_handler(dispatch, server_name))

    return serve


class DemoHttpServer:
    """Context-managed threaded HTTP demo server. Loopback only."""

    def __init__(self, dispatch: Dispatch, server_name: str, host: str = "127.0.0.1") -> None:
        self._server = ThreadingHTTPServer((host, 0), make_handler(dispatch, server_name))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def __enter__(self) -> "DemoHttpServer":
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
