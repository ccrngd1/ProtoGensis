"""Offline demos (AC #11, #12). All deterministic; every surface prints the
mechanism banner. No network, no credentials.
"""

import json
import tomllib
from pathlib import Path

from . import MECHANISM_BANNER, costmodel
from .cache_sim import CacheSimulator
from .cost import load_pricing
from .backends.embedders import HashingEmbedder, cosine
from .tokens import ApproxTokenizer

PKG_ROOT = Path(__file__).resolve().parent.parent
DEMO_CONFIG = PKG_ROOT / "config" / "demo_crossover.toml"


def _fixed(x, nd=4):
    return f"{x:.{nd}f}"


# ------------------------------------------------------------- demo crossover

def demo_crossover(seeds=None, sizes=None, arms=None, tasks_dir=None):
    """All MVP arms x sizes x seeds with MockAgent/HashingEmbedder/CacheSimulator.

    Returns a JSON-ready dict: per arm x size mechanism metrics + cost splits,
    plus the empirical crossover next to the §5.2 analytic break-even."""
    from .report import build_report
    from .runner import run_mock
    import tempfile

    with open(DEMO_CONFIG, "rb") as f:
        cfg = tomllib.load(f)
    seeds = list(seeds) if seeds else list(cfg["seeds"])
    sizes = list(sizes) if sizes else list(cfg["sizes"])
    arms = list(arms) if arms else list(cfg["arms"])
    tasks_dir = tasks_dir or (PKG_ROOT / "tasks")

    with tempfile.TemporaryDirectory(prefix="memdoc-demo-") as td:
        _, runlog = run_mock(arms, sizes, seeds, td, tasks_dir=tasks_dir,
                             profile=cfg.get("profile", "medium"),
                             p_forget=cfg.get("p_forget", 0.0))
        report, _ = build_report(runlog)

    out = {
        "banner": MECHANISM_BANNER,
        "label": "context delivery (mechanism): what each memory layer hands the "
                 "model, not what a model does with it",
        "config": {"seeds": seeds, "sizes": sizes, "arms": sorted(arms),
                   "profile": cfg.get("profile", "medium"),
                   "pricing": cfg.get("pricing", {}).get("label", "")},
        "token_source": ApproxTokenizer.label,
        "per_arm_size": report["per_arm_size"],
        "write_fidelity": report["write_fidelity"],
        "validity": report["validity"],
        "analytic_breakeven": costmodel.breakeven(),
    }
    out["empirical_crossover"] = _empirical_crossover(report["per_arm_size"], sizes)
    return out


def _empirical_crossover(per_arm_size, sizes):
    """Size at which A1's cached cost per session first exceeds A4's."""
    for size in sorted(sizes):
        a1 = per_arm_size.get(f"a1@{size}", {}).get("cost", {})
        a4 = per_arm_size.get(f"a4@{size}", {}).get("cost", {})
        if not a1 or not a4:
            continue
        if float(a1.get("usd_per_session_cached", 0)) > float(a4.get("usd_per_session_cached", 0)):
            return {"size": size,
                    "note": "first measured size where A1 cached $/session exceeds A4's"}
    return {"size": None, "note": "no crossover within the measured sizes"}


