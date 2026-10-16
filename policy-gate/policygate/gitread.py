"""Allowlisted read-only git wrapper.

Only {log, show, cat-file, rev-parse, ls-tree} are permitted; commands run with
GIT_OPTIONAL_LOCKS=0 so reads never take index locks. No git config is written
anywhere. For non-root use on repos owned by another user, a safe.directory
override can be passed via GIT_CONFIG_COUNT/KEY/VALUE environment variables
only (never needed when running as root).
"""

import os
import re
import subprocess

ALLOWED = {"log", "show", "cat-file", "rev-parse", "ls-tree"}


class GitReadError(Exception):
    pass


def run(root, args, check=True):
    """Run an allowlisted read-only git subcommand with -C <root>.

    Returns stdout as str. Raises GitReadError on a disallowed subcommand or,
    when check=True, a nonzero exit.
    """
    if not args:
        raise GitReadError("empty git argument list")
    sub = args[0]
    if sub not in ALLOWED:
        raise GitReadError(f"git subcommand {sub!r} is not in the read allowlist {sorted(ALLOWED)}")
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    if os.geteuid() != 0 and "GIT_CONFIG_COUNT" not in env:
        # non-root reads of root-owned repos hit safe.directory; pass the
        # override via environment only (no git config is ever written)
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = "safe.directory"
        env["GIT_CONFIG_VALUE_0"] = "*"
    r = subprocess.run(["git", "-C", str(root), *args],
                       capture_output=True, text=True, env=env)
    if check and r.returncode != 0:
        raise GitReadError(f"git {sub} failed ({r.returncode}): {r.stderr.strip()[:200]}")
    return r.stdout


def commit_before(root, path, ts):
    """Newest commit sha with committer time <= ts touching path, or None.

    NOTE: "touching" includes the commit that DELETED the path; callers must
    check path_in_tree() before `show`, else `git show <sha>:<path>` fails
    with exit 128 (phase 2a Bug 2).
    """
    out = run(root, ["log", "-1", "--format=%H", f"--before={ts}", "--", path]).strip()
    return out or None


def path_in_tree(root, sha, path):
    """True if path exists in the tree of commit sha (allowlisted ls-tree)."""
    out = run(root, ["ls-tree", "--name-only", sha, "--", path])
    return bool(out.strip())


def show(root, sha, path):
    return run(root, ["show", f"{sha}:{path}"])


def commit_time(root, sha):
    return run(root, ["log", "-1", "--format=%cI", sha]).strip()


def _iso_utc(cI):
    """%cI committer time (ISO-8601 with offset) -> ISO-8601 UTC with Z."""
    from datetime import datetime, timezone
    return datetime.fromisoformat(cI).astimezone(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def history(root, path, since=None, until=None):
    """Every commit touching path: [{sha, time (ISO-8601 UTC), kind A/M/D}],
    oldest first, via the allowlisted `log` subcommand only."""
    args = ["log", "--format=%H %cI", "--name-status"]
    if since:
        args.append(f"--since={since}")
    if until:
        args.append(f"--until={until}")
    args += ["--", path]
    out = run(root, args)
    entries = []
    sha = ctime = None
    for line in out.splitlines():
        line = line.rstrip("\n")
        if not line.strip():
            continue
        parts = line.split(" ", 1)
        if len(parts) == 2 and re.fullmatch(r"[0-9a-f]{40}", parts[0]):
            sha, ctime = parts[0], _iso_utc(parts[1].strip())
            continue
        if sha and line[:1] in ("A", "M", "D", "R", "C", "T"):
            # normalize to the A/M/D vocabulary: a rename/copy destination is
            # an add of this path; a type change is a modification
            kind = {"R": "A", "C": "A", "T": "M"}.get(line[0], line[0])
            entries.append({"sha": sha, "time": ctime, "kind": kind})
    entries.reverse()
    return entries
