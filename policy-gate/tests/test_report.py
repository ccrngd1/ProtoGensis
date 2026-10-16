"""Report + firing-rate flag tests (AC #17)."""

import json

from policygate import report


def test_firing_rate_flag_boundary():
    by = {
        ("R1", "cron.disable"): {"n": 5, "fired": 5},   # rate 1.0, n=5 -> flag
        ("R2", "cron.edit"): {"n": 5, "fired": 4},      # rate 0.8 -> no flag
        ("R3", "gateway.restart"): {"n": 4, "fired": 4},  # rate 1.0 but n<5 -> no flag
    }
    rates = {r["rule"]: r for r in report.firing_rates(by)}
    assert rates["R1"]["flag"] is True
    assert rates["R2"]["flag"] is False
    assert rates["R3"]["flag"] is False


def test_firing_rate_09_exact():
    by = {("R", "v"): {"n": 10, "fired": 9}}
    r = report.firing_rates(by)[0]
    assert r["rate"] == 0.9
    assert r["flag"] is True


def test_report_renders_from_run_dir(tmp_path):
    agg = {
        "profile": "pinned", "provenance_source": "heuristic",
        "readings_sha256": "a" * 64,
        "readings": {"strict": {"blocked": 3, "total": 5}, "plan": {"blocked": 2, "total": 5},
                     "lenient": {"blocked": 1, "total": 5}},
        "verdict_classes": {}, "retroactive_rules": {}, "firing_rates": [],
    }
    (tmp_path / "aggregates.json").write_text(json.dumps(agg))
    out = report.render_run(str(tmp_path), "json")
    data = json.loads(out)
    assert data["violations_per_reading"] == {"strict": 3, "plan": 2, "lenient": 1}
    # byte-identical re-render
    assert report.render_run(str(tmp_path), "json") == out
