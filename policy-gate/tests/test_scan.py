"""Scan + results lint tests (AC #21)."""

import hashlib
import json
import subprocess
import uuid as uuid_mod
from pathlib import Path

import pytest

from policygate import results_lint, scan

REPO = Path(__file__).parent.parent


def _init_repo(tmp_path):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-C", str(tmp_path), "init", "-q"], check=True)
    return tmp_path


def _commit(tmp_path, rel, content):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-C", str(tmp_path), "commit", "-q", "-m", "x"], check=True, capture_output=True)


def test_planted_findings_flagged(tmp_path):
    repo = _init_repo(tmp_path)
    aws = "AKIA" + "ABCDEFGHIJKLMNOP"
    slack = "C0" + "ABCD1234E"
    # random v4 UUID (not a real job ID), split so the repo scan of this file
    # does not flag it as real_uuid
    uuid = "c900fd22-" + "0f86-440c-a2aa-1ae221ca6c77"
    ip = "192." + "168.1.27"
    email = "alice" + "@example.com"
    token = "token:" + "SuperSecretValue123"
    _commit(repo, "f.txt", "\n".join([aws, slack, uuid, ip, email, token]))
    ok, lines = scan.scan_repo(str(repo))
    assert not ok
    joined = "\n".join(lines)
    assert "akia" in joined
    assert "slack_id" in joined
    assert "real_uuid" in joined
    assert "rfc1918" in joined
    assert "email" in joined
    assert "token_assign" in joined


def test_synthetic_uuid_passes(tmp_path):
    repo = _init_repo(tmp_path)
    _commit(repo, "f.txt", "job 5ff9ece3-0000-4000-8000-000000000001 is synthetic")
    ok, _ = scan.scan_repo(str(repo))
    assert ok


def test_allowlisted_quote_passes(tmp_path):
    repo = _init_repo(tmp_path)
    ip = "192." + "168.1.27"
    _commit(repo, "doc.md", f"Never write to WikiJS ({ip}:3002)")
    allow = '[[exception]]\nfile = "doc.md"\npattern = "rfc1918"\njustification = "research quote"\n'
    (repo / "docs").mkdir()
    (repo / "docs" / "SCAN_ALLOWLIST.toml").write_text(allow)
    ok, _ = scan.scan_repo(str(repo))
    assert ok


def test_secret_cannot_be_allowlisted(tmp_path):
    repo = _init_repo(tmp_path)
    aws = "AKIA" + "ABCDEFGHIJKLMNOP"
    _commit(repo, "doc.md", aws)
    (repo / "docs").mkdir()
    (repo / "docs" / "SCAN_ALLOWLIST.toml").write_text(
        '[[exception]]\nfile = "doc.md"\npattern = "akia"\njustification = "nope"\n')
    ok, _ = scan.scan_repo(str(repo))
    assert not ok


def test_results_lint_rejects_non_enumerated(tmp_path):
    bad = {"profile": "pinned", "note": "a free-form sentence that is not enumerated!"}
    (tmp_path / "r.json").write_text(json.dumps(bad))
    ok, lines = results_lint.lint_dir(str(tmp_path))
    assert not ok


def test_results_lint_accepts_enumerated(tmp_path):
    good = {"profile": "spike-parity", "by_vtool": {"cron.disable": 4},
            "readings_sha256": "a" * 64, "verdict_class": "NO_RULE_IN_FORCE"}
    (tmp_path / "r.json").write_text(json.dumps(good))
    ok, lines = results_lint.lint_dir(str(tmp_path))
    assert ok, lines


def test_results_lint_accepts_per_version_rule_ids(tmp_path):
    good = {"rules": {"CAB-PRE-15a": {"strict": 1}, "CAB-PRE-15b": {"strict": 1}},
            "firing_rates": [{"rule": "CAB-PRE-15b", "vtool": "config.set",
                              "n": 1, "fired": 1, "rate": 1.0, "flag": False}],
            "retroactive_rules": {"CAB-PRE-15a": {"flagged": 1}}}
    (tmp_path / "r.json").write_text(json.dumps(good))
    ok, lines = results_lint.lint_dir(str(tmp_path))
    assert ok, lines


def test_results_lint_rejects_bad_version_suffix(tmp_path):
    for bad_id in ("CAB-PRE-15ab", "CAB-PRE-15A", "cab-pre-15a!"):
        (tmp_path / "r.json").write_text(json.dumps({"rules": {bad_id: {}}}))
        ok, _ = results_lint.lint_dir(str(tmp_path))
        assert not ok, bad_id


