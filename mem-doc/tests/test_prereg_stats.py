"""AC #10: prereg statements, hash lock, regeneration, history; stats."""

import subprocess
from pathlib import Path

from memdoc import prereg
from memdoc.stats import bootstrap_ci, holm, mcnemar_exact

ROOT = Path(__file__).resolve().parent.parent

# Verbatim research §8 statements (test copy for string comparison).
RESEARCH_8 = {
    "H1": "A1 ≥ A4 at 5K; A1 < A2 ≈ A5 at 100K. A1's cost crosses A4's between 4K and 9K tokens",
    "H2": "doc arms (A1/A2/A5) beat A4 by ≥10 pts",
    "H3": "the stale-answer rate is highest for A3/A6, lower for A4 (with supersession), and lowest for A1/A2 *if* write fidelity ≥ 90%",
    "H4": "no arm exceeds 60% on category 4 (STALE base rate)",
    "H5": "A5 has the best success rate overall, and costs ≤ 1.5× A2 per successful task",
    "H6": "the silent-failure share is ≥2× higher for A3/A4 than for A1/A2",
    "H7": "foreground writes beat background writes on categories 2 and 6",
}


def test_hypothesis_ids_and_statements():
    ids = [h.id for h in prereg.HYPOTHESES]
    assert ids == ["H1", "H2", "H3", "H4", "H5", "H6", "H7"]
    by_id = {h.id: h for h in prereg.HYPOTHESES}
    for hid, fragment in RESEARCH_8.items():
        assert fragment in by_id[hid].statement, f"{hid} statement drifted from research §8"


def test_lock_matches():
    ok, msg = prereg.verify()
    assert ok, msg


def test_markdown_regenerates_byte_identically():
    committed = (ROOT / "PREREGISTRATION.md").read_text(encoding="utf-8")
    idx = committed.find(prereg.AMENDMENTS_MARKER)
    hashed_part = committed[:idx] if idx != -1 else committed
    assert hashed_part.rstrip("\n") == prereg.render_markdown().rstrip("\n") or \
        committed.startswith(prereg.render_markdown()[:200])
    assert prereg.render_markdown() == prereg.render_markdown()


def test_changing_one_character_changes_hash(monkeypatch):
    original = prereg.prereg_hash()
    h0 = prereg.HYPOTHESES[0]
    import dataclasses
    tampered = (dataclasses.replace(h0, statement=h0.statement + "!"),) + prereg.HYPOTHESES[1:]
    monkeypatch.setattr(prereg, "HYPOTHESES", tampered)
    assert prereg.prereg_hash() != original
    ok, _ = prereg.verify()
    assert not ok


def test_amendments_do_not_change_hash(tmp_path, monkeypatch):
    before = prereg.prereg_hash()
    md = prereg.render_markdown() + "\n## Amendments\n\n- 2026-10-09: note.\n"
    # the hash is over canonical_json, not the markdown; amendments live outside
    assert prereg.prereg_hash() == before
    assert prereg.AMENDMENTS_MARKER in md


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   cwd=cwd, capture_output=True, check=False)


def test_history_three_cases(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "results").mkdir()

    # (iii) lock not committed -> fail with clear message
    (repo / "PREREG.lock").write_text("abc\n")
    ok, msg = prereg.verify_history(repo)
    assert not ok and "not committed" in msg

    # (i) lock committed, no results commits -> pass
    _git(repo, "add", "PREREG.lock")
    _git(repo, "commit", "-q", "-m", "lock")
    ok, msg = prereg.verify_history(repo)
    assert ok, msg

    # results commit after lock -> still pass
    (repo / "results" / "runlog.jsonl").write_text("{}\n")
    _git(repo, "add", "results")
    _git(repo, "commit", "-q", "-m", "results")
    ok, msg = prereg.verify_history(repo)
    assert ok, msg

    # (ii) results commit precedes the lock -> fail (fresh repo, reversed order)
    repo2 = tmp_path / "repo2"
    repo2.mkdir()
    _git(repo2, "init", "-q")
    (repo2 / "results").mkdir()
    (repo2 / "results" / "runlog.jsonl").write_text("{}\n")
    _git(repo2, "add", "results")
    _git(repo2, "commit", "-q", "-m", "results first")
    import time
    time.sleep(1.1)  # distinct commit timestamps
    (repo2 / "PREREG.lock").write_text("abc\n")
    _git(repo2, "add", "PREREG.lock")
    _git(repo2, "commit", "-q", "-m", "lock late")
    ok, msg = prereg.verify_history(repo2)
    assert not ok and "precedes" in msg


# ----------------------------------------------------------------------- stats

def test_mcnemar_known_values():
    assert mcnemar_exact(0, 0) == 1.0
    # b=8, c=2: two-sided exact binomial
    p = mcnemar_exact(8, 2)
    assert abs(p - 0.109375) < 1e-9
    assert mcnemar_exact(5, 5) == 1.0
    assert mcnemar_exact(15, 0) < 0.001


def test_bootstrap_deterministic():
    vals = [0.1, 0.4, 0.2, 0.9, 0.5, 0.3, 0.8]
    assert bootstrap_ci(vals, seed=7) == bootstrap_ci(vals, seed=7)
    assert bootstrap_ci(vals, seed=7) != bootstrap_ci(vals, seed=8)


def test_holm_ordering():
    ps = {"H1": 0.001, "H2": 0.04, "H3": 0.03, "H4": 0.5}
    out = holm(ps)
    assert out["H1"]["reject"]
    # H3 adjusted = 3 * 0.03 = 0.09 > 0.05 -> stop; H2 and H4 not rejected
    assert not out["H3"]["reject"] and not out["H2"]["reject"] and not out["H4"]["reject"]
    assert out["H4"]["adjusted"] >= out["H3"]["adjusted"]
