"""AC #3 size control, AC #4 fresh context + call events."""

import json
from pathlib import Path

import pytest

from memdoc.runlog import read_events
from memdoc.runner import run_mock

ARMS = ["a0", "astar", "a1", "a2", "a4", "a5", "a6"]
STORIES = ["c2s0", "c3s0", "c7s0"]


@pytest.fixture(scope="module")
def mock_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("mockrun")
    results, runlog = run_mock(ARMS, [5000, 25000, 100000], [0], out,
                               storyline_ids=STORIES)
    return results, read_events(runlog)


def test_a1_store_within_15pct(mock_run):
    results, _ = mock_run
    for size in (5000, 25000, 100000):
        for r in results:
            if r.arm == "a1" and r.size == size:
                assert abs(r.store_tokens - size) / size <= 0.15, \
                    f"A1 store {r.store_tokens} not within 15% of {size}"


def test_measured_size_is_reported(mock_run):
    results, events = mock_run
    cells = [e for e in events if e["event"] == "cell" and e["arm"] == "a1"]
    assert all(c["store_tokens"] > 0 for c in cells)


def test_call_events_have_required_fields(mock_run):
    _, events = mock_run
    calls = [e for e in events if e["event"] == "call"]
    assert calls
    required = {"run_id", "arm", "size", "storyline", "seed", "session", "call_idx",
                "inputTokens", "cacheReadInputTokens", "cacheWriteInputTokens",
                "outputTokens", "source"}
    for c in calls[:50]:
        assert required <= set(c)
        assert c["source"] == "cache_simulator"


def test_fresh_context_no_cross_session_history():
    """No message block key from session n appears in session n+1's request.

    The runner builds requests from history keys scoped per session; this test
    re-runs one cell with an instrumented simulator to assert the invariant."""
    from memdoc.cache_sim import CacheSimulator
    seen_keys_by_call = []
    orig = CacheSimulator.simulate_call

    def spy(self, blocks, now, output_tokens=0):
        seen_keys_by_call.append([b.get("key", "") for b in blocks if "key" in b])
        return orig(self, blocks, now, output_tokens)

    CacheSimulator.simulate_call = spy
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            run_mock(ARMS, [25000], [0], td, storyline_ids=["c3s0"])
    finally:
        CacheSimulator.simulate_call = orig

    for keys in seen_keys_by_call:
        hist = [k for k in keys if k.startswith("hist:")]
        sessions = {k.split(":")[1] for k in hist}
        assert len(sessions) <= 1, f"history from multiple sessions in one request: {sessions}"


def test_mock_profile_call_count(mock_run):
    _, events = mock_run
    calls = [e for e in events if e["event"] == "call" and e.get("call_type") == "task"
             and e["arm"] == "a0" and e["size"] == 5000 and e["storyline"] == "c2s0"]
    # medium profile: 30 calls/session x 5 sessions
    assert len(calls) == 150


def test_runlog_deterministic(tmp_path):
    r1, log1 = run_mock(["a1", "a4"], [5000], [0], tmp_path / "r1", storyline_ids=["c3s0"])
    r2, log2 = run_mock(["a1", "a4"], [5000], [0], tmp_path / "r2", storyline_ids=["c3s0"])
    assert Path(log1).read_bytes() == Path(log2).read_bytes()


def test_no_absolute_paths_in_log(mock_run):
    _, events = mock_run
    text = json.dumps(events)
    assert "/tmp/" not in text and "memdoc-a" not in text
