"""requirements.txt parser (FR2.2).

Extracts package names + version specs (for typosquat / separator / CVE checks)
and index-url / extra-index-url flags — including the line-embedded form the
paper calls a "hidden index" (an index URL on its own line, not passed on the
CLI). Each parsed line also becomes a ``line`` Segment so text-based rules run.
"""

from __future__ import annotations

import re
from pathlib import Path

from setup_trap.scanner.parsers.base import IndexRef, PackageRef, ParsedFile, Segment

# Package name up to a version specifier / marker / extras.
_REQ = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*"
    r"(?P<extras>\[[^\]]*\])?\s*"
    r"(?P<spec>(==|>=|<=|~=|!=|>|<|===)\s*[^\s;#]+)?"
)
_INDEX = re.compile(
    r"(?P<flag>--(?:extra-)?index-url)[=\s]+(?P<url>\S+)", re.IGNORECASE
)


def parse(path: Path, raw: str) -> ParsedFile:
    pf = ParsedFile(path=path, raw=raw)
    segments: list[Segment] = []

    for idx, line in enumerate(raw.splitlines(), start=1):
        segments.append(Segment(text=line, start_line=idx, kind="line"))
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        m_index = _INDEX.search(line)
        if m_index:
            flag = m_index.group("flag").lower()
            kind = "extra-index-url" if "extra" in flag else "index-url"
            pf.index_urls.append(
                IndexRef(
                    url=m_index.group("url"),
                    raw=stripped,
                    line=idx,
                    kind=kind,
                )
            )
            continue

        # Skip other pip options and includes (-r/-c/-e/./git+...).
        if stripped.startswith("-") or stripped.startswith(".") or "://" in stripped:
            continue

        m = _REQ.match(stripped)
        if m and m.group("name"):
            pf.packages.append(
                PackageRef(
                    name=m.group("name"),
                    raw=stripped,
                    line=idx,
                    version_spec=(m.group("spec") or "").replace(" ", "") or None,
                )
            )

    pf.segments = segments
    return pf
