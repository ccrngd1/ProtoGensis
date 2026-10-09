"""AC #13: Converse codec round-trips fixtures; live gating; budget abort.

Everything here is offline. Fixtures not captured live are labeled
"synthetic_shape": true. Live tests requiring boto3/credentials are skipped.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from memdoc.agent.converse import (BudgetTracker, decode_response, encode_request,
                                   encode_tool_result)
from memdoc.backends.base import ToolSpec

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "converse"
MEMDOC = [sys.executable, "-m", "memdoc.cli"]


def _load(name):
    return json.loads((FIXTURES / name).read_text())


def test_fixtures_are_labeled():
    for p in FIXTURES.glob("*.json"):
        assert json.loads(p.read_text()).get("synthetic_shape") is True, p


def test_decode_text_response_usage_verbatim():
    d = decode_response(_load("text_response.json"))
    assert d["text"] == "The port is 19222."
    assert d["usage"] == {"inputTokens": 42, "cacheReadInputTokens": 10017,
                          "cacheWriteInputTokens": 0, "outputTokens": 9}
    assert d["stop_reason"] == "end_turn"


def test_decode_tool_use_and_tool_result_roundtrip():
    d = decode_response(_load("tool_use_response.json"))
    assert d["tool_uses"] == [{"toolUseId": "tu-001", "name": "memory_search",
                               "input": {"query": "relay port", "k": "5"}}]
    msg = encode_tool_result("tu-001", "hit: the relay binds 19222")
    assert msg["content"][0]["toolResult"]["toolUseId"] == "tu-001"


def test_encode_request_has_cache_point_and_tools():
    req = encode_request("PREFIX", [{"role": "user", "text": "hi"}],
                         [ToolSpec(name="grep", description="g", input_schema={"pattern": "s"})])
    assert req["system"][0] == {"text": "PREFIX"}
    assert req["system"][1] == {"cachePoint": {"type": "default"}}
    assert req["toolConfig"]["tools"][0]["toolSpec"]["name"] == "grep"


def test_budget_tracker_aborts_before_crossing():
    b = BudgetTracker(max_usd=1.0)
    b.charge(0.95)
    assert b.would_exceed(0.10)
    assert not b.would_exceed(0.04)


def _run_cli(*args):
    r = subprocess.run(MEMDOC + list(args), capture_output=True, text=True,
                       cwd=Path(__file__).resolve().parent.parent)
    return r.returncode, r.stdout + r.stderr


def test_live_without_max_usd_is_usage_error():
    code, out = _run_cli("run", "--live", "bedrock", "--model-id", "x",
                         "--arms", "a1", "--sizes", "25000", "--seeds", "0")
    assert code == 2
    assert "max-usd" in out


def test_mock_run_cannot_write_results_dir(tmp_path):
    code, out = _run_cli("run", "--arms", "a0", "--sizes", "5000", "--seeds", "0",
                         "--out", "results/sneaky")
    assert code == 2
    assert "results/" in out


@pytest.mark.skipif(True, reason="live Bedrock run: needs [bedrock] extra, credentials, "
                                 "and CC's go-ahead; never run by tests")
def test_live_run():
    pass
