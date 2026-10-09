"""AC #5 CacheSimulator tests: spike shape, head-vs-tail, TTL, min threshold."""

from memdoc.cache_sim import CacheSimulator
from memdoc.cost import call_cost, load_pricing, uncached_counterfactual


def test_spike_shape_write_then_read():
    # research §5.1: 10,017-token prefix called twice
    sim = CacheSimulator(min_cache_tokens=1024)
    blocks = [{"tokens": 10017, "key": "sys-prefix"}, {"cachePoint": True},
              {"tokens": 22, "key": "q"}]
    u1 = sim.simulate_call(blocks, now=0.0)
    assert u1.cacheWriteInputTokens == 10017
    assert u1.cacheReadInputTokens == 0
    assert u1.inputTokens == 22
    u2 = sim.simulate_call(blocks, now=10.0)
    assert u2.cacheReadInputTokens == 10017
    assert u2.cacheWriteInputTokens == 0
    assert u2.inputTokens == 22


def test_tail_injection_keeps_history_cached():
    sim = CacheSimulator(min_cache_tokens=100)
    history = []
    writes, reads = [], []
    for i in range(5):
        blocks = [{"tokens": 2000, "key": "sys"}, {"cachePoint": True}]
        for h in history:
            blocks.append(h)
        blocks.append({"cachePoint": True})
        blocks.append({"tokens": 100, "key": f"turn-{i}"})
        u = sim.simulate_call(blocks, now=float(i))
        writes.append(u.cacheWriteInputTokens)
        reads.append(u.cacheReadInputTokens)
        history.append({"tokens": 100, "key": f"turn-{i}"})
        history.append({"tokens": 50, "key": f"answer-{i}"})
    # after the first call, the whole stable prefix reads from cache
    assert writes[0] == 2000
    assert all(r >= 2000 for r in reads[1:])
    # each later call only writes the newly appended history segment
    assert all(w <= 200 for w in writes[1:])


def test_head_injection_rewrites_history():
    sim = CacheSimulator(min_cache_tokens=100)
    history = []
    total_write = 0
    for i in range(5):
        # changing head block busts every prefix behind it
        blocks = [{"tokens": 750, "key": f"head-snippets-{i}"}]
        for h in history:
            blocks.append(h)
        blocks.append({"cachePoint": True})
        blocks.append({"tokens": 100, "key": f"turn-{i}"})
        u = sim.simulate_call(blocks, now=float(i))
        total_write += u.cacheWriteInputTokens
        history.append({"tokens": 100, "key": f"turn-{i}"})
        history.append({"tokens": 50, "key": f"answer-{i}"})
    # every call re-writes head + all history: cacheWrite grows with history length
    assert total_write > 5 * 750  # strictly more than the heads alone


def test_ttl_expiry_turns_read_into_write():
    sim = CacheSimulator(ttl_seconds=300, min_cache_tokens=100)
    blocks = [{"tokens": 5000, "key": "sys"}, {"cachePoint": True}]
    u1 = sim.simulate_call(blocks, now=0.0)
    assert u1.cacheWriteInputTokens == 5000
    u2 = sim.simulate_call(blocks, now=301.0)
    assert u2.cacheWriteInputTokens == 5000
    assert u2.cacheReadInputTokens == 0


def test_min_cache_tokens_threshold():
    sim = CacheSimulator(min_cache_tokens=1024)
    blocks = [{"tokens": 500, "key": "small"}, {"cachePoint": True}]
    u = sim.simulate_call(blocks, now=0.0)
    assert u.cacheWriteInputTokens == 0
    assert u.inputTokens == 500


def test_max_cache_points_cap():
    sim = CacheSimulator(min_cache_tokens=10, max_cache_points=1)
    blocks = [{"tokens": 100, "key": "a"}, {"cachePoint": True},
              {"tokens": 100, "key": "b"}, {"cachePoint": True}]
    u = sim.simulate_call(blocks, now=0.0)
    # second cachePoint ignored: its segment is uncached
    assert u.cacheWriteInputTokens == 100
    assert u.inputTokens == 100


def test_call_cost_hand_computed():
    prices = load_pricing()
    usage = {"inputTokens": 1000, "cacheWriteInputTokens": 10000,
             "cacheReadInputTokens": 100000, "outputTokens": 500}
    # (1000*3 + 10000*3*1.25 + 100000*3*0.10 + 500*15) / 1e6
    expected = (3000 + 37500 + 30000 + 7500) / 1e6
    assert abs(call_cost(usage, prices) - expected) < 1e-12
    cf = (111000 * 3 + 500 * 15) / 1e6
    assert abs(uncached_counterfactual(usage, prices) - cf) < 1e-12
