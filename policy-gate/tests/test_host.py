"""Host-only tests (AC #16, #18). Run only with PG_HOST_TESTS=1 and a readable
/root/.openclaw; otherwise skipped by conftest."""

import json
import os
import subprocess
import sys

import pytest

pytestmark = pytest.mark.host

REPO = os.path.dirname(os.path.dirname(__file__))
ROOT = "/root/.openclaw"
BUNDLE = "config/bundle.cabal.toml"


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "policygate.cli", *args],
                          cwd=REPO, capture_output=True, text=True)


def test_bundle_show_known_commits():
    r = _cli("bundle", "show", "--root", ROOT, "--bundle", BUNDLE,
             "--at", "2026-02-19T16:00:00Z", "--format", "json")
    d = json.loads(r.stdout)
    assert d["sources"]["global/BASE-AGENTS.md"]["commit"][:8] == "b314fe85"
    r2 = _cli("bundle", "show", "--root", ROOT, "--bundle", BUNDLE,
              "--at", "2026-02-19T17:00:00Z", "--format", "json")
    d2 = json.loads(r2.stdout)
    assert d2["sources"]["global/BASE-AGENTS.md"]["commit"][:8] == "f84fecd8"


def test_parse_qualifier_inheritance():
    r = _cli("parse", "--root", ROOT, "--bundle", BUNDLE,
             "--at", "2026-02-19T17:00:00Z", "--format", "json")
    d = json.loads(r.stdout)
    quals = [c for c in d["clauses"]
             if c["src"]["file"] == "global/BASE-AGENTS.md"
             and "without explicit CC instruction" in c["inherited_qualifiers"]]
    assert len(quals) >= 3


def test_verify_sources_four_pass():
    r = _cli("demo", "feb19", "--verify-sources", ROOT)
    assert r.stdout.count("PASS") == 4
    assert r.stdout.count("FAIL") == 0


def test_spike_parity_parity_check_27(tmp_path):
    out = str(tmp_path / "parity")
    # host runs write per-action detail only to local/ or tmp --out dirs
    r = _cli("replay", "--source", "legacy-archive", "--path", f"{ROOT}/agents",
             "--profile", "spike-parity", "--format", "json", "--out", out)
    d = json.loads(r.stdout)
    pc = d["parity_check"]
    assert len(pc["matches"]) + len(pc["deltas"]) == 27


def test_replay_aggregates_hold_input_manifest(tmp_path):
    """AC #18: each results-bound aggregates file holds the input manifest
    (file count + sha256 over the sorted (relpath, size) list)."""
    out = str(tmp_path / "parity")
    r = _cli("replay", "--source", "legacy-archive", "--path", f"{ROOT}/agents",
             "--profile", "spike-parity", "--format", "json", "--out", out)
    d = json.loads(r.stdout)
    im = d["input_manifest"]
    assert im["file_count"] >= 1
    assert len(im["sha256"]) == 64
    m = json.load(open(os.path.join(out, "manifest.json")))
    assert m["input_manifest"] == im


def test_scan_against_archive(tmp_path):
    from policygate import scan
    ok, lines = scan.scan_repo(REPO, against_archive=f"{ROOT}/agents")
    assert ok, lines
