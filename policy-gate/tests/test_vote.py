"""Vote aggregation + gated live extractor usage error (AC #6)."""

import json
import sys
from pathlib import Path

from policygate import cli
from policygate.extract import vote

VOTES = json.loads((Path(__file__).parent.parent / "fixtures" / "candidates" / "votes.json").read_text())


def test_majority_vote_kept_and_dropped():
    out = vote.aggregate(VOTES["runs"], n=5)
    kept = {(k["predicate"], k["votes"], tuple(k["tools"])) for k in out["kept"]}
    # PRECONDITION cc_authorized/cron.disable appears 3/5 -> kept
    assert ("cc_authorized", "3/5", ("cron.disable",)) in kept
    # 2/5 target_protected dropped and listed
    drops = {(m["predicate"], m["votes"]) for m in out["minority_drops"]}
    assert ("target_protected", "2/5") in drops


def test_polarity_split_counted_separately():
    out = vote.aggregate(VOTES["runs"], n=5)
    types = sorted(k["type"] for k in out["kept"] if k["predicate"] == "cc_authorized")
    # cc_authorized appears both as PRECONDITION (3/5) and FORBIDDEN (3/5)
    assert types == ["FORBIDDEN", "PRECONDITION"]


def test_extract_live_missing_max_usd_exit2(monkeypatch):
    rc = cli.main(["extract", "--live", "bedrock", "--model-id", "x", "--votes", "5",
                   "--bundle", "config/bundle.cabal.toml"])
    assert rc == 2
    # the usage error is raised before boto3 is ever imported
    assert "boto3" not in sys.modules
