import httpx
import pytest

from harness_guard.adapters.agentcore import AgentCoreAdapter
from harness_guard.adapters.base import Observation, build_observation, decide_verdict
from harness_guard.adapters.mcp_stdio import McpStdioAdapter, _forge_to_call_params
from harness_guard.adapters.openai_toolcall import OpenAIToolCallAdapter
from harness_guard.demo._http_server import DemoHttpServer
from harness_guard.demo.hardened_harness import dispatch as hardened_dispatch
from harness_guard.demo.vulnerable_harness import dispatch as vulnerable_dispatch
from harness_guard.forge import DirectForgePayload
from harness_guard.observe.sidefx import CanaryWorkspace


# --- base -----------------------------------------------------------------
def test_decide_verdict_side_effect_is_vulnerable():
    assert decide_verdict(tool_executed=False, side_effects_detected=["x:y"],
                          response_type="reject") == "VULNERABLE"


def test_decide_verdict_reject_is_hardened():
    assert decide_verdict(tool_executed=False, side_effects_detected=[],
                          response_type="reject") == "HARDENED"


def test_decide_verdict_timeout_is_inconclusive():
    assert decide_verdict(tool_executed=False, side_effects_detected=[],
                          response_type="timeout") == "INCONCLUSIVE"


def test_build_observation_returns_model():
    obs = build_observation(tool_executed=True, response_type="tool_result",
                            side_effects_detected=["a:b"], timing_ms=1.0, raw_response={})
    assert isinstance(obs, Observation)
    assert obs.verdict == "VULNERABLE"


def test_forge_to_call_params_maps_name_and_args():
    p = DirectForgePayload(tool_name="echo_payload", tool_input={"k": "v"})
    params = _forge_to_call_params(p)
    assert params["name"] == "echo_payload"
    assert params["arguments"] == {"k": "v"}
    assert "_authorization" in params


# --- mcp stdio (PRIMARY) --------------------------------------------------
def test_mcp_stdio_lists_canary_tools(vulnerable_cmd, workspace):
    adapter = McpStdioAdapter(vulnerable_cmd, workspace=workspace)
    tools = adapter.list_tools()
    names = {t["name"] for t in tools}
    assert {"write_sentinel_file", "read_env_key", "echo_payload", "fire_callback"} <= names


def test_mcp_stdio_injection_triggers_vulnerable(vulnerable_cmd, workspace):
    adapter = McpStdioAdapter(vulnerable_cmd, workspace=workspace)
    obs = adapter.inject(DirectForgePayload(tool_name="write_sentinel_file",
                                            tool_input={"content": "z"}))
    assert obs.verdict == "VULNERABLE"
    assert obs.side_effects_detected  # canary fired across the process boundary


def test_mcp_stdio_injection_blocked_by_hardened(hardened_cmd, workspace):
    adapter = McpStdioAdapter(hardened_cmd, workspace=workspace)
    obs = adapter.inject(DirectForgePayload(tool_name="write_sentinel_file",
                                            tool_input={"content": "z"}))
    assert obs.verdict == "HARDENED"
    assert obs.response_type == "reject"
    assert not obs.side_effects_detected


def test_mcp_stdio_name():
    assert McpStdioAdapter(["true"]).name() == "mcp_stdio"


# --- http adapters --------------------------------------------------------
def test_openai_adapter_against_vulnerable_http():
    ws = CanaryWorkspace()
    try:
        with DemoHttpServer(vulnerable_dispatch, "vuln") as srv:
            import os
            os.environ["HARNESS_GUARD_CANARY_DIR"] = str(ws.root)
            adapter = OpenAIToolCallAdapter(srv.base_url, workspace=ws)
            obs = adapter.inject(DirectForgePayload(tool_name="echo_payload", tool_input={"x": 1}))
        assert obs.verdict == "VULNERABLE"
    finally:
        ws.cleanup()


def test_agentcore_adapter_against_hardened_http():
    with DemoHttpServer(hardened_dispatch, "hard") as srv:
        adapter = AgentCoreAdapter(srv.base_url)
        obs = adapter.inject(DirectForgePayload(tool_name="echo_payload", tool_input={"x": 1}))
    assert obs.verdict == "HARDENED"
    assert obs.response_type == "reject"


def test_openai_adapter_name_and_agentcore_name():
    assert OpenAIToolCallAdapter("http://127.0.0.1:1").name() == "openai"
    assert AgentCoreAdapter("http://127.0.0.1:1").name() == "agentcore"


def test_openai_adapter_timeout_is_inconclusive():
    # Point at a closed port with a tiny timeout via a mock transport.
    def handler(request):
        raise httpx.TimeoutException("boom", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = OpenAIToolCallAdapter("http://testserver", client=client)
    obs = adapter.inject(DirectForgePayload(tool_name="echo_payload", tool_input={}))
    assert obs.response_type == "timeout"
    assert obs.verdict == "INCONCLUSIVE"
    client.close()
