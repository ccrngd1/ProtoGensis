"""AC: seeded shell=True interpolation fails the gate with Layer 3
attribution; pre-existing findings and MEDIUM/LOW severities never gate."""

import shutil

import pytest

from swe_gate.verdict import EXIT_FAIL

from .conftest import layer_result

scanners_missing = shutil.which("bandit") is None and shutil.which("semgrep") is None

SHELL_TRUE_APP = '''\
import subprocess


def archive(path):
    subprocess.run(f"tar czf backup.tgz {path}", shell=True)
'''

FSTRING_SQL_APP = '''\
import sqlite3


def get_user(conn, user_id):
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE id = {user_id}")
    return cur.fetchone()
'''


@pytest.mark.skipif(scanners_missing, reason="bandit/semgrep not installed")
def test_shell_true_interpolation_blocks(seeded_repo):
    seeded_repo.write("app/backup.py", SHELL_TRUE_APP)
    verdict = seeded_repo.gate(layers=(3,))
    assert verdict.exit_code == EXIT_FAIL
    l3 = layer_result(verdict, 3)
    assert l3.status == "fail"
    assert any("shell" in f.rule_id or "subprocess" in f.rule_id for f in l3.blocking)


@pytest.mark.skipif(scanners_missing, reason="bandit/semgrep not installed")
def test_fstring_sql_blocks(seeded_repo):
    seeded_repo.write("app/db.py", FSTRING_SQL_APP)
    verdict = seeded_repo.gate(layers=(3,))
    assert verdict.exit_code == EXIT_FAIL
    assert any(
        f.rule_id == "semgrep-ai-fstring-sql" for f in layer_result(verdict, 3).blocking
    )


@pytest.mark.skipif(scanners_missing, reason="bandit/semgrep not installed")
def test_preexisting_vulnerability_does_not_block(seeded_repo):
    """Delta principle: HIGH finding already at baseline never gates."""
    seeded_repo.write("app/backup.py", SHELL_TRUE_APP)
    seeded_repo.commit("pre-existing debt")
    seeded_repo.write("app/version.py", "VERSION = 2\n")
    verdict = seeded_repo.gate(layers=(3,))
    assert verdict.exit_code == 0
    assert layer_result(verdict, 3).status == "pass"


@pytest.mark.skipif(scanners_missing, reason="bandit/semgrep not installed")
def test_medium_low_findings_are_advisory(seeded_repo):
    # bandit B608 flags "..." % x SQL construction as MEDIUM; our HIGH semgrep
    # rules do not match a plain '%' format on a variable-built query string.
    seeded_repo.write(
        "app/report.py",
        'def q(table):\n    return "SELECT * FROM %s" % table\n',
    )
    verdict = seeded_repo.gate(layers=(3,))
    l3 = layer_result(verdict, 3)
    assert not l3.blocking
    assert verdict.exit_code == 0
