"""Classify a harness response into a coarse response type.

Distinguishes "the tool actually ran and returned a result" from "the harness
rejected/errored/timed out". This is the *wire-level* signal; ground truth about
execution comes from :mod:`harness_guard.observe.sidefx`.
"""

from __future__ import annotations

from typing import Literal

ResponseType = Literal["tool_result", "error", "reject", "timeout"]

# Substrings that indicate an authorization / provenance rejection (a HARDENED tell).
_REJECT_MARKERS = (
    "unauthorized",
    "no model-issued authorization",
    "provenance",
    "forbidden",
    "not authorized",
    "authorization required",
    "auth failed",
    "invalid authorization",
    "rejected",
)

_ERROR_MARKERS = (
    "error",
    "exception",
    "traceback",
    "invalid request",
    "method not found",
    "parse error",
)


def classify_response(raw: dict | None, *, timed_out: bool = False) -> ResponseType:
    """Classify a raw JSON-RPC-ish response dict.

    A ``reject`` is a *deliberate* authorization/provenance refusal — the strongest
    evidence a harness is hardened. A generic ``error`` (malformed request, missing
    method) is weaker. ``tool_result`` means the tool call was honored.
    """
    if timed_out:
        return "timeout"
    if raw is None:
        return "timeout"

    blob = _stringify(raw).lower()

    # An explicit error object in JSON-RPC.
    err = raw.get("error") if isinstance(raw, dict) else None
    if err is not None:
        err_blob = _stringify(err).lower()
        if any(m in err_blob for m in _REJECT_MARKERS):
            return "reject"
        return "error"

    # Some harnesses return 200 with an error-shaped body.
    if any(m in blob for m in _REJECT_MARKERS):
        return "reject"

    result = raw.get("result") if isinstance(raw, dict) else None
    if result is not None:
        # MCP tools/call returns {"content": [...], "isError": bool}
        if isinstance(result, dict) and result.get("isError"):
            res_blob = _stringify(result).lower()
            if any(m in res_blob for m in _REJECT_MARKERS):
                return "reject"
            return "error"
        return "tool_result"

    if any(m in blob for m in _ERROR_MARKERS):
        return "error"

    # Fallback: a bare payload with content is treated as a result.
    if isinstance(raw, dict) and ("content" in raw or "output" in raw):
        return "tool_result"
    return "error"


def _stringify(obj: object) -> str:
    try:
        import json

        return json.dumps(obj, default=str)
    except (TypeError, ValueError):
        return str(obj)
