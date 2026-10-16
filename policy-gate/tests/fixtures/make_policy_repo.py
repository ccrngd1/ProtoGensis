#!/usr/bin/env python3
"""Build the deterministic synthetic policy repo used by tests and demos.

Five commits at fixed times (fixed author/committer dates, so shas are stable
across machines). The policy is CABAL-*shaped* and builder-written: paraphrased
rule shapes, not copied files. SYNTHETIC: no real content.

  commit 1 (2026-02-01T00:00:00Z): base policy, no quiet-hours rule
  commit 2 (2026-02-20T00:00:00Z): quiet-hours rule + protected-jobs block added
  commit 3 (2026-03-15T00:00:00Z): the legacy-tooling rule is removed
  commit 4 (2026-05-01T00:00:00Z): cron/jobs.json is DELETED (phase 2a Bug 2:
      `log -1 --before` returns this commit; the source is ABSENT/deleted)
  commit 5 (2026-06-01T00:00:00Z): cron/jobs.json is re-added

Commits 4/5 are after every pre-existing probe time, so commits 1-3 and all
phase-1 probes are unchanged.

Usage: python tests/fixtures/make_policy_repo.py <target-dir>
"""

import json
import os
import subprocess
import sys

COMMITS = [
    ("2026-02-01T00:00:00Z", "c1 base policy"),
    ("2026-02-20T00:00:00Z", "c2 add quiet hours + protected jobs"),
    ("2026-03-15T00:00:00Z", "c3 remove legacy tooling rule"),
    ("2026-05-01T00:00:00Z", "c4 delete cron jobs file"),
    ("2026-06-01T00:00:00Z", "c5 re-add cron jobs file"),
]

BASE_AGENTS_V1 = """# Synthetic Base Agent Policy

## Operating Rules

### Forbidden Actions (without explicit CC instruction):
- Disabling, deleting, or modifying scheduled jobs
- Restarting or stopping services
- Changing gateway configuration

### Automation
- Automation is controlled by CC or the main agent.
- You do NOT manage your own automation.

### Legacy tooling
- Never invoke the legacy deploy script directly.

### Memory discipline
- Never edit MEMORY.md.
- Write it down: always update memory files after significant work.

### Safety
- Checkpoint first: no infra change without a backup. No rollback path = don't start.
"""

BASE_AGENTS_V2 = BASE_AGENTS_V1 + """
### Quiet hours
- No autonomous infra work between midnight and 08:00 UTC.
"""

# v3: the "Legacy tooling" rule is removed
BASE_AGENTS_V3 = BASE_AGENTS_V2.replace(
    """### Legacy tooling
- Never invoke the legacy deploy script directly.

""", "")

MEMORY_V1 = """# Synthetic Agent Memory

## Notes
- Routine notes live here.
"""

MEMORY_V2 = """# Synthetic Agent Memory

## DO NOT TOUCH - Protected Jobs
**These jobs are PERMANENT. Do NOT disable or delete them:**
- 5ff9ece3-0000-4000-8000-000000000001 (morning synthetic job)
- d5c8def3-0000-4000-8000-000000000002 (evening synthetic job)

## Notes
- Routine notes live here.
"""

SOUL = """# Synthetic Soul

## Identity
- A careful synthetic test agent.

```
openclaw cron disable example-should-not-parse
```
"""

CRON_JOBS = {
    "jobs": [
        {
            "id": "aaaa1111-0000-4000-8000-000000000003",
            "agentId": "synthetic-agent",
            "payload": {"message": "Nightly digest. Do NOT execute queued items in this session; report only."},
        }
    ]
}


def git(repo, *args, date=None):
    env = dict(os.environ)
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    subprocess.run(
        ["git", "-c", "user.name=policygate", "-c", "user.email=policygate@localhost",
         "-C", repo, *args],
        check=True, capture_output=True, env=env,
    )


def write(repo, rel, content):
    p = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)


def build(target):
    os.makedirs(target, exist_ok=True)
    git(target, "init", "-q", "-b", "main")

    # commit 1
    write(target, "global/BASE-AGENTS.md", BASE_AGENTS_V1)
    write(target, "workspace/AGENTS.md", "# Synthetic workspace agents\n\n## Rules\n- Follow the base policy.\n")
    write(target, "workspace/SOUL.md", SOUL)
    write(target, "workspace/MEMORY.md", MEMORY_V1)
    write(target, "cron/jobs.json", json.dumps(CRON_JOBS, indent=2, sort_keys=True))
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", COMMITS[0][1], date=COMMITS[0][0])

    # commit 2
    write(target, "global/BASE-AGENTS.md", BASE_AGENTS_V2)
    write(target, "workspace/MEMORY.md", MEMORY_V2)
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", COMMITS[1][1], date=COMMITS[1][0])

    # commit 3
    write(target, "global/BASE-AGENTS.md", BASE_AGENTS_V3)
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", COMMITS[2][1], date=COMMITS[2][0])

    # commit 4: delete cron/jobs.json (ABSENT/deleted window)
    git(target, "rm", "-q", "cron/jobs.json")
    git(target, "commit", "-q", "-m", COMMITS[3][1], date=COMMITS[3][0])

    # commit 5: re-add it
    write(target, "cron/jobs.json", json.dumps(CRON_JOBS, indent=2, sort_keys=True))
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", COMMITS[4][1], date=COMMITS[4][0])
    return target


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: make_policy_repo.py <target-dir>", file=sys.stderr)
        sys.exit(2)
    build(sys.argv[1])
    print(sys.argv[1])
