"""Makefile parser (FR2.3).

Extracts targets and the command lines each runs, so the pre-install checks can
catch a pip/install invocation with a custom source flag hidden inside an
``install:`` target (paper scenario R10 — Makefile poisoning). Recipe lines are
tab-indented in a real Makefile; we accept leading whitespace to stay tolerant.
Every line is also emitted as a ``line`` Segment for text rules.
"""

from __future__ import annotations

import re
from pathlib import Path

from setup_trap.scanner.parsers.base import MakeTarget, ParsedFile, Segment

_TARGET = re.compile(r"^(?P<name>[A-Za-z0-9][\w./%-]*)\s*:(?!=)")


def parse(path: Path, raw: str) -> ParsedFile:
    pf = ParsedFile(path=path, raw=raw)
    segments: list[Segment] = []
    targets: list[MakeTarget] = []
    current: MakeTarget | None = None

    for idx, line in enumerate(raw.splitlines(), start=1):
        segments.append(Segment(text=line, start_line=idx, kind="line"))

        if not line.strip() or line.lstrip().startswith("#"):
            continue

        # Recipe lines are indented (tab, or spaces in a sloppy Makefile).
        is_recipe = line[:1] in ("\t", " ")
        m = _TARGET.match(line)
        if m and not is_recipe:
            current = MakeTarget(name=m.group("name"), commands=[], line=idx)
            targets.append(current)
        elif is_recipe and current is not None:
            cmd = line.strip().lstrip("@-+")
            if cmd:
                current.commands.append((idx, cmd))

    pf.make_targets = targets
    pf.segments = segments
    return pf
