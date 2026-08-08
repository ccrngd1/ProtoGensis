from harness_guard.observe.response import classify_response
from harness_guard.observe.sidefx import (
    CanaryWorkspace,
    read_side_effects,
    record_side_effect,
)
from harness_guard.observe.timing import MODEL_LATENCY_FLOOR_MS, analyze_timing


# --- side effects ----------------------------------------------------------
def test_record_and_read_side_effect(workspace):
    assert workspace.detected() == []
    record_side_effect(workspace.root, "write_sentinel_file", "/tmp/x")
    detected = workspace.detected()
    assert len(detected) == 1
    assert detected[0].startswith("write_sentinel_file:")


def test_read_side_effects_empty_when_no_dir(tmp_path):
    assert read_side_effects(tmp_path / "nope") == []


def test_workspace_reset_clears_records(workspace):
    record_side_effect(workspace.root, "echo_payload", "e")
    assert workspace.detected()
    workspace.reset()
    assert workspace.detected() == []


def test_workspace_env_exposes_dir(workspace):
    from harness_guard.observe.sidefx import ENV_VAR
    assert workspace.env[ENV_VAR] == str(workspace.root)


def test_workspace_context_manager_cleans_up():
    with CanaryWorkspace() as ws:
        root = ws.root
        assert root.is_dir()
    assert not root.is_dir()


# --- response classification ----------------------------------------------
def test_classify_tool_result():
    raw = {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text"}], "isError": False}}
    assert classify_response(raw) == "tool_result"


def test_classify_reject_from_iserror_result():
    raw = {"result": {"isError": True, "structuredContent": {"error": "unauthorized",
           "reason": "no model-issued authorization found"}}}
    assert classify_response(raw) == "reject"


def test_classify_reject_from_error_object():
    raw = {"error": {"code": -32000, "message": "unauthorized: provenance check failed"}}
    assert classify_response(raw) == "reject"


def test_classify_generic_error():
    raw = {"error": {"code": -32601, "message": "method not found"}}
    assert classify_response(raw) == "error"


def test_classify_timeout_when_none_or_flagged():
    assert classify_response(None) == "timeout"
    assert classify_response({"result": {}}, timed_out=True) == "timeout"


# --- timing ----------------------------------------------------------------
def test_timing_below_floor_flags_absent_model_latency():
    sig = analyze_timing(1.0)
    assert sig.model_latency_absent is True
    assert "no model turn" in sig.note


def test_timing_above_floor_is_plausible():
    sig = analyze_timing(MODEL_LATENCY_FLOOR_MS + 500)
    assert sig.model_latency_absent is False
    assert "plausible" in sig.note
