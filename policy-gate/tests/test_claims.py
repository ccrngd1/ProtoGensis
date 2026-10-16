"""Claims ledger tests (AC #22)."""

from policygate import claims


def _write(tmp, name, text):
    p = tmp / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def test_marker_without_row_fails(tmp_path):
    readme = _write(tmp_path, "README.md", "We blocked things <!-- claim:missing -->\n")
    ledger = _write(tmp_path, "docs/CLAIMS.md", "| id | kind | command | expected | research | note |\n")
    ok, lines = claims.verify(ledger_path=ledger, doc_paths=[readme], cwd=tmp_path,
                              host_probe=lambda: False)
    assert not ok
    assert any("has no ledger entry" in l for l in lines)


def test_naked_percentage_fails(tmp_path):
    readme = _write(tmp_path, "README.md", "It blocked 80% of actions.\n")
    ledger = _write(tmp_path, "docs/CLAIMS.md", "| id | kind | command | expected | research | note |\n")
    ok, lines = claims.verify(ledger_path=ledger, doc_paths=[readme], cwd=tmp_path,
                              host_probe=lambda: False)
    assert not ok
    assert any("naked number" in l for l in lines)


def test_exempt_patterns_pass(tmp_path):
    readme = _write(tmp_path, "README.md",
                    "Method after NOMOS (arXiv 2610.11030), v2 2026-10-14, week W42, commit f84fecd8.\n")
    ledger = _write(tmp_path, "docs/CLAIMS.md", "| id | kind | command | expected | research | note |\n")
    ok, lines = claims.verify(ledger_path=ledger, doc_paths=[readme], cwd=tmp_path,
                              host_probe=lambda: False)
    assert ok, lines


def test_offline_claim_runs_and_matches(tmp_path):
    readme = _write(tmp_path, "README.md", "Blocked nine of ten <!-- claim:nine -->\n")
    ledger = _write(tmp_path, "docs/CLAIMS.md",
                    "| id | kind | command | expected | research | note |\n"
                    "|---|---|---|---|---|---|\n"
                    "| nine | offline | `echo 9` | `9` |  | demo |\n")
    ok, lines = claims.verify(ledger_path=ledger, doc_paths=[readme], cwd=tmp_path,
                              host_probe=lambda: False)
    assert ok, lines


def test_mismatch_fails(tmp_path):
    readme = _write(tmp_path, "README.md", "Blocked nine <!-- claim:nine -->\n")
    ledger = _write(tmp_path, "docs/CLAIMS.md",
                    "| id | kind | command | expected | research | note |\n"
                    "|---|---|---|---|---|---|\n"
                    "| nine | offline | `echo 7` | `9` |  | demo |\n")
    ok, lines = claims.verify(ledger_path=ledger, doc_paths=[readme], cwd=tmp_path,
                              host_probe=lambda: False)
    assert not ok


def test_research_delta_without_results_row_fails(tmp_path):
    readme = _write(tmp_path, "README.md", "value <!-- claim:v -->\n")
    ledger = _write(tmp_path, "docs/CLAIMS.md",
                    "| id | kind | command | expected | research | note |\n"
                    "|---|---|---|---|---|---|\n"
                    "| v | offline | `echo 47` | `47` | `80` | parity |\n")
    _write(tmp_path, "docs/RESULTS.md", "# Results\n\nNo delta table here.\n")
    ok, lines = claims.verify(ledger_path=ledger, doc_paths=[readme], cwd=tmp_path,
                              host_probe=lambda: False)
    assert not ok
    assert any("no RESULTS.md delta row" in l for l in lines)


def test_research_delta_with_results_row_passes(tmp_path):
    readme = _write(tmp_path, "README.md", "value <!-- claim:v -->\n")
    ledger = _write(tmp_path, "docs/CLAIMS.md",
                    "| id | kind | command | expected | research | note |\n"
                    "|---|---|---|---|---|---|\n"
                    "| v | offline | `echo 47` | `47` | `80` | parity |\n")
    _write(tmp_path, "docs/RESULTS.md",
           "# Results\n\n## Deltas vs research\n\n| id | research | actual |\n|---|---|---|\n| v | 80 | 47 |\n")
    ok, lines = claims.verify(ledger_path=ledger, doc_paths=[readme], cwd=tmp_path,
                              host_probe=lambda: False)
    assert ok, lines


def test_host_only_skipped_offhost(tmp_path):
    readme = _write(tmp_path, "README.md", "host value <!-- claim:h -->\n")
    ledger = _write(tmp_path, "docs/CLAIMS.md",
                    "| id | kind | command | expected | research | note |\n"
                    "|---|---|---|---|---|---|\n"
                    "| h | host_only | `echo 123` | `PENDING_HOST` |  | host |\n")
    ok, lines = claims.verify(ledger_path=ledger, doc_paths=[readme], cwd=tmp_path,
                              host_probe=lambda: False)
    assert ok
    assert any("SKIPPED (host-only): h" in l for l in lines)


def test_on_host_requires_pg_host_tests_env(tmp_path, monkeypatch):
    """AC #22 phase 3: "on-host" = PG_HOST_TESTS=1 AND readable /root/.openclaw,
    exactly like tests/conftest.py. Root with a readable archive but no opt-in
    env var stays off-host, so PENDING_HOST rows SKIP, never FAIL."""
    monkeypatch.delenv("PG_HOST_TESTS", raising=False)
    # even if /root/.openclaw were readable, the env gate keeps this off-host
    assert claims._host_readable() is False
    readme = _write(tmp_path, "README.md", "host value <!-- claim:h -->\n")
    ledger = _write(tmp_path, "docs/CLAIMS.md",
                    "| id | kind | command | expected | research | note |\n"
                    "|---|---|---|---|---|---|\n"
                    "| h | host_only | `echo 123` | `PENDING_HOST` |  | host |\n")
    ok, lines = claims.verify(ledger_path=ledger, doc_paths=[readme], cwd=tmp_path)
    assert ok
    assert any("SKIPPED (host-only): h" in l for l in lines)


def test_pending_rerun_skipped_offhost_fails_onhost(tmp_path):
    """PENDING_RERUN behaves exactly like PENDING_HOST (phase 4)."""
    readme = _write(tmp_path, "README.md", "rerun value <!-- claim:rr -->\n")
    ledger = _write(tmp_path, "docs/CLAIMS.md",
                    "| id | kind | command | expected | research | note |\n"
                    "|---|---|---|---|---|---|\n"
                    "| rr | host_only | `echo 5` | `PENDING_RERUN` |  | rerun |\n")
    ok, lines = claims.verify(ledger_path=ledger, doc_paths=[readme], cwd=tmp_path,
                              host_probe=lambda: False)
    assert ok
    assert any("SKIPPED (host-only): rr" in l for l in lines)
    ok, lines = claims.verify(ledger_path=ledger, doc_paths=[readme], cwd=tmp_path,
                              host_probe=lambda: True)
    assert not ok
    assert any("PENDING_RERUN expected value on-host" in l for l in lines)


def test_pending_host_fails_on_host(tmp_path):
    readme = _write(tmp_path, "README.md", "host value <!-- claim:h -->\n")
    ledger = _write(tmp_path, "docs/CLAIMS.md",
                    "| id | kind | command | expected | research | note |\n"
                    "|---|---|---|---|---|---|\n"
                    "| h | host_only | `echo 123` | `PENDING_HOST` |  | host |\n")
    ok, lines = claims.verify(ledger_path=ledger, doc_paths=[readme], cwd=tmp_path,
                              host_probe=lambda: True)
    assert not ok
    assert any("PENDING_HOST expected value on-host" in l for l in lines)
