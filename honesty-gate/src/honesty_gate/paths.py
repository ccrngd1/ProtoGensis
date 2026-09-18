"""Deterministic path normalization shared by every component.

All set membership tests (asked vs actual_accessed vs claims) go through
`normalize` so that `./src/../src/file3.py`, `src/file3.py`, and the
absolute form all land on the same key.
"""

from __future__ import annotations

import os
import posixpath


def normalize(path: str, root: str | None = None) -> str:
    """Normalize a path to an absolute, symlink-free-ish posix form.

    `root` anchors relative paths (defaults to the current working
    directory). Purely lexical (normpath), so behavior is deterministic
    and does not depend on which files exist on this machine.
    """
    p = os.path.expanduser(path.strip())
    if not os.path.isabs(p):
        base = root if root is not None else os.getcwd()
        p = os.path.join(base, p)
    p = os.path.normpath(p)
    return p.replace(os.sep, "/") if os.sep != "/" else p


def normalize_set(paths, root: str | None = None) -> set[str]:
    return {normalize(p, root) for p in paths}


def basename(path: str) -> str:
    return posixpath.basename(normalize(path))


def stem(path: str) -> str:
    name = basename(path)
    dot = name.rfind(".")
    return name[:dot] if dot > 0 else name
