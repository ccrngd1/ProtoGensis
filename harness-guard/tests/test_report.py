from harness_guard.report.risk import (
    build_report,
    classify_tool_risk,
    max_risk_tier,
    remediation_checklist,
    score_hardening_tier,
)


# --- risk tiers ------------------------------------------------------------
def test_classify_read_only():
    assert classify_tool_risk("read_env_key", "Read an env var") == "read_only"


def test_classify_write():
    assert classify_tool_risk("write_sentinel_file", "Write a file") == "write"


def test_classify_destructive():
    assert classify_tool_risk("delete_all", "removes everything") == "destructive"
    assert classify_tool_risk("run_shell", "exec a shell command") == "destructive"


def test_classify_exfil():
    assert classify_tool_risk("fire_callback", "POST to a webhook") == "exfil"


def test_classify_unknown_defaults_to_write():
    assert classify_tool_risk("frobnicate", "does a thing") == "write"


def test_max_risk_tier_picks_most_severe():
    assert max_risk_tier(["read_only", "exfil", "write"]) == "exfil"
    assert max_risk_tier([]) == "read_only"


# --- hardening tier scoring -----------------------------------------------
def test_tier_0_when_direct_succeeds():
    v = {"direct": "VULNERABLE", "replay": "VULNERABLE", "cross_session": "VULNERABLE"}
    assert score_hardening_tier(v) == 0


def test_tier_1_when_direct_blocked_but_replay_succeeds():
    v = {"direct": "HARDENED", "replay": "VULNERABLE", "cross_session": "VULNERABLE"}
    assert score_hardening_tier(v) == 1


def test_tier_2_when_all_blocked():
    v = {"direct": "HARDENED", "replay": "HARDENED", "cross_session": "HARDENED"}
    assert score_hardening_tier(v) == 2


# --- remediation -----------------------------------------------------------
def test_remediation_tier_0_includes_core_fix():
    items = remediation_checklist(0)
    assert any("model-issued authorization for EVERY" in i for i in items)


def test_remediation_tier_2_focuses_on_semantic_and_monitoring():
    items = remediation_checklist(2)
    assert any("EBTE" in i for i in items)


def test_remediation_no_duplicates():
    items = remediation_checklist(0)
    assert len(items) == len(set(items))


# --- full report -----------------------------------------------------------
def test_build_report_overall_hardened():
    report = build_report(
        target="hardened",
        adapter="mcp_stdio",
        tools=[{"name": "write_sentinel_file", "description": "write a file"}],
        vector_results={
            "direct": {"verdict": "HARDENED", "response_type": "reject",
                       "side_effects_detected": [], "timing_ms": 0.1},
            "replay": {"verdict": "HARDENED", "response_type": "reject",
                       "side_effects_detected": [], "timing_ms": 0.1},
            "cross_session": {"verdict": "HARDENED", "response_type": "reject",
                              "side_effects_detected": [], "timing_ms": 0.1},
        },
    )
    assert report["overall_verdict"] == "HARDENED"
    assert report["hardening_tier"] == 2
    assert report["tools"][0]["risk_tier"] == "write"
    assert "invariant" in report
    assert report["remediation"]


def test_build_report_overall_vulnerable():
    report = build_report(
        target="vulnerable",
        adapter="mcp_stdio",
        tools=[],
        vector_results={
            "direct": {"verdict": "VULNERABLE", "response_type": "tool_result",
                       "side_effects_detected": ["write_sentinel_file:/tmp/x"], "timing_ms": 0.1},
        },
    )
    assert report["overall_verdict"] == "VULNERABLE"
    assert report["hardening_tier"] == 0
