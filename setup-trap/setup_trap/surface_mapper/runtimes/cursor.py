"""Cursor init-file surface inventory.

Provenance: .cursorrules and the newer .cursor/rules/*.mdc project-rules
mechanism are documented Cursor behavior (SOURCED). Exact precedence between
legacy and new formats we tag INFERRED where not explicitly documented.
"""

from setup_trap.model import Provenance
from setup_trap.surface_mapper.base import SurfaceEntry, SurfaceInventory, register

_P = Provenance


@register("cursor")
def inventory() -> SurfaceInventory:
    return SurfaceInventory(
        runtime="cursor",
        display_name="Cursor",
        summary=(
            "Cursor injects project rules into the model's system context. Legacy "
            ".cursorrules and the newer .cursor/rules/*.mdc files both steer the "
            "agent before any user prompt."
        ),
        entries=[
            SurfaceEntry(
                path="./.cursorrules (project root)",
                when_read="every request in the project",
                scope="project",
                risk="Write here -> steer the model's behavior for every prompt "
                "in this repo (legacy but still honored).",
                provenance=_P.SOURCED,
            ),
            SurfaceEntry(
                path=".cursor/rules/*.mdc",
                when_read="attached per glob/always, injected into context",
                scope="project / directory-chain",
                risk="Write a rule file -> inject always-on or path-scoped "
                "instructions; 'always' rules apply to every request.",
                provenance=_P.SOURCED,
                note="Rules can be scoped by globs or set alwaysApply.",
            ),
            SurfaceEntry(
                path="AGENTS.md (project root)",
                when_read="picked up as agent instructions",
                scope="project",
                risk="Write here -> supply agent-wide behavior instructions in the "
                "increasingly-standard AGENTS.md location.",
                provenance=_P.INFERRED,
                note="AGENTS.md convergence; treat read behavior as inferred.",
            ),
            SurfaceEntry(
                path="~/.cursor/ user rules",
                when_read="every session for the user",
                scope="user-global",
                risk="Write here -> inject instructions into all of the user's "
                "Cursor sessions.",
                provenance=_P.INFERRED,
            ),
            SurfaceEntry(
                path=".cursor/mcp.json",
                when_read="MCP server startup",
                scope="project / user",
                risk="Write here -> register a malicious MCP server that supplies "
                "tools/data to the agent.",
                provenance=_P.INFERRED,
            ),
        ],
    )
