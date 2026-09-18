"""Shared access-extraction rules for both capture paths.

A file counts as "accessed" when a file-opening tool call COMPLETED
SUCCESSFULLY on it:

- hooks path: Claude Code fires PostToolUse only after a tool completes
  successfully, so every logged PostToolUse with a file path is an access.
- transcript path: a tool_use block whose paired tool_result is not an
  error is an access.

Tools counted: Read, Edit, MultiEdit, NotebookEdit (Edit implies the agent
inspected the file's content). Write is NOT counted: creating/overwriting
a file is not evidence its prior content was reviewed.

KNOWN BLIND SPOT: files read through Bash (cat/grep/less/head...) are not
visible to either path. See README "Bash-read blind spot".
"""

from __future__ import annotations

from ..paths import normalize

# tool name -> tool_input key holding the file path
FILE_ACCESS_TOOLS: dict[str, str] = {
    "Read": "file_path",
    "Edit": "file_path",
    "MultiEdit": "file_path",
    "NotebookEdit": "notebook_path",
}


def access_path(tool_name: str, tool_input: dict | None, root: str | None = None) -> str | None:
    """Return the normalized path accessed by this tool call, or None."""
    key = FILE_ACCESS_TOOLS.get(tool_name or "")
    if not key or not isinstance(tool_input, dict):
        return None
    raw = tool_input.get(key)
    if not raw or not isinstance(raw, str):
        return None
    return normalize(raw, root)
