"""Feb-19 reconstruction tests (AC #15, #16)."""

import json
import subprocess
import sys
from pathlib import Path

from policygate import demos

REPO = Path(__file__).parent.parent


def _demo_json(*args):
    r = subprocess.run([sys.executable, "-m", "policygate.cli", "demo", "feb19",
                        "--format", "json", *args],
                       cwd=REPO, capture_output=True, text=True)
    return json.loads(r.stdout)


def test_counts():
    d = demos.feb19_data()
    e = d["episodes"]
    assert [e["ep1_pinned"]["calls"], e["ep1_pinned"]["blocked"],
            e["ep1_counterfactual"]["blocked"], e["ep1_counterfactual"]["retroactive"],
            e["ep2_pinned"]["calls"], e["ep2_pinned"]["blocked"],
            d["weakens_policy_fired"]] == [11, 0, 10, True, 10, 9, True]


def test_double_fire_four():
    d = demos.feb19_data()
    doubles = [c for c in d["calls"] if c["episode"] == "ep2_pinned" and len(c["fired"]) == 2]
    assert len(doubles) == 4


def test_banner_first_line():
    r = subprocess.run([sys.executable, "-m", "policygate.cli", "demo", "feb19"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.stdout.splitlines()[0].startswith("RECONSTRUCTED FIXTURE")


def test_no_real_ids_in_fixtures():
    # hashed banned list + redacted-prefix rule (scan.banned_id_hits), so this
    # test holds no real ID or fragment, not even split (R10, main review P2)
    from policygate import scan
    prefixes = scan.redacted_prefixes(str(REPO))
    assert len(prefixes) >= 6  # the six redacted job prefixes (AC #16)
    for p in (REPO / "fixtures" / "feb19").rglob("*"):
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="ignore")
            for lineno, line in enumerate(text.splitlines(), 1):
                hits = scan.banned_id_hits(line, scan.BANNED_ID_SHA256, prefixes)
                assert not hits, f"{hits} in {p}:{lineno}"


def test_resolve_block_matches_spike():
    d = demos.feb19_data()
    assert [[r["id"], r["outcome"], r["class"]] for r in d["resolve"]] == [
        ["TWR-PRE-01", "REPAIR", "write-scope"],
        ["TWR-FBD-02", "REPAIR", "argument-signature"],
        ["TWR-PRE-04", "REJECT", "unscoped-wildcard"],
    ]
