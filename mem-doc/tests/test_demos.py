"""AC #11/#12 demo tests. The full 3-seed demo runs in the Verify Checklist;
tests here use reduced seeds/sizes through the same code path to stay fast,
plus one full-size single-seed run asserting all MVP arms at all three sizes."""

import json

import pytest

from memdoc import MECHANISM_BANNER, costmodel
from memdoc.demos import (demo_cache, demo_costmodel, demo_crossover, demo_stale,
                          render_cache, render_costmodel, render_crossover, render_stale)

REDUCED = dict(seeds=[0], sizes=[5000], arms=["a0", "a1", "a4"])


def test_banner_everywhere():
    assert MECHANISM_BANNER == ("MECHANISM DEMO: scripted agent, hashing embedder, "
                                "simulated cache. Not benchmark results.")
    data = demo_crossover(**REDUCED)
    assert data["banner"] == MECHANISM_BANNER
    assert render_crossover(data).startswith(MECHANISM_BANNER)
    assert demo_cache()["banner"] == MECHANISM_BANNER
    assert demo_costmodel()["banner"] == MECHANISM_BANNER
    assert demo_stale()["banner"] == MECHANISM_BANNER


def test_crossover_byte_identical_json():
    a = render_crossover(demo_crossover(**REDUCED), "json")
    b = render_crossover(demo_crossover(**REDUCED), "json")
    assert a == b


@pytest.mark.slow
def test_crossover_all_mvp_arms_all_sizes():
    data = demo_crossover(seeds=[0])  # default sizes + arms from config
    keys = set(data["per_arm_size"])
    for arm in ("a0", "astar", "a1", "a2", "a4", "a5", "a6"):
        for size in (5000, 25000, 100000):
            assert f"{arm}@{size}" in keys


def test_crossover_breakeven_matches_costmodel():
    data = demo_crossover(**REDUCED)
    assert data["analytic_breakeven"] == costmodel.breakeven()
    assert data["analytic_breakeven"] == {"short": 4000, "medium": 6000, "long": 9000}


def test_crossover_labels_mechanism():
    data = demo_crossover(**REDUCED)
    assert "mechanism" in data["label"].lower()
    assert "accuracy" not in json.dumps(data["per_arm_size"]).lower()


def test_demo_cache_head_beats_tail():
    data = demo_cache()
    assert data["totals"]["head"]["cacheWrite"] > data["totals"]["tail"]["cacheWrite"]
    text = render_cache(data)
    assert "baseline" in text  # the ratio names its baseline (R11)


def test_demo_costmodel_tables_equal_module():
    data = demo_costmodel()
    assert data["tables"] == costmodel.tables()
    assert data["breakeven"] == costmodel.breakeven()
    assert "research §5.2" in data["label"] or "research" in data["label"]


def test_demo_stale_labels():
    data = demo_stale()
    assert data["embedder_label"] == "hashing embedder, not Titan"
    assert "research spike, 2026-10-09" in data["research_spike"]
    text = render_stale(data)
    assert "hashing embedder, not Titan" in text
    assert "research spike" in text
    assert len(data["ranking"]) == 5
