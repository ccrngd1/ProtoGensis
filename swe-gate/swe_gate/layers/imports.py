"""Layer 1 — import hallucination (lead feature).

Walks the AST of every changed Python file and extracts imported module
names. Imports that already existed in the baseline version of the file are
ignored (delta principle); each *new* top-level module must resolve through
one of the deterministic, offline resolvers:

1. relative import → resolved against the repo filesystem
2. repo-local module (repo root, ``src/``, or beside the importing file)
3. Python stdlib (``sys.stdlib_module_names``)
4. installed package (``importlib.util.find_spec``)
5. installed distribution metadata (``importlib.metadata``)

A new import that resolves nowhere is a hallucination candidate and BLOCKS.
With ``--check-pypi`` (opt-in; the only networked code path in SWE-Gate) the
candidate is looked up on the PyPI JSON API:

* 404 → confirmed nonexistent, stays blocking
* found → downgraded to advisory ("exists on PyPI but not installed here")
* network error → stays blocking, labeled "unverified (PyPI unreachable)"

The offline default never touches the network and labels candidates
"unverified against PyPI".
"""

from __future__ import annotations

import ast
import importlib.metadata
import importlib.util
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from swe_gate.findings import Finding, LayerResult
from swe_gate.gitdiff import ChangedFile, Changeset

LAYER = 1

PYPI_JSON_URL = "https://pypi.org/pypi/{name}/json"
PYPI_TIMEOUT = 5.0


@dataclass(frozen=True)
class ImportRef:
    module: str  # full dotted module as written ("" for `from . import x`)
    level: int  # relative-import level
    lineno: int

    @property
    def top(self) -> str:
        return self.module.split(".")[0] if self.module else ""


def _extract_imports(source: str) -> set[ImportRef] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    refs: set[ImportRef] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                refs.add(ImportRef(module=alias.name, level=0, lineno=node.lineno))
        elif isinstance(node, ast.ImportFrom):
            refs.add(
                ImportRef(module=node.module or "", level=node.level, lineno=node.lineno)
            )
    return refs


def _resolves_relative(ref: ImportRef, file_path: Path) -> bool:
    base = file_path.parent
    for _ in range(ref.level - 1):
        base = base.parent
    target = base
    if ref.module:
        for part in ref.module.split("."):
            target = target / part
    return target.is_dir() or target.with_suffix(".py").is_file()


def _resolves_in_repo(top: str, repo: Path, file_dir: Path) -> bool:
    for root in (repo, repo / "src", file_dir):
        cand = root / top
        if cand.is_dir() or cand.with_suffix(".py").is_file():
            return True
    return False


def _resolves_installed(top: str) -> bool:
    if top in sys.stdlib_module_names:
        return True
    try:
        if importlib.util.find_spec(top) is not None:
            return True
    except (ImportError, ValueError, AttributeError):
        pass
    try:
        importlib.metadata.distribution(top)
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


def check_pypi(name: str) -> str:
    """Return 'exists', 'missing', or 'unreachable'. Only called with --check-pypi."""
    try:
        req = urllib.request.Request(
            PYPI_JSON_URL.format(name=name),
            headers={"User-Agent": "swe-gate/0.1", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=PYPI_TIMEOUT) as resp:
            json.load(resp)
            return "exists"
    except urllib.error.HTTPError as exc:
        return "missing" if exc.code == 404 else "unreachable"
    except (urllib.error.URLError, OSError, ValueError):
        return "unreachable"


def run(changeset: Changeset, use_pypi: bool = False) -> LayerResult:
    result = LayerResult(layer=LAYER, status="")
    py_files = changeset.python_files
    if not py_files:
        result.status = "n/a"
        result.detail = "no Python in scope"
        return result

    checked = 0
    pypi_cache: dict[str, str] = {}

    for cf in py_files:
        new_src = changeset.working_content(cf)
        if new_src is None:
            continue
        new_imports = _extract_imports(new_src)
        if new_imports is None:
            continue  # unparseable files are Layer 0/2 territory

        old_src = changeset.baseline_content(cf)
        old_imports = _extract_imports(old_src) if old_src is not None else set()
        if old_imports is None:
            old_imports = set()
        old_keys = {(r.module, r.level) for r in old_imports}

        file_path = changeset.repo / cf.path
        for ref in sorted(new_imports, key=lambda r: (r.lineno, r.module)):
            if (ref.module, ref.level) in old_keys:
                continue  # pre-existing import, out of scope for the gate
            checked += 1

            if ref.level > 0:
                if not _resolves_relative(ref, file_path):
                    result.findings.append(
                        Finding(
                            layer=LAYER,
                            rule_id="import-relative-unresolved",
                            message=(
                                f"relative import '{'.' * ref.level}{ref.module}' "
                                "does not resolve within the repository"
                            ),
                            file=cf.path,
                            line=ref.lineno,
                            blocking=True,
                        )
                    )
                continue

            top = ref.top
            if not top:
                continue
            if _resolves_installed(top) or _resolves_in_repo(top, changeset.repo, file_path.parent):
                continue

            # Unresolved everywhere deterministic — hallucination candidate.
            if use_pypi:
                status = pypi_cache.setdefault(top, check_pypi(top))
                if status == "exists":
                    result.findings.append(
                        Finding(
                            layer=LAYER,
                            rule_id="import-not-installed",
                            message=(
                                f"'{top}' is not installed in this environment but "
                                "exists on PyPI — verify it is a declared dependency"
                            ),
                            file=cf.path,
                            line=ref.lineno,
                            blocking=False,
                        )
                    )
                    continue
                label = (
                    "not found on PyPI"
                    if status == "missing"
                    else "unverified (PyPI unreachable)"
                )
            else:
                label = "unverified against PyPI (offline default; use --check-pypi)"

            result.findings.append(
                Finding(
                    layer=LAYER,
                    rule_id="import-hallucinated",
                    message=(
                        f"import '{ref.module}' resolves to no installed package, "
                        f"stdlib module, or repo-local module; {label}"
                    ),
                    file=cf.path,
                    line=ref.lineno,
                    blocking=True,
                )
            )

    result.detail = f"{checked} new import(s) checked across {len(py_files)} changed file(s)"
    return result.finalize()
