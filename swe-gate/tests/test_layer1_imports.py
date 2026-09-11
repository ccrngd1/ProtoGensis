"""AC: seeded hallucinated import fails the gate with Layer 1 attribution,
and the offline default never touches the network."""

import pytest

from swe_gate.layers import imports as imports_layer
from swe_gate.verdict import EXIT_FAIL

from .conftest import layer_result

HALLUCINATED_APP = '''\
import sqlite3

import turbovalidatorx_nonexistent


def get_user(conn, user_id):
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return turbovalidatorx_nonexistent.clean(cur.fetchone())
'''


def test_hallucinated_import_blocks(seeded_repo):
    seeded_repo.write("app/db.py", HALLUCINATED_APP)
    verdict = seeded_repo.gate(layers=(1,))
    assert verdict.exit_code == EXIT_FAIL
    l1 = layer_result(verdict, 1)
    assert l1.status == "fail"
    finding = next(f for f in l1.blocking if f.rule_id == "import-hallucinated")
    assert "turbovalidatorx_nonexistent" in finding.message
    assert "unverified" in finding.message  # offline default is labeled


def test_offline_default_never_calls_pypi(seeded_repo, monkeypatch):
    def explode(name):
        raise AssertionError("network touched without --check-pypi")

    monkeypatch.setattr(imports_layer, "check_pypi", explode)
    seeded_repo.write("app/db.py", HALLUCINATED_APP)
    verdict = seeded_repo.gate(layers=(1,))
    assert verdict.exit_code == EXIT_FAIL  # still blocks, just unverified


def test_pypi_unreachable_stays_blocking(seeded_repo, monkeypatch):
    monkeypatch.setattr(imports_layer, "check_pypi", lambda name: "unreachable")
    seeded_repo.write("app/db.py", HALLUCINATED_APP)
    verdict = seeded_repo.gate(layers=(1,), check_pypi=True)
    assert verdict.exit_code == EXIT_FAIL
    finding = layer_result(verdict, 1).blocking[0]
    assert "unreachable" in finding.message


def test_pypi_exists_downgrades_to_advisory(seeded_repo, monkeypatch):
    monkeypatch.setattr(imports_layer, "check_pypi", lambda name: "exists")
    seeded_repo.write("app/db.py", HALLUCINATED_APP)
    verdict = seeded_repo.gate(layers=(1,), check_pypi=True)
    assert verdict.exit_code == 0
    l1 = layer_result(verdict, 1)
    assert l1.status == "pass"
    assert any(f.rule_id == "import-not-installed" for f in l1.advisory)


def test_stdlib_and_repo_local_imports_pass(seeded_repo):
    seeded_repo.write(
        "app/service.py",
        "import json\nimport os.path\n\nfrom app.db import get_user\nfrom . import db\n",
    )
    verdict = seeded_repo.gate(layers=(1,))
    assert verdict.exit_code == 0


def test_preexisting_bad_import_does_not_block(seeded_repo):
    """Delta principle: hallucinated import already at baseline is out of scope."""
    seeded_repo.write("app/legacy.py", "import ghost_package_qqq\n")
    seeded_repo.commit("legacy debt")
    seeded_repo.write("app/legacy.py", "import ghost_package_qqq\n\nVERSION = 2\n")
    verdict = seeded_repo.gate(layers=(1,))
    assert verdict.exit_code == 0
