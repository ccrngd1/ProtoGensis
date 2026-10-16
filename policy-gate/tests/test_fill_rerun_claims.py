"""scripts/fill_rerun_claims.py: PENDING_RERUN -> command value in the ledger
and in marker-carrying doc lines; BLOG title rule printed. SYNTHETIC tree."""

import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(__file__))
SCRIPT = os.path.join(REPO, "scripts", "fill_rerun_claims.py")

LEDGER = """| id | kind | command | expected | research | note |
|---|---|---|---|---|---|
| amb-total | host_only | `echo 42` | `PENDING_RERUN` |  | rerun |
| holes-vs-agents | host_only | `echo holes=9 unauthorized=13 holes_gt_agents=false` | `PENDING_RERUN` |  | title |
| untouched | host_only | `echo 5` | `5` |  | already filled |
"""

README = """Items: <!-- claim:amb-total --> PENDING_RERUN items by kind.
Other line without a marker stays PENDING_RERUN untouched? no such line.
"""


def _tree(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "CLAIMS.md").write_text(LEDGER)
    (tmp_path / "README.md").write_text(README)
    (tmp_path / "BLOG.md").write_text("no markers here\n")
    return tmp_path


def _run(tmp_path, *args):
    return subprocess.run([sys.executable, SCRIPT, "--repo", str(tmp_path), *args],
                          capture_output=True, text=True)


def test_fills_ledger_and_docs(tmp_path):
    _tree(tmp_path)
    r = _run(tmp_path)
    assert r.returncode == 0, r.stderr
    ledger = (tmp_path / "docs" / "CLAIMS.md").read_text()
    assert "| amb-total | host_only | `echo 42` | `42` |" in ledger
    assert "PENDING_RERUN" not in ledger
    readme = (tmp_path / "README.md").read_text()
    assert "<!-- claim:amb-total --> 42 items by kind." in readme
    # rows already holding a value are untouched
    assert "| untouched | host_only | `echo 5` | `5` |" in ledger


def test_title_rule_printed(tmp_path):
    _tree(tmp_path)
    r = _run(tmp_path)
    assert "holes-vs-agents does NOT hold" in r.stdout
    assert "alternate title" in r.stdout


def test_dry_run_edits_nothing(tmp_path):
    _tree(tmp_path)
    r = _run(tmp_path, "--dry-run")
    assert r.returncode == 0
    assert "PENDING_RERUN" in (tmp_path / "docs" / "CLAIMS.md").read_text()
    assert "PENDING_RERUN" in (tmp_path / "README.md").read_text()


def test_failing_command_exits_1(tmp_path):
    _tree(tmp_path)
    (tmp_path / "docs" / "CLAIMS.md").write_text(
        "| id | kind | command | expected | research | note |\n"
        "|---|---|---|---|---|---|\n"
        "| bad | host_only | `false` | `PENDING_RERUN` |  | fails |\n")
    r = _run(tmp_path)
    assert r.returncode == 1
    assert "FAIL" in r.stderr
