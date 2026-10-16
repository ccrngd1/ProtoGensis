"""Bundle + git pinning tests on the synthetic tmp repo (AC #3)."""

import subprocess
import sys
from pathlib import Path

import pytest

from policygate import bundle

FIX = Path(__file__).parent / "fixtures"
BUNDLE_TOML = Path(__file__).parent.parent / "fixtures" / "bundle.synthetic.toml"


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    target = tmp_path_factory.mktemp("policy_repo")
    subprocess.run([sys.executable, str(FIX / "make_policy_repo.py"), str(target)],
                   check=True, capture_output=True)
    return str(target)


@pytest.fixture(scope="module")
def pb(repo):
    return bundle.PolicyBundle.load(str(BUNDLE_TOML), repo)


def _sha_at(pb, t, path="global/BASE-AGENTS.md"):
    return pb.at(t).sources[path].commit


def test_absent_before_first_commit(pb):
    at = pb.at("2026-01-15T00:00:00Z")
    assert all(s.commit is None for s in at.sources.values())
    assert all(s.text is None for s in at.sources.values())


def test_five_probe_times(pb):
    # t1: before c1 -> ABSENT; t2: after c1; t3: between c1 and c2 (same sha);
    # t4: after c2; t5: after c3
    t1 = _sha_at(pb, "2026-01-31T23:59:59Z")
    t2 = _sha_at(pb, "2026-02-01T00:00:01Z")
    t3 = _sha_at(pb, "2026-02-19T00:00:00Z")
    t4 = _sha_at(pb, "2026-02-20T12:00:00Z")
    t5 = _sha_at(pb, "2026-04-01T00:00:00Z")
    assert t1 is None
    assert t2 is not None and t2 == t3
    assert t4 is not None and t4 != t2
    assert t5 is not None and t5 != t4


def test_rule_added_at_commit2(pb):
    before = pb.at("2026-02-19T00:00:00Z").sources["global/BASE-AGENTS.md"].text
    after = pb.at("2026-02-21T00:00:00Z").sources["global/BASE-AGENTS.md"].text
    assert "Quiet hours" not in before
    assert "Quiet hours" in after


def test_rule_removed_at_commit3(pb):
    mid = pb.at("2026-02-21T00:00:00Z").sources["global/BASE-AGENTS.md"].text
    late = pb.at("2026-03-16T00:00:00Z").sources["global/BASE-AGENTS.md"].text
    assert "legacy deploy script" in mid
    assert "legacy deploy script" not in late


def test_memory_only_changes_at_commit2(pb):
    m1 = pb.at("2026-02-10T00:00:00Z").sources["workspace/MEMORY.md"]
    m2 = pb.at("2026-02-21T00:00:00Z").sources["workspace/MEMORY.md"]
    m3 = pb.at("2026-04-01T00:00:00Z").sources["workspace/MEMORY.md"]
    assert "DO NOT TOUCH" not in m1.text
    assert "DO NOT TOUCH" in m2.text
    # MEMORY.md untouched by commit 3 -> same pinned commit
    assert m2.commit == m3.commit


def test_platform_rules_loaded(pb):
    at = pb.at("2026-03-01T00:00:00Z")
    ids = [r["id"] for r in at.platform_rules]
    assert "PLAT-FBD-04" in ids
    assert at.platform_rules[0].get("effective_from") == "unknown"


def test_deleted_source_is_absent_not_crash(pb):
    """Phase 2a Bug 2: `log -1 --before` returns the deleting commit; at() must
    report ABSENT/deleted (with the deleting sha) instead of crashing on
    `git show <sha>:<path>`."""
    # before first add
    s0 = pb.at("2026-01-15T00:00:00Z").sources["cron/jobs.json"]
    assert s0.status == "ABSENT" and s0.absent_reason == "never_added"
    assert s0.commit is None and s0.text is None
    # after add (c1), before delete (c4)
    s1 = pb.at("2026-03-01T00:00:00Z").sources["cron/jobs.json"]
    assert s1.status == "PRESENT" and s1.commit and "jobs" in s1.text
    # after delete (c4), before re-add (c5)
    s2 = pb.at("2026-05-15T00:00:00Z").sources["cron/jobs.json"]
    assert s2.status == "ABSENT" and s2.absent_reason == "deleted"
    assert s2.commit is None and s2.text is None
    assert s2.deleted_in and s2.deleted_in != s1.commit
    # after re-add (c5)
    s3 = pb.at("2026-06-15T00:00:00Z").sources["cron/jobs.json"]
    assert s3.status == "PRESENT" and s3.commit not in (None, s1.commit)
    assert s3.text == s1.text


