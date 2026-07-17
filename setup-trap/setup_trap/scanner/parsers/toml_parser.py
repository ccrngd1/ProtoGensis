"""pyproject.toml parser (FR2.4).

Reads dependency specs (``project.dependencies``, optional-dependencies) for
typosquat / separator / CVE checks, and surfaces custom package index sources
(``[[tool.poetry.source]]``, ``[[tool.uv.index]]``, pip ``index-url`` under
tool tables) that redirect installs away from PyPI. Uses stdlib ``tomllib``
(Python 3.11+). Tolerant: a malformed TOML yields a parse_error, not a crash.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from setup_trap.scanner.parsers.base import IndexRef, PackageRef, ParsedFile, Segment

_DEP_SEP = ("==", ">=", "<=", "~=", "!=", ">", "<", "===", "[", ";", " ")


def _split_name(spec: str) -> tuple[str, str | None]:
    s = spec.strip()
    # Cut the name at the EARLIEST separator position (not the first in list
    # order) so "requests>=2.31.0" -> "requests", not "requests>".
    cut = len(s)
    for sep in ("[", "=", ">", "<", "~", "!", ";", " ", "("):
        i = s.find(sep)
        if 0 < i < cut:
            cut = i
    name = s[:cut]
    version = None
    for op in ("==", ">=", "<=", "~=", "!=", "==="):
        if op in s:
            version = s[s.index(op):].split(";")[0].strip()
            break
    return name.strip(), version


def _find_line(raw: str, needle: str) -> int:
    for idx, line in enumerate(raw.splitlines(), start=1):
        if needle in line:
            return idx
    return 1


def parse(path: Path, raw: str) -> ParsedFile:
    pf = ParsedFile(path=path, raw=raw)
    pf.segments = [
        Segment(text=line, start_line=idx, kind="line")
        for idx, line in enumerate(raw.splitlines(), start=1)
    ]

    try:
        data = tomllib.loads(raw)
    except (tomllib.TOMLDecodeError, ValueError) as exc:
        pf.parse_error = f"invalid TOML: {exc}"
        return pf

    def collect_deps(deps) -> None:
        if isinstance(deps, list):
            for spec in deps:
                if not isinstance(spec, str):
                    continue
                name, version = _split_name(spec)
                if name:
                    pf.packages.append(
                        PackageRef(
                            name=name,
                            raw=spec,
                            line=_find_line(raw, spec[:20]),
                            version_spec=version,
                        )
                    )
        elif isinstance(deps, dict):
            for name, spec in deps.items():
                ver = spec if isinstance(spec, str) else None
                pf.packages.append(
                    PackageRef(
                        name=str(name),
                        raw=f"{name} = {spec}",
                        line=_find_line(raw, str(name)),
                        version_spec=ver,
                    )
                )

    project = data.get("project", {})
    collect_deps(project.get("dependencies", []))
    for group in (project.get("optional-dependencies", {}) or {}).values():
        collect_deps(group)

    tool = data.get("tool", {})
    # Poetry deps live under tool.poetry.dependencies as a table.
    collect_deps(tool.get("poetry", {}).get("dependencies", {}))

    # Custom package sources that redirect installs off PyPI.
    for src in tool.get("poetry", {}).get("source", []) or []:
        if isinstance(src, dict) and src.get("url"):
            pf.index_urls.append(
                IndexRef(
                    url=src["url"],
                    raw=str(src),
                    line=_find_line(raw, src["url"]),
                    kind="index-url",
                )
            )
    for idx_tbl in tool.get("uv", {}).get("index", []) or []:
        if isinstance(idx_tbl, dict) and idx_tbl.get("url"):
            pf.index_urls.append(
                IndexRef(
                    url=idx_tbl["url"],
                    raw=str(idx_tbl),
                    line=_find_line(raw, idx_tbl["url"]),
                    kind="extra-index-url",
                )
            )
    pip_tbl = tool.get("pip", {})
    for key, kind in (("index-url", "index-url"), ("extra-index-url", "extra-index-url")):
        val = pip_tbl.get(key)
        for url in [val] if isinstance(val, str) else (val or []):
            pf.index_urls.append(
                IndexRef(url=url, raw=f"{key}={url}", line=_find_line(raw, url), kind=kind)
            )

    return pf
