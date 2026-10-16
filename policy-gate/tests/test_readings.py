"""Readings tests: ported authorized() equals the spike's (AC #13)."""

from policygate import readings as readings_mod
from tests.spike_ref import spike_replay

RD = readings_mod.default()

CASES = [
    ("cron.disable", "please disable the cron job", "", ),
    ("gateway.restart", "yes", "I will restart the gateway, ok?"),
    ("gateway.restart", "yes", "unrelated prior message"),
    ("cron.edit", "do it", "shall I edit the cron schedule?"),
    ("service.restart", None, ""),
    ("config.set", "set the config value", ""),
]


def test_matches_spike_all_readings():
    for vt, cc, prev in CASES:
        for reading in ("strict", "plan", "lenient"):
            ours = RD.authorized(reading, vt, cc, prev)
            theirs = spike_replay.authorized(reading, vt, cc, prev)
            assert ours == theirs, (vt, cc, prev, reading)


def test_three_keys_present():
    out = RD.all_readings("cron.disable", "disable the job", "")
    assert sorted(out.keys()) == ["lenient", "plan", "strict"]


def test_sha256_stable():
    assert readings_mod.Readings().sha256 == RD.sha256
