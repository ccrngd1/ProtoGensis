"""JSONL run-log events (AC #4) with an injectable clock.

Event types:
  run_header   run_id, mode, prereg_hash, git_head, config echo
  call         {run_id, arm, size, storyline, seed, session, call_idx,
                inputTokens, cacheReadInputTokens, cacheWriteInputTokens,
                outputTokens, source, call_type}
  probe        probe outcome + delivery flags + cause code
  write_fidelity  per write session: canary present / superseded handled
  cell         health signals per (arm, size, seed, storyline)
  run_end      summary counters

Mock logs contain no timestamps, absolute paths, PIDs, or tmpdir names, so the
same seeds give byte-identical logs.
"""

import hashlib
import json
import subprocess
from pathlib import Path


def deterministic_run_id(payload: dict) -> str:
    s = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "mock-" + hashlib.sha256(s.encode()).hexdigest()[:12]


def git_head(repo_dir) -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir,
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "no-git"


class RunLog:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "w", encoding="utf-8")

    def write(self, event: dict):
        self._fh.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")

    def close(self):
        self._fh.flush()
        self._fh.close()


def read_events(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
