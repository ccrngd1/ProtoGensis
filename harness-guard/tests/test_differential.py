"""Differential oracle: the vulnerable harness must FAIL every vector, and the
hardened harness must PASS (block) every vector. This is the core acceptance test.

All injection goes through the PRIMARY mcp_stdio adapter against the demo servers
spawned as subprocesses. No network."""

import pytest

from harness_guard.adapters.mcp_stdio import McpStdioAdapter
from harness_guard.auth import AuthMinter
from harness_guard.demo.hardened_harness import dispatch as hardened_dispatch
from harness_guard.demo.vulnerable_harness import dispatch as vulnerable_dispatch
from harness_guard.scanner import ALL_VECTORS, scan

VECTORS = list(ALL_VECTORS)


@pytest.mark.parametrize("vector", VECTORS)
def test_vulnerable_fails_each_vector(vector, vulnerable_cmd, workspace):
    adapter = McpStdioAdapter(vulnerable_cmd, workspace=workspace)
    report = scan(adapter, tool_name="write_sentinel_file",
                  tool_input={"content": "x"}, vectors=[vector],
                  tools=adapter.list_tools(), target="vulnerable")
    assert report["vectors"][vector]["verdict"] == "VULNERABLE"


@pytest.mark.parametrize("vector", VECTORS)
def test_hardened_blocks_each_vector(vector, hardened_cmd, workspace):
    adapter = McpStdioAdapter(hardened_cmd, workspace=workspace)
    report = scan(adapter, tool_name="write_sentinel_file",
                  tool_input={"content": "x"}, vectors=[vector],
                  tools=adapter.list_tools(), target="hardened")
    assert report["vectors"][vector]["verdict"] == "HARDENED"


def test_full_differential_vulnerable_overall_vulnerable(vulnerable_cmd, workspace):
    adapter = McpStdioAdapter(vulnerable_cmd, workspace=workspace)
    report = scan(adapter, tool_name="write_sentinel_file", tool_input={"content": "x"},
                  vectors=VECTORS, tools=adapter.list_tools(), target="vulnerable")
    assert report["overall_verdict"] == "VULNERABLE"
    assert report["hardening_tier"] == 0


def test_full_differential_hardened_overall_hardened(hardened_cmd, workspace):
    adapter = McpStdioAdapter(hardened_cmd, workspace=workspace)
    report = scan(adapter, tool_name="write_sentinel_file", tool_input={"content": "x"},
                  vectors=VECTORS, tools=adapter.list_tools(), target="hardened")
    assert report["overall_verdict"] == "HARDENED"
    assert report["hardening_tier"] == 2


# --- unit-level proof the fix is genuine (not just a hardcoded reject) -----
def test_valid_authorization_permits_dispatch():
    """A properly minted authorization must actually let the tool run — proving the
    hardened harness rejects on provenance grounds, not by refusing everything."""
    from harness_guard.demo import hardened_harness

    minter = hardened_harness._MINTER
    auth = minter.mint("sess", "turn1", "echo_payload", {"hello": "world"})
    params = {"_authorization": auth.to_dict()}
    result = hardened_dispatch("echo_payload", {"hello": "world"}, params)
    assert result["isError"] is False
    assert result["structuredContent"]["echo"] == {"hello": "world"}


def test_authorization_is_one_time_use():
    minter = AuthMinter()
    auth = minter.mint("s", "t", "echo_payload", {"a": 1})
    ok1, _ = minter.verify_and_consume(auth, "echo_payload", {"a": 1})
    ok2, reason2 = minter.verify_and_consume(auth, "echo_payload", {"a": 1})
    assert ok1 is True
    assert ok2 is False
    assert "replay" in reason2 or "consumed" in reason2


def test_authorization_args_binding():
    minter = AuthMinter()
    auth = minter.mint("s", "t", "echo_payload", {"a": 1})
    ok, reason = minter.verify_and_consume(auth, "echo_payload", {"a": 999})
    assert ok is False
    assert "args_hash" in reason


def test_vulnerable_dispatch_runs_without_auth():
    result = vulnerable_dispatch("echo_payload", {"z": 1}, {})
    assert result["isError"] is False
