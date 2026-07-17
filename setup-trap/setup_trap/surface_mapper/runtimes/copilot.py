"""GitHub Copilot init-file surface inventory.

Provenance: best-effort. .github/copilot-instructions.md is a documented Copilot
custom-instructions location (SOURCED); other paths and precise read-timing are
INFERRED — the brief explicitly flags Copilot as best-effort / inferred (FR5.3,
success criterion 4).
"""

from setup_trap.model import Provenance
from setup_trap.surface_mapper.base import SurfaceEntry, SurfaceInventory, register

_P = Provenance


@register("copilot")
def inventory() -> SurfaceInventory:
    return SurfaceInventory(
        runtime="copilot",
        display_name="GitHub Copilot",
        summary=(
            "GitHub Copilot reads repository custom-instructions files to steer "
            "chat/agent responses. Paths and read-timing below are best-effort; "
            "several are INFERRED, not vendor-confirmed."
        ),
        entries=[
            SurfaceEntry(
                path=".github/copilot-instructions.md",
                when_read="Copilot Chat / agent requests in the repo",
                scope="project",
                risk="Write here -> inject repo-wide custom instructions Copilot "
                "applies to responses.",
                provenance=_P.SOURCED,
                note="Documented custom-instructions location.",
            ),
            SurfaceEntry(
                path=".github/instructions/*.instructions.md",
                when_read="applied per applyTo glob",
                scope="project / directory-chain",
                risk="Write here -> path-scoped instruction injection for matching "
                "files.",
                provenance=_P.INFERRED,
            ),
            SurfaceEntry(
                path="AGENTS.md (project root)",
                when_read="agent mode, where supported",
                scope="project",
                risk="Write here -> supply agent behavior via the shared AGENTS.md "
                "convention.",
                provenance=_P.INFERRED,
            ),
            SurfaceEntry(
                path=".vscode/settings.json (github.copilot.*)",
                when_read="editor/session start",
                scope="project / user",
                risk="Write here -> alter Copilot configuration and enabled "
                "instruction sources.",
                provenance=_P.INFERRED,
            ),
        ],
    )
