"""File parsers.

Each parser turns a raw file into a :class:`ParsedFile` — the neutral
representation the engine matches rules against. Parsers are tolerant: a
malformed file yields a ``parse_error`` note (surfaced as a Warning finding by
the engine) rather than crashing the scan (FR2.5).
"""

from setup_trap.scanner.parsers.base import ParsedFile, Segment, parse_file

__all__ = ["ParsedFile", "Segment", "parse_file"]
