"""Hardened demo harness — the fix.

Same tool surface as the vulnerable harness, but every dispatch requires a
matching, unexpired, unconsumed, model-issued authorization:

* A real model turn mints a one-time HMAC authorization bound to
  ``{session_id, turn_id, tool_name, args_hash, nonce, issued_at, expires_at}``.
* The signing key is ephemeral (fresh per process, never stored, never logged).
* At dispatch the harness verifies the presented authorization and consumes it.
* No/invalid/replayed authorization → reject with a provenance error.

Because the signing key never leaves the process, the forge vectors — which carry
no authorization (direct), a fabricated one (replay), or one bound to another
session (cross_session) — all fail verification.
"""

from __future__ import annotations

from ..auth import AuthMinter, Authorization
from .canary_tools import execute_canary

# One ephemeral minter per process. Never persisted; never logged.
_MINTER = AuthMinter(ttl_seconds=30.0)


def mint_for_model_turn(session_id: str, turn_id: str, tool_name: str, tool_input: dict) -> Authorization:
    """Called by the (simulated) model-turn handler when the model emits tool_use."""
    return _MINTER.mint(session_id, turn_id, tool_name, tool_input)


def _extract_auth(arguments: dict, params: dict | None) -> Authorization | None:
    raw = None
    if params is not None:
        raw = params.get("_authorization")
    if raw is None and isinstance(arguments, dict):
        raw = arguments.get("_authorization")
    if raw is None:
        return None
    try:
        return Authorization.from_dict(raw)
    except (KeyError, TypeError, ValueError):
        return None


def dispatch(name: str, arguments: dict, params: dict | None = None) -> dict:
    """Dispatch only with a valid model-issued authorization. HARDENED by design."""
    auth = _extract_auth(arguments, params)
    ok, reason = _MINTER.verify_and_consume(auth, name, arguments)
    if not ok:
        return {
            "content": [{"type": "text", "text": f"unauthorized: {reason}"}],
            "structuredContent": {"error": "unauthorized", "reason": reason},
            "isError": True,
        }
    try:
        output = execute_canary(name, arguments)
    except KeyError as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    return {
        "content": [{"type": "text", "text": "ok"}],
        "structuredContent": output,
        "isError": False,
    }


def build_http_app():  # pragma: no cover - optional dep
    from ._http_server import make_wsgi_app

    return make_wsgi_app(dispatch, server_name="hardened-harness")


def main() -> None:  # pragma: no cover - entrypoint
    from ._stdio_server import serve_stdio

    serve_stdio(dispatch, server_name="hardened-harness")


if __name__ == "__main__":  # pragma: no cover
    main()
