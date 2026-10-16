"""Claims ledger verifier, ported from mem-doc/memdoc/claims.py (AC #22).

Adds the `research` column, the deltas rule, and the naked-number check.
Own numbers in README/BLOG carry <!-- claim:ID -->; docs/CLAIMS.md rows are
| id | kind | command | expected | research | note | with
kind ∈ {offline, host_only}. External numbers carry <!-- cite:URL-or-arXiv -->.
`claims verify` re-runs each command (host_only rows SKIP off-host), checks
expected appears in the output, fails on any marker without a row, and fails if
a row's non-empty research value differs from expected AND the id is absent from
the docs/RESULTS.md "Deltas vs research" table. PENDING_HOST expected values are
SKIPPED off-host and FAIL on-host. PENDING_RERUN behaves the same way: it marks
a row whose value depends on the stage-b re-run (ambiguity counts changed in
phase 4); MasterControl runs scripts/fill_rerun_claims.py after the re-run to
replace it with the value the row's command prints.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
# not-yet-filled expected values: SKIP off-host, FAIL on-host.
# PENDING_HOST = filled from the first host run; PENDING_RERUN = filled by
# scripts/fill_rerun_claims.py after the stage-b re-run.
PENDING_VALUES = ("PENDING_HOST", "PENDING_RERUN")
CLAIM_RE = re.compile(r"<!--\s*claim:([A-Za-z0-9_-]+)\s*-->")
CITE_RE = re.compile(r"<!--\s*cite:[^>]+-->")
ROW_START_RE = re.compile(r"^\|\s*`?([A-Za-z0-9_-]+)`?\s*\|\s*([A-Za-z_-]+)\s*\|")
TICK_RE = re.compile(r"`([^`]*)`")

# naked-number check: a percentage, N/M ratio, or integer >= 10 on a line
# without a claim/cite marker. Exempt: dates, version strings, arXiv IDs, week
# labels (W42), commit SHAs, and code blocks.
NUMBER_RE = re.compile(r"\d+%|\b\d+\s*/\s*\d+\b|\b\d{2,}\b")
ARXIV_RE = re.compile(r"\b\d{4}\.\d{5}\b")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b20\d{2}\b")
WEEK_RE = re.compile(r"\bW\d{1,2}\b")
SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b")
VERSION_RE = re.compile(r"\bv?\d+\.\d+(\.\d+)?\b")


def parse_ledger(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        m = ROW_START_RE.match(line)
        if not m:
            continue
        cid, kind = m.group(1), m.group(2)
        if cid in ("id", "---") or kind not in ("offline", "host_only"):
            continue
        spans = [s.replace("\\|", "|") for s in TICK_RE.findall(line[m.end():])]
        if not spans:
            continue
        command = spans[0]
        expected = spans[1] if len(spans) > 1 else ""
        research = spans[2] if len(spans) > 2 else ""
        out[cid] = {"kind": kind, "command": command, "expected": expected,
                    "research": research}
    return out


def collect_markers(doc_paths):
    found = {}
    for p in doc_paths:
        if not Path(p).exists():
            continue
        text = Path(p).read_text(encoding="utf-8")
        for m in CLAIM_RE.finditer(text):
            found.setdefault(m.group(1), []).append(str(p))
    return found


def _results_delta_ids(cwd):
    """IDs listed in the docs/RESULTS.md 'Deltas vs research' table."""
    path = Path(cwd) / "docs" / "RESULTS.md"
    if not path.exists():
        return set()
    ids = set()
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if "Deltas vs research" in line:
            in_table = True
            continue
        if in_table:
            if line.startswith("#"):
                in_table = False
                continue
            m = re.match(r"^\|\s*`?([A-Za-z0-9_-]+)`?\s*\|", line.strip())
            if m and m.group(1) not in ("id", "---"):
                ids.add(m.group(1))
    return ids


def naked_number_check(doc_paths):
    """Fail any percentage / N/M / integer >= 10 on a line without a marker."""
    problems = []
    for p in doc_paths:
        if not Path(p).exists():
            continue
        in_code = False
        for lineno, line in enumerate(Path(p).read_text(encoding="utf-8").splitlines(), 1):
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            if CLAIM_RE.search(line) or CITE_RE.search(line):
                continue
            masked = line
            for rx in (ARXIV_RE, DATE_RE, WEEK_RE, SHA_RE, VERSION_RE):
                masked = rx.sub("", masked)
            if NUMBER_RE.search(masked):
                problems.append(f"{os.path.basename(p)}:{lineno}: naked number without claim/cite marker: {line.strip()[:80]}")
    return problems


def _run(command, cwd):
    env = dict(os.environ)
    bin_dir = str(Path(sys.executable).parent)
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    r = subprocess.run(["bash", "-c", command], cwd=cwd, capture_output=True,
                       text=True, timeout=600, env=env)
    return r.returncode, r.stdout.strip()


def _host_readable():
    """"On-host" means the same thing as tests/conftest.py: PG_HOST_TESTS=1
    AND a readable /root/.openclaw. Root alone (readable archive, no opt-in)
    stays off-host, so the offline checklist line is identical everywhere."""
    if os.environ.get("PG_HOST_TESTS") != "1":
        return False
    probe = Path("/root/.openclaw")
    try:
        return probe.is_dir() and bool(list(probe.iterdir()))
    except (PermissionError, OSError):
        return False


def verify(ledger_path=None, doc_paths=None, cwd=None, host_probe=None):
    cwd = Path(cwd) if cwd else PKG_ROOT
    ledger_path = ledger_path if ledger_path else (cwd / "docs" / "CLAIMS.md")
    if not os.path.isabs(str(ledger_path)):
        ledger_path = cwd / ledger_path
    doc_paths = doc_paths or [cwd / "README.md", cwd / "BLOG.md"]
    ledger = parse_ledger(ledger_path)
    markers = collect_markers(doc_paths)
    host_probe = host_probe or _host_readable
    on_host = host_probe()
    delta_ids = _results_delta_ids(cwd)

    lines, ok = [], True

    for cid in sorted(markers):
        if cid not in ledger:
            lines.append(f"FAIL: marker claim:{cid} has no ledger entry")
            ok = False

    for problem in naked_number_check(doc_paths):
        lines.append(f"FAIL: {problem}")
        ok = False

    for cid, entry in sorted(ledger.items()):
        research = entry.get("research", "")
        expected = entry["expected"]
        # host-only / not-yet-filled rows: resolve skip-vs-fail first, before
        # the research-delta rule (a PENDING_HOST / PENDING_RERUN row has no
        # final value to compare against the research column yet).
        if entry["kind"] == "host_only" or expected in PENDING_VALUES:
            if not on_host:
                lines.append(f"SKIPPED (host-only): {cid}")
                continue
            if expected in PENDING_VALUES:
                lines.append(f"FAIL: {cid}: {expected} expected value on-host "
                             "(fill via scripts/fill_rerun_claims.py)")
                ok = False
                continue
        # research-delta rule (applies to rows with a concrete expected value)
        if research and research != expected and cid not in delta_ids:
            lines.append(f"FAIL: {cid}: research {research!r} differs from expected "
                         f"{expected!r} but no RESULTS.md delta row")
            ok = False
            continue
        code, out = _run(entry["command"], cwd)
        if code != 0:
            lines.append(f"FAIL: {cid}: command exited {code}: {entry['command']}")
            ok = False
        elif expected and expected not in out:
            lines.append(f"FAIL: {cid}: expected {expected!r} not in output {out[:200]!r}")
            ok = False
        else:
            lines.append(f"ok: {cid}")
    return ok, lines