def test_source_error_does_not_abort_bundle(pb, repo):
    """One source's git error becomes status ERROR; the others still resolve."""
    bad = bundle.PolicyBundle(repo, pb.sources + [
        {"path": "nope/\x01bad", "kind": "base", "subjects": ["*"], "precedence": 0}],
        pb.platform_rules)
    # a nonexistent path is ABSENT (never added), not an error; simulate a git
    # failure with an unreadable root for one bundle instead
    at = bad.at("2026-03-01T00:00:00Z")
    assert at.sources["global/BASE-AGENTS.md"].status == "PRESENT"
    broken = bundle.PolicyBundle(repo + "-does-not-exist", pb.sources, pb.platform_rules)
    at2 = broken.at("2026-03-01T00:00:00Z")
    assert all(s.status == "ERROR" and s.error for s in at2.sources.values())


def test_render_show_marks_deleted(pb):
    import json as _json
    d = _json.loads(bundle.render_show(pb.at("2026-05-15T00:00:00Z"), "json"))
    cj = d["sources"]["cron/jobs.json"]
    assert cj["commit"] == "ABSENT"
    assert cj["status"] == "ABSENT"
    assert cj["absent_reason"] == "deleted"
    assert cj["deleted_in"]
    txt = bundle.render_show(pb.at("2026-05-15T00:00:00Z"), "terminal")
    assert "ABSENT (deleted in" in txt


def test_bundle_history(pb):
    hist = bundle.history(pb)
    cj = hist["cron/jobs.json"]
    assert cj["status"] == "OK"
    assert [c["kind"] for c in cj["commits"]] == ["A", "D", "A"]
    times = [c["time"] for c in cj["commits"]]
    assert times == sorted(times)
    assert all(t.endswith("Z") for t in times)
    ba = hist["global/BASE-AGENTS.md"]
    assert [c["kind"] for c in ba["commits"]] == ["A", "M", "M"]
    # since/until narrow the window
    narrowed = bundle.history(pb, since="2026-02-10T00:00:00Z",
                              until="2026-04-01T00:00:00Z")
    assert [c["kind"] for c in narrowed["global/BASE-AGENTS.md"]["commits"]] == ["M", "M"]
    assert narrowed["cron/jobs.json"]["commits"] == []


def test_bundle_history_error_per_source(pb, repo):
    broken = bundle.PolicyBundle(repo + "-does-not-exist", pb.sources, pb.platform_rules)
    hist = bundle.history(broken)
    assert all(h["status"] == "ERROR" and h["commits"] == [] for h in hist.values())


def test_cli_bundle_exit_codes(repo):
    """CLI: a deleted source never makes `bundle show` exit nonzero unless the
    user asked for that source; history exits 0 and is valid JSON."""
    import json as _json
    import subprocess
    repo_root = str(Path(__file__).parent.parent)

    def cli(*args):
        return subprocess.run([sys.executable, "-m", "policygate.cli", *args],
                              cwd=repo_root, capture_output=True, text=True)

    r = cli("bundle", "show", "--root", repo, "--bundle", str(BUNDLE_TOML),
            "--at", "2026-05-15T00:00:00Z", "--format", "json")
    assert r.returncode == 0, r.stderr
    d = _json.loads(r.stdout)
    assert d["sources"]["cron/jobs.json"]["status"] == "ABSENT"

    # exit 2 only when the user asked for a source that is ERROR / not in bundle
    r2 = cli("bundle", "show", "--root", repo, "--bundle", str(BUNDLE_TOML),
             "--at", "2026-05-15T00:00:00Z", "--source", "not/in-bundle.md",
             "--format", "json")
    assert r2.returncode == 2

    r3 = cli("bundle", "history", "--root", repo, "--bundle", str(BUNDLE_TOML),
             "--since", "2026-02-01T00:00:00Z", "--until", "2026-09-28T00:00:00Z",
             "--format", "json")
    assert r3.returncode == 0, r3.stderr
    h = _json.loads(r3.stdout)
    assert h["schema"] == "policygate-bundle-history-v1"
    assert [c["kind"] for c in h["sources"]["cron/jobs.json"]["commits"]] == ["A", "D", "A"]


def test_shas_deterministic_across_builds(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    for t in (a, b):
        subprocess.run([sys.executable, str(FIX / "make_policy_repo.py"), str(t)],
                       check=True, capture_output=True)
    pa = bundle.PolicyBundle.load(str(BUNDLE_TOML), str(a))
    pbb = bundle.PolicyBundle.load(str(BUNDLE_TOML), str(b))
    t = "2026-03-01T00:00:00Z"
    assert {k: s.commit for k, s in pa.at(t).sources.items()} == \
           {k: s.commit for k, s in pbb.at(t).sources.items()}
