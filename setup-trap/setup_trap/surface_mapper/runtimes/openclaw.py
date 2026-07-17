"""OpenClaw / CABAL init-file surface inventory.

Provenance grounded in the OpenClaw runtime docs shipped with the install
(docs/concepts/system-prompt.md, docs/concepts/soul.md, docs/cli/hooks.md,
docs/AGENTS.md): the system prompt injects workspace bootstrap files (AGENTS.md,
workspace context), SOUL.md carries agent personality, SKILL.md instructions are
loaded on demand, and hooks are event-driven automations that can fire on
gateway startup. Those behaviors are SOURCED. CABAL-specific operational files
(HEARTBEAT.md, TOOLS.md, persona files) follow the same injection model; their
exact per-file read timing is tagged INFERRED.
"""

from setup_trap.model import Provenance
from setup_trap.surface_mapper.base import SurfaceEntry, SurfaceInventory, register

_P = Provenance


@register("openclaw")
def inventory() -> SurfaceInventory:
    return SurfaceInventory(
        runtime="openclaw",
        display_name="OpenClaw / CABAL",
        summary=(
            "OpenClaw builds each agent's system prompt by injecting workspace "
            "bootstrap files (AGENTS.md and workspace context), the SOUL.md "
            "personality layer, and on-demand SKILL.md instructions; hooks add "
            "event-driven automations that can fire at gateway startup. Every one "
            "of these is trusted context assembled before the agent acts."
        ),
        entries=[
            SurfaceEntry(
                path="AGENTS.md (workspace root)",
                when_read="injected into the system prompt at agent bootstrap",
                scope="project",
                risk="Write here -> inject workspace-wide behavior instructions "
                "into the system prompt for every turn.",
                provenance=_P.SOURCED,
                note="docs/concepts/system-prompt.md: runtime injects AGENTS.md as "
                "workspace context.",
            ),
            SurfaceEntry(
                path="<subdir>/AGENTS.md",
                when_read="injected when the agent works in that subtree",
                scope="directory-chain",
                risk="Write here -> scope a hijack to a sensitive subdirectory "
                "(the docs subtree, an ops runbook, etc.).",
                provenance=_P.SOURCED,
                note="Directory-scoped AGENTS.md is standard OpenClaw layout.",
            ),
            SurfaceEntry(
                path="SOUL.md",
                when_read="injected as the personality/voice layer at bootstrap",
                scope="project",
                risk="Write here -> rewrite the agent's identity and voice — the "
                "cleanest identity-substitution surface.",
                provenance=_P.SOURCED,
                note="docs/concepts/soul.md: SOUL.md is the personality layer.",
            ),
            SurfaceEntry(
                path="skills/*/SKILL.md",
                when_read="skill instructions loaded on demand when invoked",
                scope="skill",
                risk="Write a skill body -> malicious instructions run as trusted "
                "context the moment the skill is used.",
                provenance=_P.SOURCED,
                note="docs/concepts/system-prompt.md: skills load instructions on "
                "demand.",
            ),
            SurfaceEntry(
                path="hooks (agent hooks / gateway startup)",
                when_read="event-driven: /new, /reset, gateway startup, etc.",
                scope="project / user",
                risk="Write/enable a hook -> run commands automatically on "
                "lifecycle events, before any user task — persistence + execution.",
                provenance=_P.SOURCED,
                note="docs/cli/hooks.md: hooks are event-driven automations "
                "including gateway startup.",
            ),
            SurfaceEntry(
                path="HEARTBEAT.md",
                when_read="consulted by the heartbeat/health loop",
                scope="project / session",
                risk="Write here -> attach behavior to the recurring heartbeat, "
                "giving an attacker a periodic, low-visibility trigger.",
                provenance=_P.INFERRED,
                note="CABAL operational convention; exact read timing inferred.",
            ),
            SurfaceEntry(
                path="TOOLS.md",
                when_read="injected/consulted as tool guidance",
                scope="project",
                risk="Write here -> redefine how the agent uses tools (command "
                "wraps, install sources), binding malicious behavior to tools.",
                provenance=_P.INFERRED,
                note="CABAL operational convention; exact read timing inferred.",
            ),
            SurfaceEntry(
                path="persona*.md",
                when_read="injected as additional persona/context",
                scope="project",
                risk="Write here -> layer an alternate persona over the agent's "
                "identity.",
                provenance=_P.INFERRED,
            ),
            SurfaceEntry(
                path="requirements.txt / Makefile / pyproject.toml",
                when_read="when the agent installs dependencies for a task",
                scope="project",
                risk="Write here -> the package-install supply-chain surface "
                "(typosquat, index redirect, Makefile poisoning) from "
                "arXiv:2607.15143.",
                provenance=_P.SOURCED,
                note="This is the paper's proven package-install class.",
            ),
        ],
    )
