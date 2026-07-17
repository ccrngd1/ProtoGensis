"""SetupTrap — static scanner + attack-surface mapper for AI coding-agent setup files.

SetupTrap scans the config/setup files an AI coding agent reads at
initialization time and flags directives that could hijack the agent before it
does any user-requested work.

Provenance honesty gate (see README): the package-install supply-chain class
(typosquatting, separator confusion, registry redirection, hidden index,
Makefile poisoning, CVE-pinning, error-message injection) is SOURCED from
arXiv:2607.15143. The AGENTS.md/CLAUDE.md behavior-hijacking class (identity,
exfiltration, tool-binding command-wrap, memory-write, conditional triggers) is
a SYNTHESIZED extension grounded in prompt-injection literature and NOT
empirically evaluated by that paper. Every rule carries its provenance tag.
"""

__version__ = "0.1.0"
