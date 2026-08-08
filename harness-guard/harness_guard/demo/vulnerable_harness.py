"""Vulnerable demo harness — the CoreBreak repro.

This harness dispatches a tool call whenever a tool-use-shaped object is present in
the request, WITHOUT verifying that a model turn produced it. This is the Strands
``_has_tool_use_in_latest_message`` pattern: provenance is assumed from message
*shape*, not proven.

Runnable two ways:
* as an MCP stdio server:  ``python -m harness_guard.demo.vulnerable_harness``
* in-process via :func:`dispatch` for HTTP adapters and unit tests.
"""

from __future__ import annotations

from .canary_tools import execute_canary


def dispatch(name: str, arguments: dict, params: dict | None = None) -> dict:
    """Dispatch on shape alone — no authorization check. VULNERABLE by design."""
    try:
        output = execute_canary(name, arguments)
    except KeyError as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    return {
        "content": [{"type": "text", "text": "ok"}],
        "structuredContent": output,
        "isError": False,
    }


def build_http_app():  # pragma: no cover - exercised via adapter/CLI, optional dep
    """Return a minimal WSGI app dispatching tool calls without provenance checks."""
    from ._http_server import make_wsgi_app

    return make_wsgi_app(dispatch, server_name="vulnerable-harness")


def main() -> None:  # pragma: no cover - entrypoint
    from ._stdio_server import serve_stdio

    serve_stdio(dispatch, server_name="vulnerable-harness")


if __name__ == "__main__":  # pragma: no cover
    main()
