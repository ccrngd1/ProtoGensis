"""Reference workspace (AC #15): synthetic hybrid-tiered template.

`memdoc reference init <dir>` writes a budgeted always-loaded core
(AGENTS/SOUL/USER/MEMORY-style files, synthetic content), a one-level catalog.md
whose entries have read_if conditions, and a notes/ episodic tier.

`memdoc reference check <dir>` lints: core <= token budget (default 5K); every
catalog entry has a read_if; no second routing level (per 2607.17598).
"""

import re
from pathlib import Path

from .tokens import ApproxTokenizer

PKG_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = PKG_ROOT / "reference"

CORE_FILES = ("AGENTS.md", "SOUL.md", "USER.md", "MEMORY.md")


def init(target_dir):
    """Copy the committed template into target_dir."""
    import shutil
    target = Path(target_dir)
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"{target} exists and is not empty")
    shutil.copytree(TEMPLATE_DIR, target, dirs_exist_ok=True)
    return target


def check(workspace_dir, core_budget: int = 5000) -> list[str]:
    """Returns a list of violations (empty = pass)."""
    ws = Path(workspace_dir)
    tok = ApproxTokenizer()
    out = []
    core_total = 0
    for name in CORE_FILES:
        p = ws / name
        if not p.exists():
            out.append(f"missing core file {name}")
            continue
        core_total += tok.count(p.read_text(encoding="utf-8"))
    if core_total > core_budget:
        out.append(f"core is {core_total} tokens (estimate); budget is {core_budget}")

    cat = ws / "catalog.md"
    if not cat.exists():
        out.append("missing catalog.md")
        return out
    entries = _parse_catalog(cat.read_text(encoding="utf-8"))
    if not entries:
        out.append("catalog.md has no entries")
    for path, read_if in entries:
        if not read_if.strip():
            out.append(f"catalog entry {path} has no read_if")
        target = ws / path
        if target.suffix == ".md" and target.exists():
            text = target.read_text(encoding="utf-8")
            # a second routing level: a cataloged doc that is itself a catalog
            if _looks_like_catalog(text) and path != "catalog.md":
                out.append(f"catalog entry {path} is a second routing level "
                           "(one level only, per 2607.17598)")
    if not (ws / "notes").is_dir():
        out.append("missing notes/ episodic tier")
    return out


def _parse_catalog(text):
    entries = []
    path, read_if = None, None
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"- `([^`]+)`", s)
        if m:
            if path is not None:
                entries.append((path, read_if or ""))
            path, read_if = m.group(1), ""
        elif s.lower().startswith("- read if:") and path is not None:
            read_if = s[len("- read if:"):].strip()
    if path is not None:
        entries.append((path, read_if or ""))
    return entries


def _looks_like_catalog(text):
    low = text.lower()
    return ("read if:" in low) and ("- `" in text)
