"""AC #16 honesty gates, enforced by tests."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from memdoc.claims import CLAIM_RE, collect_markers, parse_ledger, verify

ROOT = Path(__file__).resolve().parent.parent

ARXIV_ALLOWLIST = {
    "2402.17753", "2410.10813", "2507.05257", "2602.16313", "2605.06527",
    "2606.27472", "2606.24775", "2609.05339", "2607.17598", "2610.02472",
    "2510.04618", "2504.19413", "2606.12329", "2606.23127", "2602.11988",
    "2601.20404", "2609.31587", "2511.12884", "2307.03172", "2603.07670",
}

BANNED = re.compile(
    r"docs beat RAG|RAG is dead|memory is solved|first (benchmark|tool|library)|"
    r"only benchmark|first-ever|nobody has (measured|benchmarked)", re.IGNORECASE)


def _doc_texts():
    out = {}
    for name in ("README.md", "BLOG.md"):
        out[name] = (ROOT / name).read_text(encoding="utf-8")
    for p in sorted((ROOT / "docs").glob("*.md")):
        out[f"docs/{p.name}"] = p.read_text(encoding="utf-8")
    return out


def test_claims_verify_passes_on_committed_docs():
    ok, lines = verify(cwd=ROOT, host_only_probe=lambda: False)
    assert ok, "\n".join(lines)


def test_claims_verify_fails_on_planted_unmarked_number(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text((ROOT / "README.md").read_text() +
                      "\nSuccess rate was 97% <!-- claim:planted-nonsense -->.\n")
    ok, lines = verify(ledger_path=ROOT / "docs" / "CLAIMS.md",
                       doc_paths=[readme], cwd=ROOT, host_only_probe=lambda: False)
    assert not ok
    assert any("planted-nonsense" in l for l in lines)


def test_pending_live_run_present_while_results_empty():
    results = ROOT / "results"
    nontrivial = [p for p in results.iterdir() if p.name != ".gitkeep"] if results.exists() else []
    if nontrivial:
        pytest.skip("live results exist")
    assert "pending live run" in (ROOT / "README.md").read_text()
    assert "pending live run" in (ROOT / "BLOG.md").read_text()


def test_no_accuracy_claim_markers_without_live_run():
    results = ROOT / "results"
    nontrivial = [p for p in results.iterdir() if p.name != ".gitkeep"] if results.exists() else []
    if nontrivial:
        pytest.skip("live results exist")
    ledger = parse_ledger(ROOT / "docs" / "CLAIMS.md")
    markers = collect_markers([ROOT / "README.md", ROOT / "BLOG.md"])
    for cid in markers:
        kind = ledger.get(cid, {}).get("kind", "")
        assert kind != "accuracy", f"accuracy claim {cid} with no live run"


def test_banned_phrases_absent():
    for name, text in _doc_texts().items():
        m = BANNED.search(text)
        assert m is None, f"banned phrase {m.group(0)!r} in {name}"
    for p in (ROOT / "memdoc").rglob("*.py"):
        m = BANNED.search(p.read_text(encoding="utf-8"))
        assert m is None, f"banned phrase {m.group(0)!r} in {p}"


def test_arxiv_ids_in_allowlist():
    pat = re.compile(r"\b\d{4}\.\d{5}\b")
    for name in ("README.md", "BLOG.md"):
        for aid in pat.findall((ROOT / name).read_text(encoding="utf-8")):
            assert aid in ARXIV_ALLOWLIST, f"{aid} in {name} not on the allowlist"


def test_license_is_mit():
    assert "MIT License" in (ROOT / "LICENSE").read_text(encoding="utf-8")


def test_third_party_notices():
    text = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "Operator Memory" in text and "BSD-3" in text


def test_real_clone_url():
    assert "ccrngd1/ProtoGensis" in (ROOT / "README.md").read_text(encoding="utf-8")
    bad = re.compile(r"github\.com/protogensis/mem-doc", re.IGNORECASE)
    for name, text in _doc_texts().items():
        assert not bad.search(text), name


def test_mock_outputs_never_say_accuracy():
    """Mock surfaces label delivery as mechanism, never accuracy (Trap 12)."""
    from memdoc.demos import demo_costmodel
    from memdoc.report import build_report, render
    # the only 'accuracy' use allowed in report.py is the live-mode label
    src = (ROOT / "memdoc" / "report.py").read_text(encoding="utf-8")
    assert 'if mode == "mock" else "accuracy"' in src
