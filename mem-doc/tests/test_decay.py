"""AC #14: decay on a synthetic tmp git repo; --until; no line text leaks;
spike parity (survival.py logic run on the same repo)."""

import datetime as dt
import statistics as st
import subprocess
from pathlib import Path

import pytest

from memdoc.decay import analyze, render

MARKER = "zzqx-secret-line-content"


def _git(cwd, *args, date=None):
    env = {"GIT_AUTHOR_DATE": f"{date}T12:00:00", "GIT_COMMITTER_DATE": f"{date}T12:00:00"} if date else {}
    import os
    full_env = {**os.environ, **env}
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   cwd=cwd, capture_output=True, check=False, env=full_env)


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    """Synthetic history: 4 commits over 100 days with known line churn."""
    root = tmp_path_factory.mktemp("decayrepo")
    _git(root, "init", "-q")
    f = root / "MEMORY.md"
    lines_v1 = [f"- {MARKER} alpha fact number {i} stays stable" for i in range(10)]
    f.write_text("# MEMORY\n" + "\n".join(lines_v1) + "\n")
    _git(root, "add", "-A", date="2026-01-01")
    _git(root, "commit", "-q", "-m", "c1", date="2026-01-01")

    # day 10: 5 lines rewritten
    lines_v2 = lines_v1[:5] + [f"- {MARKER} beta rewritten fact {i} changed today" for i in range(5)]
    f.write_text("# MEMORY\n" + "\n".join(lines_v2) + "\n")
    _git(root, "add", "-A", date="2026-01-11")
    _git(root, "commit", "-q", "-m", "c2", date="2026-01-11")

    # day 40: 5 more new lines appended
    lines_v3 = lines_v2 + [f"- {MARKER} gamma appended fact {i} arrives later" for i in range(5)]
    f.write_text("# MEMORY\n" + "\n".join(lines_v3) + "\n")
    _git(root, "add", "-A", date="2026-02-10")
    _git(root, "commit", "-q", "-m", "c3", date="2026-02-10")

    # day 100: half of everything replaced
    lines_v4 = lines_v3[:7] + [f"- {MARKER} delta final fact {i} replaces the rest" for i in range(8)]
    f.write_text("# MEMORY\n" + "\n".join(lines_v4) + "\n")
    _git(root, "add", "-A", date="2026-04-11")
    _git(root, "commit", "-q", "-m", "c4", date="2026-04-11")
    return root


def test_known_values(repo):
    data = analyze(repo, "MEMORY.md")
    assert data["commits"] == 4
    assert data["current_content_lines"] == 15
    # distinct ever: 10 + 5 + 5 + 8 = 28; churn 28/15
    assert data["distinct_lines_ever"] == 28
    assert data["churn_ratio"] == round(28 / 15, 2)
    # 7d survival: c1 at d8 -> 5/10 survive... compute: snapshots at d0,d10,d40,d100
    # horizon 7: d0+7=d7<=d100 -> at(d7)=v1 -> 1.0; d10+7 -> v2 -> 1.0; d40+7 -> v3 -> 1.0
    assert data["survival_median"]["7"]["median"] == 1.0
    # horizon 30: d0+30 -> v2: |v1 & v2|/|v1| = 5/10 = 0.5 ; d10+30 -> v3 ⊇ v2 -> 1.0;
    # d40+30 -> v3 -> 1.0  => median 1.0
    assert data["survival_median"]["30"]["median"] == 1.0
    assert data["survival_median"]["30"]["min"] == 0.5


def test_until_respected(repo):
    data = analyze(repo, "MEMORY.md", until="2026-02-15")
    assert data["commits"] == 3
    assert data["current_content_lines"] == 15  # v3 has 15 lines


def test_until_before_first_commit_errors(repo):
    with pytest.raises(RuntimeError):
        analyze(repo, "MEMORY.md", until="2025-01-01")


def test_no_line_text_in_output(repo):
    data = analyze(repo, "MEMORY.md")
    for fmt in ("terminal", "json"):
        out = render(data, fmt)
        assert MARKER not in out
        assert "alpha fact" not in out and "delta final" not in out


def test_spike_parity(repo):
    """Run the verbatim survival.py logic on the same repo; compare aggregates."""
    spike = Path(__file__).resolve().parent.parent / ".mastercontrol" / "spikes" / "survival.py"
    if not spike.exists():
        pytest.skip("spike file not present")
    code = spike.read_text().replace('rel="workspace/MEMORY.md"', 'rel="MEMORY.md"')
    r = subprocess.run(["python3", "-c", code], cwd=repo, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = r.stdout
    data = analyze(repo, "MEMORY.md")
    assert f"commits {data['commits']}" in out
    assert f"distinct lines ever {data['distinct_lines_ever']} current {data['current_content_lines']}" in out
    assert f"ratio {data['churn_ratio']}" in out
    for h in ("7", "30", "60", "90"):
        v = data["survival_median"][h]
        if v["median"] is not None:
            assert f"horizon {int(h):3d}d: median exact-line survival {v['median']:.2f}" in out
