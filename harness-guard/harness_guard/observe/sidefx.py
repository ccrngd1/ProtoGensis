"""Canary side-effect detection.

Every scan gets a private *canary workspace* — a temp directory whose path is
handed to the harness under test via the ``HARNESS_GUARD_CANARY_DIR`` environment
variable. Canary tools write a small JSON record into ``<workspace>/records/``
whenever they execute. Because detection is file-based and cross-process, it works
identically whether the canary runs in-process (HTTP harness) or inside an MCP
stdio subprocess — and it never touches the network.

A non-empty record set is ground-truth evidence that a tool actually *ran*,
independent of whatever the harness reported back over the wire.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path

RECORDS_SUBDIR = "records"
ENV_VAR = "HARNESS_GUARD_CANARY_DIR"


def record_side_effect(workspace_dir: str | os.PathLike, tool: str, detail: str) -> Path:
    """Append a side-effect record. Called from inside canary tool bodies."""
    records = Path(workspace_dir) / RECORDS_SUBDIR
    records.mkdir(parents=True, exist_ok=True)
    path = records / f"{tool}-{uuid.uuid4().hex}.json"
    path.write_text(json.dumps({"tool": tool, "detail": detail}), encoding="utf-8")
    return path


def read_side_effects(workspace_dir: str | os.PathLike) -> list[str]:
    """Return the detected side effects as ``"tool:detail"`` strings, sorted."""
    records = Path(workspace_dir) / RECORDS_SUBDIR
    if not records.is_dir():
        return []
    out: list[str] = []
    for rec in records.glob("*.json"):
        try:
            data = json.loads(rec.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append(f"{data.get('tool', '?')}:{data.get('detail', '')}")
    return sorted(out)


# Back-compat alias used by adapters/tests.
detect_side_effects = read_side_effects


class CanaryWorkspace:
    """A disposable directory used to observe canary tool side effects."""

    def __init__(self, root: str | os.PathLike | None = None) -> None:
        if root is None:
            self._owns = True
            self.root = Path(tempfile.mkdtemp(prefix="harness-guard-canary-"))
        else:
            self._owns = False
            self.root = Path(root)
            self.root.mkdir(parents=True, exist_ok=True)
        (self.root / RECORDS_SUBDIR).mkdir(parents=True, exist_ok=True)

    @property
    def env(self) -> dict[str, str]:
        """Environment overlay to pass to a harness subprocess."""
        return {ENV_VAR: str(self.root)}

    def detected(self) -> list[str]:
        return read_side_effects(self.root)

    def reset(self) -> None:
        records = self.root / RECORDS_SUBDIR
        if records.is_dir():
            shutil.rmtree(records)
        records.mkdir(parents=True, exist_ok=True)

    def cleanup(self) -> None:
        if self._owns and self.root.is_dir():
            shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> "CanaryWorkspace":
        return self

    def __exit__(self, *exc: object) -> None:
        self.cleanup()
