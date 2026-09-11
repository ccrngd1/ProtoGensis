"""Baseline resolution and changeset extraction via git subprocess.

The gate compares the working tree against a baseline commit:

* ``--baseline <ref>`` when given, else
* ``git merge-base HEAD <default branch>`` (origin/HEAD, then origin/main,
  origin/master, main, master), else
* ``HEAD`` (uncommitted changes only), else an empty tree for fresh repos.

Everything downstream (all four layers) sees only the delta: changed files,
changed line numbers, and baseline file contents. Pre-existing debt is
invisible to the gate by construction.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# git's well-known empty tree object; lets us diff a repo with no commits.
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


class GitError(RuntimeError):
    """Raised when git itself fails; maps to exit code 2."""


def _git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


@dataclass
class ChangedFile:
    path: str  # repo-relative, posix separators
    status: str  # A(dded), M(odified), R(enamed) — deletions are excluded
    old_path: str | None = None  # pre-rename path, if renamed
    changed_lines: set[int] = field(default_factory=set)  # new-side line numbers

    @property
    def is_python(self) -> bool:
        return self.path.endswith(".py")


@dataclass
class Changeset:
    repo: Path
    baseline: str
    files: list[ChangedFile]

    @property
    def python_files(self) -> list[ChangedFile]:
        return [f for f in self.files if f.is_python]

    def baseline_content(self, cf: ChangedFile) -> str | None:
        """Content of the file at the baseline, or None if it did not exist."""
        path = cf.old_path or cf.path
        proc = subprocess.run(
            ["git", "-C", str(self.repo), "show", f"{self.baseline}:{path}"],
            capture_output=True,
            text=True,
        )
        return proc.stdout if proc.returncode == 0 else None

    def working_content(self, cf: ChangedFile) -> str | None:
        try:
            return (self.repo / cf.path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None


def repo_root(path: Path) -> Path:
    out = _git(path, "rev-parse", "--show-toplevel").strip()
    return Path(out)


def resolve_baseline(repo: Path, baseline: str | None) -> str:
    if baseline:
        return _git(repo, "rev-parse", "--verify", f"{baseline}^{{commit}}").strip()

    for ref in ("origin/HEAD", "origin/main", "origin/master", "main", "master"):
        probe = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0:
            continue
        mb = subprocess.run(
            ["git", "-C", str(repo), "merge-base", "HEAD", ref],
            capture_output=True,
            text=True,
        )
        if mb.returncode == 0:
            return mb.stdout.strip()

    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", "HEAD"],
        capture_output=True,
        text=True,
    )
    return head.stdout.strip() if head.returncode == 0 else EMPTY_TREE


def _changed_lines(repo: Path, baseline: str, path: str) -> set[int]:
    """New-side line numbers touched by the diff for one file."""
    out = _git(
        repo, "diff", "--unified=0", "--no-color", baseline, "--", path, check=False
    )
    lines: set[int] = set()
    for raw in out.splitlines():
        m = _HUNK_RE.match(raw)
        if m:
            start = int(m.group(1))
            count = int(m.group(2)) if m.group(2) is not None else 1
            lines.update(range(start, start + max(count, 1)))
    return lines


def collect_changeset(path: Path, baseline_ref: str | None = None) -> Changeset:
    repo = repo_root(path)
    baseline = resolve_baseline(repo, baseline_ref)

    # Diff baseline vs working tree (committed + uncommitted), plus untracked files.
    out = _git(repo, "diff", "--name-status", "--no-color", "-M", baseline)
    files: list[ChangedFile] = []
    for row in out.splitlines():
        parts = row.split("\t")
        status = parts[0]
        if status.startswith("D"):
            continue  # deleted files have no new-side content to gate
        if status.startswith("R") and len(parts) >= 3:
            cf = ChangedFile(path=parts[2], status="R", old_path=parts[1])
        else:
            cf = ChangedFile(path=parts[1], status=status[0])
        files.append(cf)

    untracked = _git(repo, "ls-files", "--others", "--exclude-standard")
    for p in untracked.splitlines():
        if p:
            files.append(ChangedFile(path=p, status="A"))

    files.sort(key=lambda f: f.path)
    for cf in files:
        if cf.status == "A" and cf.is_python:
            content = (repo / cf.path)
            try:
                n = len(content.read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                n = 0
            cf.changed_lines = set(range(1, n + 1))
        elif cf.is_python:
            cf.changed_lines = _changed_lines(repo, baseline, cf.path)

    return Changeset(repo=repo, baseline=baseline, files=files)
