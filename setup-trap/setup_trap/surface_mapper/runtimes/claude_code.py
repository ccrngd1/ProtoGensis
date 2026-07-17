"""Claude Code init-file surface inventory.

Provenance: CLAUDE.md memory files and their user/project/subdirectory scoping
are documented Claude Code behavior (SOURCED). Precise multi-file read-ordering
details we do not assert beyond what is documented; where we generalize we tag
INFERRED.
"""

from setup_trap.model import Provenance
from setup_trap.surface_mapper.base import SurfaceEntry, SurfaceInventory, register

_P = Provenance


@register("claude_code")
def inventory() -> SurfaceInventory:
    return SurfaceInventory(
        runtime="claude_code",
        display_name="Claude Code",
        summary=(
            "Claude Code loads CLAUDE.md memory files at session start, layering "
            "user-global, project, and subdirectory scopes. Anything in these "
            "files is treated as trusted context before any user task runs."
        ),
        entries=[
            SurfaceEntry(
                path="~/.claude/CLAUDE.md",
                when_read="session start (every project)",
                scope="user-global",
                risk="Write here -> inject instructions into EVERY Claude Code "
                "session on this machine, across all projects.",
                provenance=_P.SOURCED,
                note="User-level memory file, documented.",
            ),
            SurfaceEntry(
                path="./CLAUDE.md (project root)",
                when_read="session start when working in the project",
                scope="project",
                risk="Write here -> shape agent behavior for everyone who opens "
                "this repo in Claude Code.",
                provenance=_P.SOURCED,
            ),
            SurfaceEntry(
                path="<subdir>/CLAUDE.md",
                when_read="pulled in when working within that subtree",
                scope="directory-chain",
                risk="Write here -> hijack behavior specifically when the agent "
                "operates in a sensitive subdirectory (e.g. an auth/ module).",
                provenance=_P.SOURCED,
            ),
            SurfaceEntry(
                path="./CLAUDE.local.md",
                when_read="session start (if present); typically gitignored",
                scope="project",
                risk="Write here -> inject un-reviewed local instructions that do "
                "not show up in version control.",
                provenance=_P.INFERRED,
                note="Local override convention; inferred read behavior.",
            ),
            SurfaceEntry(
                path=".claude/settings.json (+ settings.local.json)",
                when_read="session start",
                scope="project / user",
                risk="Write here -> configure hooks that execute commands on tool "
                "events, or grant tool permissions the user never approved.",
                provenance=_P.SOURCED,
                note="Hooks run shell commands on lifecycle events — high value.",
            ),
            SurfaceEntry(
                path=".claude/skills/*/SKILL.md",
                when_read="skill discovery / invocation",
                scope="skill",
                risk="Write here -> a malicious skill body runs as trusted "
                "instructions when the skill is invoked.",
                provenance=_P.INFERRED,
            ),
            SurfaceEntry(
                path="@imports referenced from CLAUDE.md",
                when_read="resolved transitively at load",
                scope="directory-chain",
                risk="Write an imported file -> inject content into memory without "
                "editing the CLAUDE.md a reviewer looks at.",
                provenance=_P.INFERRED,
                note="Import mechanism means the visible file is not the whole surface.",
            ),
        ],
    )
