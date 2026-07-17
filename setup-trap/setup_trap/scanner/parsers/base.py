"""Neutral parsed-file representation and parser dispatch.

The engine does not care what kind of file it is scanning — it matches rules
against a list of :class:`Segment` objects, each carrying its text, starting
line number, and a ``kind`` (``prose`` / ``code`` / ``line``) so a rule can
target markdown code blocks vs. prose (FR2.1). Non-markdown files produce a
single ``line``-kind segment per logical unit.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Segment:
    """A contiguous chunk of a file the engine can match against.

    ``kind`` is one of:
      prose  markdown prose / headings
      code   markdown fenced code block contents
      line   a raw line (non-markdown files, or whole-file fallback)
    """

    text: str
    start_line: int
    kind: str = "line"


@dataclass
class ParsedFile:
    path: Path
    raw: str
    segments: list = field(default_factory=list)  # list[Segment]
    # Structured extras populated by specific parsers (used by pre-install checks).
    packages: list = field(default_factory=list)  # list[PackageRef]
    index_urls: list = field(default_factory=list)  # list[IndexRef]
    make_targets: list = field(default_factory=list)  # list[MakeTarget]
    parse_error: Optional[str] = None

    @property
    def lines(self) -> list:
        return self.raw.splitlines()


@dataclass
class PackageRef:
    """A dependency reference extracted from requirements.txt / pyproject."""

    name: str
    raw: str
    line: int
    version_spec: Optional[str] = None  # e.g. "==1.2.3"


@dataclass
class IndexRef:
    """An index-url / extra-index-url flag found in a dependency file."""

    url: str
    raw: str
    line: int
    kind: str  # "index-url" | "extra-index-url"


@dataclass
class MakeTarget:
    """A Makefile target and the command lines it runs."""

    name: str
    commands: list  # list[tuple[int, str]]  (line, command)
    line: int


# Filename → parser module dispatch. Globs matched case-insensitively.
def parse_file(path: Path) -> ParsedFile:
    """Dispatch to the right parser based on filename, tolerant of errors."""

    from setup_trap.scanner.parsers import (
        makefile,
        markdown,
        requirements,
        toml_parser,
    )

    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        pf = ParsedFile(path=path, raw="")
        pf.parse_error = f"could not read file: {exc}"
        return pf

    name = path.name.lower()
    try:
        if name == "makefile" or name.endswith(".mk"):
            return makefile.parse(path, raw)
        if name == "requirements.txt" or fnmatch.fnmatch(name, "requirements*.txt"):
            return requirements.parse(path, raw)
        if name == "pyproject.toml":
            return toml_parser.parse(path, raw)
        if name.endswith(".md") or name.endswith(".markdown") or name == ".cursorrules":
            return markdown.parse(path, raw)
        # Fallback: treat as plain lines so rules with broad file_patterns still run.
        return markdown.parse(path, raw)
    except Exception as exc:  # noqa: BLE001 — tolerance is the contract (FR2.5)
        pf = ParsedFile(path=path, raw=raw)
        pf.segments = [Segment(text=raw, start_line=1, kind="line")]
        pf.parse_error = f"parser error ({type(exc).__name__}): {exc}"
        return pf
