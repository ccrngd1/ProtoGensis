"""Shared fixtures: build small git repos with a baseline commit, apply a
"patch" (write new file contents), and run the gate against them."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from swe_gate.cli import ALL_LAYERS, run_gate
from swe_gate.verdict import Verdict


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


class GateRepo:
    def __init__(self, root: Path):
        self.root = root
        _git(root, "init", "-q", "-b", "main")
        _git(root, "config", "user.email", "gate@test")
        _git(root, "config", "user.name", "gate")

    def write(self, rel: str, content: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def commit(self, message: str = "baseline") -> None:
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-qm", message)

    def gate(self, layers=ALL_LAYERS, check_pypi: bool = False) -> Verdict:
        return run_gate(
            str(self.root), baseline="HEAD", layers=layers, check_pypi=check_pypi
        )


@pytest.fixture
def repo(tmp_path: Path) -> GateRepo:
    return GateRepo(tmp_path)


BASELINE_APP = '''\
import sqlite3


def get_user(conn, user_id):
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cur.fetchone()
'''

BASELINE_TESTS = '''\
import sqlite3

from app.db import get_user


def test_get_user_missing():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    assert get_user(conn, 1) is None
    assert get_user(conn, 2) is None
'''


@pytest.fixture
def seeded_repo(repo: GateRepo) -> GateRepo:
    """A repo with a clean baseline: small app + real tests."""
    repo.write("app/__init__.py", "")
    repo.write("app/db.py", BASELINE_APP)
    repo.write("tests/test_db.py", BASELINE_TESTS)
    repo.commit()
    return repo


def layer_result(verdict: Verdict, layer: int):
    return next(lr for lr in verdict.layers if lr.layer == layer)