def test_results_lint_accepts_eval_schema_strings(tmp_path):
    from policygate.baselines.keyword import LABEL
    good = {"label_status": "provisional",
            "baselines": {"keyword": {"label": LABEL, "precision": 0.1887}}}
    (tmp_path / "r.json").write_text(json.dumps(good))
    ok, lines = results_lint.lint_dir(str(tmp_path))
    assert ok, lines
    # label_status values are a closed set; only the exact baseline label passes
    bad = {"label_status": "definitely confirmed by someone"}
    (tmp_path / "r.json").write_text(json.dumps(bad))
    ok, _ = results_lint.lint_dir(str(tmp_path))
    assert not ok
    bad2 = {"baselines": {"keyword": {"label": LABEL + " v2"}}}
    (tmp_path / "r.json").write_text(json.dumps(bad2))
    ok, _ = results_lint.lint_dir(str(tmp_path))
    assert not ok


def test_results_get(tmp_path):
    (tmp_path / "r.json").write_text(json.dumps({"readings": {"strict": {"blocked": 7}}}))
    assert results_lint.get_key(str(tmp_path / "r.json"), "readings.strict.blocked") == 7


# ---- known-real-ID checks (main review P1-P3) ----

def _split(value, at=9):
    """Source text of `value` split by string concatenation, as a test or a
    shell script would write it to dodge a literal grep."""
    return f'x = "{value[:at]}" + "{value[at:]}"'


def test_split_banned_id_caught_in_tests_and_scripts(tmp_path):
    # a fresh random ID stands in for a real one; only its hash is "banned"
    fake_real = str(uuid_mod.uuid4())
    h = hashlib.sha256(fake_real.encode()).hexdigest()
    repo = _init_repo(tmp_path)
    _commit(repo, "tests/test_x.py", _split(fake_real))
    _commit(repo, "scripts/x.sh", f'IDS="{fake_real[:9]}""{fake_real[9:]}"')
    ok, lines = scan.scan_repo(str(repo), extra_banned_hashes={h})
    assert not ok
    joined = "\n".join(lines)
    assert "tests/test_x.py:1: banned_id" in joined
    assert "scripts/x.sh:1: banned_id" in joined
    ok, lines = scan.scan_ids(str(repo), extra_banned_hashes={h})
    assert not ok and len(lines) == 3
    # without the hash the split form is invisible to the plain patterns
    ok, _ = scan.scan_ids(str(repo))
    assert ok


def test_banned_id_cannot_be_allowlisted(tmp_path):
    fake_real = str(uuid_mod.uuid4())
    h = hashlib.sha256(fake_real.encode()).hexdigest()
    repo = _init_repo(tmp_path)
    _commit(repo, "tests/t.py", _split(fake_real))
    (repo / "docs").mkdir()
    (repo / "docs" / "SCAN_ALLOWLIST.toml").write_text(
        '[[exception]]\nfile = "*"\npattern = "*"\njustification = "nope"\n')
    ok, lines = scan.scan_repo(str(repo), extra_banned_hashes={h})
    assert not ok and any("banned_id" in l for l in lines)


def test_real_prefix_fragment_caught(tmp_path):
    # a redacted fixture keeps the real 8-hex prefix with a synthetic suffix;
    # any other suffix after that prefix (a real fragment) is flagged, even split
    # (prefix built at runtime so this file itself carries no prefix+suffix)
    pfx = uuid_mod.uuid4().hex[:8]
    repo = _init_repo(tmp_path)
    _commit(repo, "fixtures/f.json", '{"job": "%s-0000-4000-8000-000000000001"}' % pfx)
    _commit(repo, "tests/t.py", 'banned = ["%s-" + "9f3c"]' % pfx)
    ok, lines = scan.scan_ids(str(repo))
    assert not ok
    assert any(l.startswith("tests/t.py:1: real_prefix_fragment") for l in lines)


def test_banned_hashes_are_hashes_only():
    # the committed list holds sha256 digests, never plaintext IDs
    assert len(scan.BANNED_ID_SHA256) == 7
    assert all(len(h) == 64 and set(h) <= set("0123456789abcdef")
               for h in scan.BANNED_ID_SHA256)


def test_repo_tree_has_no_known_real_ids():
    # the real policy-gate tree, tests/ and scripts/ included
    ok, lines = scan.scan_ids(str(REPO))
    assert ok, lines
    files = scan._git_files(str(REPO))
    assert any(f.startswith("tests/") for f in files)
    assert any(f.startswith("scripts/") for f in files)


@pytest.mark.host
def test_repo_has_no_live_cron_job_ids():
    """Host: every job ID in the (read-only) cron store, hashed in memory, is
    absent from the tree in raw or concatenation-split form."""
    import glob
    import re
    rx = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    ids = set()
    for p in glob.glob("/root/.openclaw/cron/jobs*.json*"):
        try:
            ids.update(rx.findall(open(p, encoding="utf-8", errors="ignore").read()))
        except OSError:
            continue
    if not ids:
        pytest.skip("no readable cron job store")
    hashes = {hashlib.sha256(i.encode()).hexdigest() for i in ids}
    ok, lines = scan.scan_ids(str(REPO), extra_banned_hashes=hashes)
    assert ok, lines[:5]
