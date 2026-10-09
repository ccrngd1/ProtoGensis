"""Decay analyzer (AC #14): port of the research spike survival.py.

Exact-line survival of non-heading content lines (>15 chars) across the git
history of one file. Prints aggregates only, never line text (R9). `--until`
truncates the snapshot list to commits dated <= the cutoff.

Formulas and selection rules are unchanged from the spike:
  - snapshot lines: stripped, len > 15, not starting with '#'
  - survival at horizon h: for each snapshot whose date+h is within range,
    |lines & lines_at(date+h)| / |lines| ; median over snapshots
  - churn: distinct lines ever vs current
  - age: days since a current line's first appearance; median + share > 90d

Caveat printed with results: exact-line match counts an edit as a removal, so
this measures churn, not wrong facts.
"""

import datetime as dt
import json
import statistics as st
import subprocess


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


def analyze(repo, rel, until=None):
    """Returns the aggregate dict. Raises RuntimeError if the history is empty."""
    log = _git(repo, "log", "--reverse", "--format=%h %ad", "--date=short", "--", rel)
    if log.returncode != 0:
        raise RuntimeError(f"git log failed in {repo}: {log.stderr.strip()}")
    snaps = []
    cutoff = dt.date.fromisoformat(until) if until else None
    for line in log.stdout.split("\n"):
        if not line.strip():
            continue
        h, d = line.split()
        date = dt.date.fromisoformat(d)
        if cutoff and date > cutoff:
            continue
        txt = _git(repo, "show", f"{h}:{rel}").stdout
        lines = {x.strip() for x in txt.split("\n")
                 if len(x.strip()) > 15 and not x.strip().startswith("#")}
        snaps.append((date, lines, len(txt)))
    if not snaps:
        raise RuntimeError(f"no commits found for {rel} in {repo}"
                           + (f" until {until}" if until else ""))

    def at(date):
        c = None
        for d, L, n in snaps:
            if d <= date:
                c = L
            else:
                break
        return c

    survival = {}
    for horizon in (7, 30, 60, 90):
        surv = []
        for d, L, n in snaps:
            t = d + dt.timedelta(days=horizon)
            if t > snaps[-1][0] or not L:
                continue
            L2 = at(t)
            surv.append(len(L & L2) / len(L))
        survival[str(horizon)] = {
            "median": round(st.median(surv), 2) if surv else None,
            "n": len(surv),
            "min": round(min(surv), 2) if surv else None,
        }

    cur = snaps[-1][1]
    first = {}
    for d, L, n in snaps:
        for x in L:
            first.setdefault(x, d)
    ages = [(snaps[-1][0] - first[x]).days for x in cur]
    all_lines = set().union(*[L for _, L, _ in snaps])
    return {
        "file": rel,
        "until": until,
        "commits": len(snaps),
        "first_commit": snaps[0][0].isoformat(),
        "last_commit": snaps[-1][0].isoformat(),
        "size_bytes_trajectory": {
            "first": snaps[0][2],
            "last": snaps[-1][2],
            "max": max(n for _, _, n in snaps),
            "min": min(n for _, _, n in snaps),
        },
        "survival_median": survival,
        "current_content_lines": len(cur),
        "median_age_days": st.median(ages) if ages else None,
        "share_older_than_90d": round(sum(a > 90 for a in ages) / len(ages), 2) if ages else None,
        "distinct_lines_ever": len(all_lines),
        "churn_ratio": round(len(all_lines) / len(cur), 2) if cur else None,
        "caveat": "exact-line survival counts an edit as a removal: this measures churn, not wrong facts",
    }


def render(data, fmt_name="terminal"):
    if fmt_name == "json":
        return json.dumps(data, sort_keys=True, indent=1)
    s = data["survival_median"]
    lines = [
        f"decay analysis of {data['file']}"
        + (f" (until {data['until']})" if data["until"] else ""),
        f"commits: {data['commits']}  ({data['first_commit']} -> {data['last_commit']})",
        f"size bytes: first {data['size_bytes_trajectory']['first']:,} -> "
        f"last {data['size_bytes_trajectory']['last']:,} "
        f"(min {data['size_bytes_trajectory']['min']:,}, max {data['size_bytes_trajectory']['max']:,})",
    ]
    for h in ("7", "30", "60", "90"):
        v = s[h]
        lines.append(f"horizon {h:>3}d: median exact-line survival "
                     f"{v['median']} (n={v['n']}, min {v['min']})")
    lines += [
        f"current content lines: {data['current_content_lines']}, "
        f"median age {data['median_age_days']} days, "
        f"{data['share_older_than_90d']} older than 90d",
        f"distinct lines ever {data['distinct_lines_ever']:,} vs current "
        f"{data['current_content_lines']} -> churn {data['churn_ratio']}x",
        f"note: {data['caveat']}",
    ]
    return "\n".join(lines)
