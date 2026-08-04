"""Parser front door: tries the ProLeap JAR, falls back to pure Python.

`parse(source_path, copy_dirs)` returns a dict conforming to
cobalt.schema (cobalt-parser-v0). The choice of backend is transparent to
callers; `doc["parser"]` records which one produced the output.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ..schema import validate

# assets/ lives at the package root, one level above cobalt/
_ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
PARSER_JAR = _ASSETS / "cobalt-parser-v0.jar"


class ParserUnavailable(RuntimeError):
    pass


def java_parser_available() -> bool:
    return PARSER_JAR.exists() and shutil.which("java") is not None


def parse_with_java(source_path: str, copy_dirs: list[str]) -> dict:
    """Invoke the ProLeap wrapper JAR. JSON contract on stdout."""
    if not java_parser_available():
        raise ParserUnavailable(
            f"JAR not found at {PARSER_JAR} or no `java` on PATH; "
            "build it with java-parser/build.sh"
        )
    cmd = ["java", "-jar", str(PARSER_JAR), source_path]
    for d in copy_dirs:
        cmd += ["--copy-dir", d]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise ParserUnavailable(
            f"cobalt-parser-v0.jar exited {result.returncode}: {result.stderr.strip()}"
        )
    return validate(json.loads(result.stdout))


def parse_with_fallback(source_path: str, copy_dirs: list[str]) -> dict:
    from .fallback import parse_source

    return validate(parse_source(source_path, copy_dirs))


def parse(source_path: str, copy_dirs: list[str] | None = None,
          prefer: str = "auto") -> dict:
    """Parse a COBOL source file into the cobalt-parser-v0 document.

    prefer: "auto" (java if available, else fallback), "java", "fallback".
    """
    copy_dirs = copy_dirs or []
    if prefer == "java":
        return parse_with_java(source_path, copy_dirs)
    if prefer == "fallback":
        return parse_with_fallback(source_path, copy_dirs)
    if java_parser_available():
        try:
            return parse_with_java(source_path, copy_dirs)
        except ParserUnavailable:
            pass
    return parse_with_fallback(source_path, copy_dirs)
