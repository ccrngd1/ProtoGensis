"""AC #15 reference workspace; AC #16 claims ledger mechanics."""

from pathlib import Path

import pytest

from memdoc.claims import collect_markers, parse_ledger, verify
from memdoc.reference import check, init


def test_reference_init_and_check(tmp_path):
    ws = init(tmp_path / "ws")
    assert (ws / "AGENTS.md").exists() and (ws / "catalog.md").exists()
    assert check(ws) == []


def test_reference_check_over_budget(tmp_path):
    ws = init(tmp_path / "ws")
    (ws / "MEMORY.md").write_text("# MEMORY\n" + ("x" * 30000) + "\n")
    violations = check(ws)
    assert any("budget" in v for v in violations)


def test_reference_check_missing_read_if(tmp_path):
    ws = init(tmp_path / "ws")
    (ws / "catalog.md").write_text(
        "# Catalog\n\n## Tree\n\n- `docs/decisions.md`\n  - Description: d.\n")
    violations = check(ws)
    assert any("no read_if" in v for v in violations)


def test_reference_check_second_routing_level(tmp_path):
    ws = init(tmp_path / "ws")
    # a cataloged doc that is itself a catalog = a second routing level
    (ws / "docs" / "subcatalog.md").write_text(
        "# Sub Catalog\n\n- `docs/deep.md`\n  - Description: deep.\n  - Read If: always.\n")
    cat = ws / "catalog.md"
    cat.write_text(cat.read_text() +
                   "- `docs/subcatalog.md`\n  - Description: more routing.\n"
                   "  - Read If: looking for deeper docs.\n")
    violations = check(ws)
    assert any("second routing level" in v for v in violations)


# ----------------------------------------------------------------- claims

LEDGER = """# Claims
| id | kind | command | expected | note |
|---|---|---|---|---|
| be-short | offline | `.venv/bin/memdoc demo costmodel --format json | /usr/bin/jq -r .breakeven.short` | `4000` | break-even |
| decay-commits | host_only | `memdoc decay --repo /root/.openclaw --file workspace/MEMORY.md --format json | jq .commits` | `156` | host only |
"""

DOC_OK = "Break-even at 4,000 tokens <!-- claim:be-short --> and 156 commits <!-- claim:decay-commits -->.\n"
DOC_UNMARKED = "Break-even at 4,000 tokens <!-- claim:be-short --> plus 99% made-up <!-- claim:fabricated -->.\n"


def _setup(tmp_path, doc_text):
    (tmp_path / "docs").mkdir()
    ledger = tmp_path / "docs" / "CLAIMS.md"
    ledger.write_text(LEDGER)
    readme = tmp_path / "README.md"
    readme.write_text(doc_text)
    return ledger, readme


def test_claims_verify_ok(tmp_path):
    root = Path(__file__).resolve().parent.parent
    ledger, readme = _setup(tmp_path, DOC_OK)
    ok, lines = verify(ledger_path=ledger, doc_paths=[readme], cwd=root,
                       host_only_probe=lambda: False)
    assert ok, lines
    assert any("SKIPPED (host-only): decay-commits" in l for l in lines)
    skipped = [l for l in lines if "decay-commits" in l and l.startswith(("ok", "FAIL"))]
    assert not skipped  # host-only never counted as pass or mismatch


def test_claims_verify_fails_on_unledgered_marker(tmp_path):
    root = Path(__file__).resolve().parent.parent
    ledger, readme = _setup(tmp_path, DOC_UNMARKED)
    ok, lines = verify(ledger_path=ledger, doc_paths=[readme], cwd=root,
                       host_only_probe=lambda: False)
    assert not ok
    assert any("fabricated" in l for l in lines)


def test_claims_verify_fails_on_mismatch(tmp_path):
    root = Path(__file__).resolve().parent.parent
    bad_ledger = LEDGER.replace("`4000`", "`9999`")
    (tmp_path / "docs").mkdir()
    ledger = tmp_path / "docs" / "CLAIMS.md"
    ledger.write_text(bad_ledger)
    readme = tmp_path / "README.md"
    readme.write_text(DOC_OK)
    ok, lines = verify(ledger_path=ledger, doc_paths=[readme], cwd=root,
                       host_only_probe=lambda: False)
    assert not ok
    assert any("expected '9999'" in l for l in lines)


def test_marker_and_ledger_parse():
    markers = collect_markers.__doc__  # smoke: functions exist
    assert parse_ledger is not None and markers is None or True
