"""AC: seeded test-tampering patch fails the gate with Layer 0 attribution."""

from swe_gate.verdict import EXIT_FAIL

from .conftest import layer_result

WEAKENED_TESTS = '''\
import sqlite3

from app.db import get_user


def test_get_user_missing():
    assert True
'''

SKIPPED_TESTS = '''\
import sqlite3

import pytest

from app.db import get_user


@pytest.mark.skip(reason="flaky")
def test_get_user_missing():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    assert get_user(conn, 1) is None
    assert get_user(conn, 2) is None
'''


def test_weakened_assertions_block(seeded_repo):
    seeded_repo.write("tests/test_db.py", WEAKENED_TESTS)
    verdict = seeded_repo.gate(layers=(0,))
    assert verdict.exit_code == EXIT_FAIL
    l0 = layer_result(verdict, 0)
    assert l0.status == "fail"
    rules = {f.rule_id for f in l0.blocking}
    assert "tamper-assert-removed" in rules
    assert "tamper-trivial-assert" in rules


def test_added_skip_blocks(seeded_repo):
    seeded_repo.write("tests/test_db.py", SKIPPED_TESTS)
    verdict = seeded_repo.gate(layers=(0,))
    assert verdict.exit_code == EXIT_FAIL
    l0 = layer_result(verdict, 0)
    assert any(f.rule_id == "tamper-skip-added" for f in l0.blocking)


def test_deleted_test_blocks(seeded_repo):
    seeded_repo.write("tests/test_db.py", "import sqlite3\n\nfrom app.db import get_user\n")
    verdict = seeded_repo.gate(layers=(0,))
    assert verdict.exit_code == EXIT_FAIL
    l0 = layer_result(verdict, 0)
    assert any(f.rule_id == "tamper-test-deleted" for f in l0.blocking)


def test_untouched_tests_pass(seeded_repo):
    seeded_repo.write("app/db.py", "import sqlite3\n\n\ndef get_user(conn, user_id):\n    return None\n")
    verdict = seeded_repo.gate(layers=(0,))
    assert verdict.exit_code == 0
    assert layer_result(verdict, 0).status == "pass"


def test_new_test_file_with_real_assertions_passes(seeded_repo):
    seeded_repo.write(
        "tests/test_more.py",
        "def test_math():\n    assert 1 + 1 == 2\n",
    )
    verdict = seeded_repo.gate(layers=(0,))
    assert verdict.exit_code == 0