def render_crossover(data, fmt_name="terminal"):
    if fmt_name == "json":
        return json.dumps(data, sort_keys=True, indent=1)
    lines = [data["banner"], "", data["label"],
             f"tokens: {data['token_source']}",
             f"pricing: {data['config']['pricing']}", ""]
    hdr = ["arm@size", "gold-in-ctx%", "stale-in-ctx%", "stale-first%",
           "mem-tok/call", "$/sess cached", "$/sess uncached", "hit%"]
    md = fmt_name == "md"
    if md:
        lines.append("| " + " | ".join(hdr) + " |")
        lines.append("|" + "---|" * len(hdr))
    else:
        lines.append("  ".join(hdr))
    for key, b in sorted(data["per_arm_size"].items()):
        if not b:
            continue
        cost = b.get("cost", {})
        row = [key, b.get("gold_in_context_pct", "n/a"), b.get("stale_in_context_pct", "n/a"),
               b.get("stale_first_pct", "n/a"), str(b.get("memory_tokens_per_call", "n/a")),
               str(cost.get("usd_per_session_cached", "n/a")),
               str(cost.get("usd_per_session_uncached", "n/a")),
               str(cost.get("cache_hit_pct", "n/a"))]
        lines.append(("| " + " | ".join(row) + " |") if md else "  ".join(row))
    lines += ["",
              f"analytic break-even (costmodel §5.2): {data['analytic_breakeven']}",
              f"empirical crossover (A1 cached $ > A4): {data['empirical_crossover']}",
              "", "cause codes and unknown-unknown breakdowns: --format json",
              "scripted agent; tells you what the memory layer hands the model, "
              "not what a model does with it"]
    return "\n".join(lines)


# ------------------------------------------------------------------ demo cache

def demo_cache(calls=150, turns=15):
    """One long session: A1 prefix vs A4-tail vs A4-head through the simulator.

    Per-call cacheRead/cacheWrite curves and totals; head busts history."""
    prices = load_pricing()
    tok = ApproxTokenizer()
    arms = {}
    store_tokens = 10000
    snippet_tokens = 750
    hist_step = 520  # filler + output per call

    def run(mode):
        sim = CacheSimulator(ttl_seconds=prices.ttl_seconds,
                             min_cache_tokens=prices.min_cache_tokens,
                             max_cache_points=prices.max_cache_points, tokenizer=tok)
        history = []
        rows = []
        clock = 0.0
        calls_per_turn = calls // turns
        for t in range(turns):
            for c in range(calls_per_turn):
                blocks = []
                if mode == "a1_prefix":
                    blocks.append({"tokens": store_tokens, "key": "workspace"})
                elif mode == "a4_head":
                    blocks.append({"tokens": snippet_tokens, "key": f"head-{t}"})
                blocks.append({"cachePoint": True})
                blocks.extend(history)
                blocks.append({"cachePoint": True})
                extra = 0
                if mode in ("a4_tail", "a4_head") and c == 0:
                    extra = snippet_tokens if mode == "a4_tail" else 0
                blocks.append({"tokens": 400 + extra, "key": f"call-{t}-{c}"})
                u = sim.simulate_call(blocks, now=clock, output_tokens=120)
                clock += 2.0
                rows.append({"call": len(rows) + 1,
                             "cacheRead": u.cacheReadInputTokens,
                             "cacheWrite": u.cacheWriteInputTokens,
                             "uncached": u.inputTokens})
                history.append({"tokens": hist_step + extra, "key": f"hist-{t}-{c}"})
        totals = {"cacheRead": sum(r["cacheRead"] for r in rows),
                  "cacheWrite": sum(r["cacheWrite"] for r in rows),
                  "uncached": sum(r["uncached"] for r in rows)}
        return {"rows": rows, "totals": totals}

    arms["a1_prefix"] = run("a1_prefix")
    arms["tail"] = run("a4_tail")
    arms["head"] = run("a4_head")
    return {
        "banner": MECHANISM_BANNER,
        "session": {"calls": calls, "turns": turns, "store_tokens": store_tokens,
                    "snippet_tokens": snippet_tokens},
        "arms": {"a1_prefix": arms["a1_prefix"], "a4_tail": arms["tail"],
                 "a4_head": arms["head"]},
        "totals": {"a1_prefix": arms["a1_prefix"]["totals"],
                   "tail": arms["tail"]["totals"], "head": arms["head"]["totals"]},
        "note": ("head injection changed each turn re-writes all history behind it; "
                 "tail injection reads history from cache. Ratio names its baseline: "
                 "head cacheWrite vs tail cacheWrite."),
    }


