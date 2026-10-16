"""Demo tests: determinism, banners, offline (AC #12, #13, #17, #25)."""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent


def _run(args, home=None):
    env = dict(os.environ)
    if home:
        env["HOME"] = home
    return subprocess.run([sys.executable, "-m", "policygate.cli", *args],
                          cwd=REPO, capture_output=True, text=True, env=env)


def test_demo_all_byte_identical(tmp_path):
    h = str(tmp_path / "home")
    os.makedirs(h)
    r1 = _run(["demo", "all", "--format", "json"], home=h)
    r2 = _run(["demo", "all", "--format", "json"])
    assert r1.returncode == 0
    assert r1.stdout == r2.stdout


def test_demo_all_banner_counts():
    r = _run(["demo", "all"])
    assert r.stdout.count("SYNTHETIC FIXTURE: mechanism demo, not results from real transcripts") == 4
    assert r.stdout.count("RECONSTRUCTED FIXTURE") == 1


def test_adversarial_zero_accepted():
    r = _run(["demo", "adversarial", "--format", "json"])
    d = json.loads(r.stdout)
    assert d["accepted_authorizations"] == 0
    assert d["cases"] >= 12


def test_readings_three_totals():
    r = _run(["demo", "readings", "--format", "json"])
    d = json.loads(r.stdout)
    assert sorted(d["totals"].keys()) == ["lenient", "plan", "strict"]


def test_amend_overlay_not_written():
    r = _run(["demo", "amend", "--format", "json"])
    d = json.loads(r.stdout)
    assert d["items_closed"] >= 1
    assert d["overlay_written_to_policy_repo"] is False
