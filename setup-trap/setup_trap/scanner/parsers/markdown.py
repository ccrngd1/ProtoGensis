"""Markdown parser — separates prose from fenced code blocks (FR2.1).

Lightweight, dependency-free. It walks the file line by line, toggling in/out of
fenced code blocks (``` or ~~~). Each contiguous run of prose or code becomes a
:class:`Segment` carrying its starting line number, so findings report accurate
locations and rules can target ``prose`` vs ``code``.

Also used as the tolerant fallback for arbitrary text files (.cursorrules,
persona files, unknown extensions).
"""

from __future__ import annotations

import re
from pathlib import Path

from setup_trap.scanner.parsers.base import ParsedFile, Segment

_FENCE = re.compile(r"^\s*(```+|~~~+)")


def parse(path: Path, raw: str) -> ParsedFile:
    pf = ParsedFile(path=path, raw=raw)
    lines = raw.splitlines()

    segments: list[Segment] = []
    buf: list[str] = []
    buf_start = 1
    in_code = False

    def flush(kind: str) -> None:
        nonlocal buf
        if buf:
            segments.append(
                Segment(text="\n".join(buf), start_line=buf_start, kind=kind)
            )
            buf = []

    for idx, line in enumerate(lines, start=1):
        if _FENCE.match(line):
            # A fence line toggles code mode. Flush whatever we accumulated
            # (prose if we were outside code, code if we were inside) and start
            # the next buffer on the line after the fence.
            flush("code" if in_code else "prose")
            in_code = not in_code
            buf_start = idx + 1
            continue
        if not buf:
            buf_start = idx
        buf.append(line)

    flush("code" if in_code else "prose")

    # Guarantee at least one segment so broad-pattern rules still run on empties.
    if not segments:
        segments = [Segment(text=raw, start_line=1, kind="prose")]

    pf.segments = segments
    return pf