def render_cache(data, fmt_name="terminal"):
    if fmt_name == "json":
        return json.dumps(data, sort_keys=True, indent=1)
    lines = [data["banner"], "",
             f"one session: {data['session']['calls']} calls / {data['session']['turns']} turns, "
             f"A1 store {data['session']['store_tokens']} tok, snippets "
             f"{data['session']['snippet_tokens']} tok", ""]
    for arm in ("a1_prefix", "a4_tail", "a4_head"):
        rows = data["arms"][arm]["rows"]
        t = data["arms"][arm]["totals"]
        curve = " ".join(str(r["cacheWrite"]) for r in rows[:10])
        lines.append(f"{arm:10s} totals: cacheRead={t['cacheRead']:,} "
                     f"cacheWrite={t['cacheWrite']:,} uncached={t['uncached']:,}")
        lines.append(f"           first-10-call cacheWrite curve: {curve}")
    head_w = data["totals"]["head"]["cacheWrite"]
    tail_w = data["totals"]["tail"]["cacheWrite"]
    lines += ["", f"head-inject cacheWrite / tail-inject cacheWrite = "
              f"{head_w / tail_w:.1f}x (baseline: A4 tail-inject, same session)",
              data["note"]]
    return "\n".join(lines)


# --------------------------------------------------------------- demo costmodel

def demo_costmodel():
    return {"banner": MECHANISM_BANNER,
            "label": "analytic model from research §5.2 (memory overhead only); "
                     "research parameters ($3/$15 per M, Sonnet-class list price)",
            "tables": costmodel.tables(),
            "breakeven": costmodel.breakeven()}


def render_costmodel(data, fmt_name="terminal"):
    if fmt_name == "json":
        return json.dumps(data, sort_keys=True, indent=1)
    return data["banner"] + "\n" + data["label"] + "\n" + costmodel.render_terminal()


# ------------------------------------------------------------------ demo stale

STALE_STORE = [
    "Decision: use PostgreSQL for the orders service.",
    "Decision reversed: do NOT use PostgreSQL for the orders service; use DynamoDB.",
    "Orders service runs on ECS Fargate.",
    "PostgreSQL connection pooling notes: use pgbouncer, pool size 20.",
    "The billing service uses DynamoDB streams.",
]
STALE_QUERY = "What database should the orders service use?"

RESEARCH_SPIKE_BLOCK = (
    "research spike, 2026-10-09 (Titan v2, live): "
    "'Decision: use PostgreSQL...' scored 0.680; "
    "'Decision reversed: do NOT use PostgreSQL... use DynamoDB' scored 0.493. "
    "The superseded decision outranked its reversal."
)


def demo_stale(live=False, region="us-east-1"):
    """The research §4.1 orders-service store, ranked by the active embedder."""
    if live:
        from .backends.embedders import TitanEmbedder
        emb = TitanEmbedder(region=region)
        label = "Titan v2 (live)"
    else:
        emb = HashingEmbedder()
        label = "hashing embedder, not Titan"
    qv = emb.embed(STALE_QUERY)
    ranked = sorted(((cosine(qv, emb.embed(s)), s) for s in STALE_STORE),
                    key=lambda t: (-t[0], t[1]))
    return {"banner": MECHANISM_BANNER,
            "query": STALE_QUERY,
            "embedder_label": label,
            "ranking": [{"score": _fixed(s, 3), "text": t} for s, t in ranked],
            "research_spike": RESEARCH_SPIKE_BLOCK}


def render_stale(data, fmt_name="terminal"):
    if fmt_name == "json":
        return json.dumps(data, sort_keys=True, indent=1)
    lines = [data["banner"], "",
             f"query: {data['query']}",
             f"ranking below is from the {data['embedder_label']}; offline scores are "
             "arbitrary w.r.t. semantics and only exercise the code path:", ""]
    for r in data["ranking"]:
        lines.append(f"  {r['score']}  {r['text']}")
    lines += ["", "--- labeled research spike block ---", data["research_spike"]]
    return "\n".join(lines)
