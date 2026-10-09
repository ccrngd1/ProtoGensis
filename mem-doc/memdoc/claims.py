"""Claims ledger verifier (AC #16).

Every number in README.md / BLOG.md from our own runs or analyses carries
<!-- claim:ID -->; docs/CLAIMS.md maps each ID to the exact command and expected
value. `memdoc claims verify` re-runs offline commands and exits 1 on any
mismatch or any marker without a ledger entry. External numbers carry
<!-- cite:URL-or-arXiv --> instead.

Ledger entries tagged host_only depend on this host's /root/.openclaw history;
when that path is unreadable they print `SKIPPED (host-only): <id>` and are not
counted as passes or mismatches.
"""

import json
import re
import shlex
import subprocess
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
CLAIM_RE = re.compile(r"<!--\s*claim:([A-Za-z0-9_-]+)\s*-->")
CITE_RE = re.compile(r"<!--\s*cite:[^>]+-->")

# Ledger table row: | id | kind | `command` | `expected` | note |
# Commands may contain pipes, so the command and expected value are read from
# the first two backtick spans after the kind cell, not from naive `|` splits.
ROW_START_RE = re.compile(r"^\|\s*`?([A-Za-z0-9_-]+)`?\s*\|\s*([A-Za-z_-]+)\s*\|")
TICK_RE = re.compile(r"`([^`]*)`")


def parse_ledger(path):
    """Returns {id: {kind, command, expected}}."""
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        m = ROW_START_RE.match(line)
        if not m:
            continue
        cid, kind = m.group(1), m.group(2)
        if cid in ("id", "---"):
            continue
        spans = [s.replace("\\|", "|") for s in TICK_RE.findall(line[m.end():])]
        if not spans:
            continue
        command = spans[0]
        expected = spans[1] if len(spans) > 1 else ""
        out[cid] = {"kind": kind, "command": command, "expected": expected}
    return out


def collect_markers(doc_paths):
    found = {}
    for p in doc_paths:
        text = Path(p).read_text(encoding="utf-8")
        for m in CLAIM_RE.finditer(text):
            found.setdefault(m.group(1), []).append(str(p))
    return found


def _run(command, cwd):
    import os
    import sys
    # make `memdoc` resolve to this interpreter's console script even when the
    # venv isn't activated in the caller's shell
    env = dict(os.environ)
    bin_dir = str(Path(sys.executable).parent)
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    r = subprocess.run(["bash", "-c", command], cwd=cwd, capture_output=True,
                       text=True, timeout=600, env=env)
    return r.returncode, r.stdout.strip()


def verify(ledger_path=None, doc_paths=None, cwd=None, host_only_probe=None):
    """Returns (ok, lines). host_only_probe: callable -> bool for /root/.openclaw
    readability (injectable for tests)."""
    cwd = Path(cwd) if cwd else PKG_ROOT
    ledger_path = ledger_path or (cwd / "docs" / "CLAIMS.md")
    doc_paths = doc_paths or [cwd / "README.md", cwd / "BLOG.md"]
    ledger = parse_ledger(ledger_path)
    markers = collect_markers([p for p in doc_paths if Path(p).exists()])

    if host_only_probe is None:
        def host_only_probe():
            probe = Path("/root/.openclaw")
            try:
                return probe.is_dir() and bool(list(probe.iterdir()))
            except PermissionError:
                return False
            except OSError:
                return False

    lines, ok = [], True
    for cid in sorted(markers):
        if cid not in ledger:
            lines.append(f"FAIL: marker claim:{cid} has no ledger entry")
            ok = False
    for cid, entry in sorted(ledger.items()):
        if cid not in markers:
            lines.append(f"note: ledger entry {cid} has no marker in the docs (allowed)")
        if entry["kind"] == "host_only":
            if not host_only_probe():
                lines.append(f"SKIPPED (host-only): {cid}")
                continue
        code, out = _run(entry["command"], cwd)
        expected = entry["expected"]
        if code != 0:
            lines.append(f"FAIL: {cid}: command exited {code}: {entry['command']}")
            ok = False
        elif expected and expected not in out:
            lines.append(f"FAIL: {cid}: expected {expected!r} not in output {out[:200]!r}")
            ok = False
        else:
            lines.append(f"ok: {cid}")
    return ok, lines
