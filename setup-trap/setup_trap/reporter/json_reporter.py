"""JSON reporter (FR7.2) — machine-readable output for CI / aggregation."""

from __future__ import annotations

import json

from setup_trap.model import Severity


def result_to_dict(result, *, path: str = "") -> dict:
    counts = {"critical": 0, "warning": 0, "info": 0}
    for f in result.findings:
        counts[f.severity.name.lower()] += 1
    return {
        "tool": "setup-trap",
        "version": _version(),
        "scanned_path": path,
        "files_scanned": result.files_scanned,
        "rules_loaded": result.rules_loaded,
        "summary": {
            "total": len(result.findings),
            **counts,
        },
        "notes": list(result.notes),
        "findings": [f.to_dict() for f in result.findings],
    }


def render_json(result, *, path: str = "", indent: int = 2) -> str:
    return json.dumps(result_to_dict(result, path=path), indent=indent)


def surface_to_json(inventory, *, indent: int = 2) -> str:
    return json.dumps(inventory.to_dict(), indent=indent)


def _version() -> str:
    try:
        from setup_trap import __version__

        return __version__
    except Exception:  # noqa: BLE001
        return "0"
