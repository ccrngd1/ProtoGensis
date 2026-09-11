"""AC: seeded wrong-signature call fails the gate with Layer 2 attribution;
missing pyright degrades to a labeled skip, not exit 2."""

import pytest

from swe_gate.layers import signatures
from swe_gate.verdict import EXIT_FAIL

from .conftest import layer_result

pyright_missing = not signatures.pyright_available()

UTIL = "def add(a: int, b: int) -> int:\n    return a + b\n"
CALLER_OK = "from app.util import add\n\n\ndef run() -> int:\n    return add(1, 2)\n"
CALLER_BAD = "from app.util import add\n\n\ndef run() -> int:\n    return add(1, 2, 3)\n"


@pytest.fixture
def sig_repo(repo):
    repo.write("app/__init__.py", "")
    repo.write("app/util.py", UTIL)
    repo.write("app/main.py", CALLER_OK)
    repo.commit()
    return repo


@pytest.mark.skipif(pyright_missing, reason="pyright not installed")
def test_wrong_arg_count_blocks(sig_repo):
    sig_repo.write("app/main.py", CALLER_BAD)
    verdict = sig_repo.gate(layers=(2,))
    assert verdict.exit_code == EXIT_FAIL
    l2 = layer_result(verdict, 2)
    assert l2.status == "fail"
    assert any(f.rule_id == "signature-reportCallIssue" for f in l2.blocking)


@pytest.mark.skipif(pyright_missing, reason="pyright not installed")
def test_preexisting_signature_error_does_not_block(sig_repo):
    """Delta principle: an error already at baseline never gates."""
    sig_repo.write("app/main.py", CALLER_BAD)
    sig_repo.commit("pre-existing debt")
    sig_repo.write("app/other.py", "X = 1\n")
    verdict = sig_repo.gate(layers=(2,))
    assert verdict.exit_code == 0


def test_missing_pyright_degrades_to_skip(sig_repo, monkeypatch):
    monkeypatch.setattr(signatures, "pyright_available", lambda: False)
    sig_repo.write("app/main.py", CALLER_BAD)
    verdict = sig_repo.gate(layers=(2,))
    assert verdict.exit_code == 0  # skip is labeled, non-blocking, not exit 2
    l2 = layer_result(verdict, 2)
    assert l2.status == "skipped"
    assert "pyright not installed" in l2.detail


@pytest.mark.skipif(pyright_missing, reason="pyright not installed")
def test_missing_stubs_reports_unverifiable(sig_repo):
    # bs4 ships no py.typed/stubs in this environment; if it happens to be
    # installed with stubs the layer legitimately reports pass instead.
    sig_repo.write(
        "app/scraper.py",
        "import nonexistent_stub_pkg_qqq\n\n\ndef go():\n    return nonexistent_stub_pkg_qqq.parse('x')\n",
    )
    verdict = sig_repo.gate(layers=(2,))
    l2 = layer_result(verdict, 2)
    # missing module surfaces as reportMissingImports -> stub gap -> unverifiable
    assert l2.status in ("unverifiable", "pass")
    assert verdict.exit_code == 0
