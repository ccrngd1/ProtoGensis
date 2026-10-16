#!/usr/bin/env python3
"""Fill PENDING_RERUN claim values after the stage-b re-run (phase 4, AC #22).

Generic: for every docs/CLAIMS.md row whose `expected` cell is PENDING_RERUN,
re-run the row's command and replace PENDING_RERUN with the exact value the
command prints (single line). Then replace PENDING_RERUN on any README.md /
BLOG.md / docs/RESULTS.md line that carries the same `<!-- claim:ID -->`
marker, so the prose numbers and the ledger stay in lockstep.

Postscript (Blog Notes title rule): if the `holes-vs-agents` claim was filled,
print which BLOG title applies — the recommended title only if
(policy-silent labeled + ambiguity items) > unauthorized labeled
(`holes_gt_agents=true` in the claim output); otherwise the alternate title
stands. This script only PRINTS the verdict; it does not edit the title.

Usage (MasterControl, repo root, venv active, after host_run.sh stage-b):
    python scripts/fill_rerun_claims.py [--dry-run]

Exit 1 if any PENDING_RERUN command fails or prints nothing.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from policygate import claims  # noqa: E402

DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_NAMES = ("README.md", "BLOG.md", os.path.join("docs", "RESULTS.md"))
MARKER = "PENDING_RERUN"

RECOMMENDED_TITLE = ("I compiled my AGENTS.md into a deterministic gate. "
                     "It found more holes in my rulebook than in my agents.")
ALTERNATE_TITLE = ("My agent read the rule, then rewrote it: replaying eight "
                   "months of AI agents against their own policy")


def fill_ledger(repo, dry_run=False):
    """Run each PENDING_RERUN row's command; return {claim_id: value}."""
    ledger_path = os.path.join(repo, "docs", "CLAIMS.md")
    ledger = claims.parse_ledger(ledger_path)
    values = {}
    failed = []
    for cid, entry in sorted(ledger.items()):
        if entry["expected"] != MARKER:
            continue
        code, out = claims._run(entry["command"], repo)
        value = out.strip().splitlines()[-1].strip() if out.strip() else ""
        if code != 0 or not value:
            failed.append(f"{cid}: command exited {code} with output {out[:120]!r}")
            continue
        values[cid] = value
        print(f"fill: {cid} = {value}")
    if failed:
        for f in failed:
            print(f"FAIL: {f}", file=sys.stderr)
        sys.exit(1)
    if not values:
        print("nothing to fill (no PENDING_RERUN rows)")
        return values
    if dry_run:
        return values

    # rewrite the ledger: replace PENDING_RERUN only on the matched row's line
    lines = open(ledger_path, encoding="utf-8").read().splitlines(keepends=True)
    for i, line in enumerate(lines):
        m = re.match(r"^\|\s*`?([A-Za-z0-9_-]+)`?\s*\|", line.strip())
        if m and m.group(1) in values and MARKER in line:
            lines[i] = line.replace(MARKER, values[m.group(1)], 1)
    with open(ledger_path, "w", encoding="utf-8") as f:
        f.write("".join(lines))
    return values


def fill_docs(repo, values, dry_run=False):
    """Replace PENDING_RERUN on doc lines carrying a filled claim marker."""
    for name in DOC_NAMES:
        path = os.path.join(repo, name)
        if not os.path.exists(path):
            continue
        lines = open(path, encoding="utf-8").read().splitlines(keepends=True)
        changed = False
        for i, line in enumerate(lines):
            if MARKER not in line:
                continue
            for m in claims.CLAIM_RE.finditer(line):
                cid = m.group(1)
                if cid in values:
                    lines[i] = lines[i].replace(MARKER, values[cid], 1)
                    changed = True
                    print(f"fill: {name}:{i + 1} ({cid}) = {values[cid]}")
                    break
        if changed and not dry_run:
            with open(path, "w", encoding="utf-8") as f:
                f.write("".join(lines))


def report_title(values):
    out = values.get("holes-vs-agents", "")
    if not out:
        return
    if "holes_gt_agents=true" in out:
        print(f"BLOG title rule: holes-vs-agents HOLDS ({out}); the "
              f"recommended title applies:\n  {RECOMMENDED_TITLE!r}")
    else:
        print(f"BLOG title rule: holes-vs-agents does NOT hold ({out}); "
              f"the alternate title stands:\n  {ALTERNATE_TITLE!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="print the values without editing any file")
    ap.add_argument("--repo", default=DEFAULT_REPO,
                    help="repo root (tests use a synthetic tree)")
    ns = ap.parse_args()
    values = fill_ledger(ns.repo, dry_run=ns.dry_run)
    fill_docs(ns.repo, values, dry_run=ns.dry_run)
    report_title(values)
    print(f"filled {len(values)} claim(s)" + (" (dry-run)" if ns.dry_run else ""))


if __name__ == "__main__":
    main()
