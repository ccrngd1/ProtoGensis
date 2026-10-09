"""Verbatim port of the research spike cost model (research §5.2, spikes/costmodel.py).

Formulas are unchanged from the spike (AC #5). Only the surrounding plumbing differs:
the spike's top-level print loop is wrapped in functions so the CLI and tests can call
it, and constants keep the spike's names and values.

Model: memory overhead only; task tokens are common to all arms and excluded.
"""

P_IN, P_OUT = 3.0, 15.0      # $/M tokens (Sonnet-class list price; parameter)
CW, CR = 1.25, 0.10          # cache write / read multipliers (5-min TTL)


def cost(tokens_in_uncached=0, cached_write=0, cached_read=0, out=0):
    return (tokens_in_uncached * P_IN + cached_write * P_IN * CW + cached_read * P_IN * CR + out * P_OUT) / 1e6


def doc_full(S, calls, turns, cache=True):
    # whole store in stable prefix; re-sent every model call
    if cache:
        rd = cost(cached_write=S, cached_read=S * (calls - 1))
    else:
        rd = cost(tokens_in_uncached=S * calls)
    wr = cost(out=600 * 1)               # one end-of-task doc edit (diff-style)
    return rd + wr


def doc_catalog(S, calls, turns, cache=True):
    C = max(500, 0.04 * S)               # catalog ~4% of store
    R = min(S, 3000)                     # agent opens ~2 docs on demand (enter context once, then ride along)
    pre = C + R
    rd = cost(cached_write=pre, cached_read=pre * (calls - 1)) if cache else cost(tokens_in_uncached=pre * calls)
    rd += cost(out=150)                  # tool-call overhead for the reads
    wr = cost(out=600)
    return rd + wr


def rag_tail(S, calls, turns, k=5, s=150, extract=True):
    inj = k * s                          # injected per user turn, appended at tail -> cached thereafter
    calls_per_turn = calls / turns
    rd = turns * cost(cached_write=inj, cached_read=inj * max(0, calls - calls_per_turn) / 1.0 / turns * 0 + 0)
    # injected snippets accumulate in history: turn i's snippets ride along for remaining calls
    tot_read = sum(inj * (calls - (i + 1) * calls_per_turn) for i in range(turns))
    rd = cost(cached_write=inj * turns, cached_read=max(0, tot_read))
    wr = turns * cost(tokens_in_uncached=2500, out=200) if extract else 0  # Mem0-style LLM fact extraction per turn
    emb = 0.02 * turns * 3000 / 1e6      # embeddings: negligible
    return rd + wr + emb


def rag_head(S, calls, turns, k=5, s=150, hist_per_call=1500, extract=True):
    # snippets injected at TOP of context and changed each turn -> busts cache for all history behind it
    calls_per_turn = calls / turns
    busted = 0
    for i in range(turns):
        hist = hist_per_call * i * calls_per_turn  # history accumulated before this turn
        busted += hist                              # must be re-written to cache once per turn
    extra = cost(cached_write=busted) - cost(cached_read=busted)
    return rag_tail(S, calls, turns, k, s, extract) + extra


SIZES = [2000, 10000, 25000, 50000, 100000]
SESSIONS = {
    "short (5 calls, 2 turns)": (5, 2),
    "medium (30 calls, 5 turns)": (30, 5),
    "long (150 calls, 15 turns)": (150, 15),
}
# Short keys for JSON output / breakeven mapping, in SESSIONS order.
SESSION_KEYS = {"short (5 calls, 2 turns)": "short",
                "medium (30 calls, 5 turns)": "medium",
                "long (150 calls, 15 turns)": "long"}

COLUMNS = [
    ("doc_full_cached", lambda S, c, t: doc_full(S, c, t)),
    ("doc_full_uncached", lambda S, c, t: doc_full(S, c, t, False)),
    ("doc_catalog", lambda S, c, t: doc_catalog(S, c, t)),
    ("rag_tail_extract", lambda S, c, t: rag_tail(S, c, t)),
    ("rag_tail_no_extract", lambda S, c, t: rag_tail(S, c, t, extract=False)),
    ("rag_head_inject", lambda S, c, t: rag_head(S, c, t)),
]

COLUMN_HEADERS = [
    "doc full-load (cached)", "doc full-load (no cache)", "doc catalog+on-demand",
    "RAG tail-inject (+extract)", "RAG tail (no extract)", "RAG head-inject (cache-busting)",
]


def tables():
    """All three research §5.2 tables as {session_key: {size: {column: $}}}."""
    out = {}
    for name, (c, t) in SESSIONS.items():
        key = SESSION_KEYS[name]
        out[key] = {str(S): {col: fn(S, c, t) for col, fn in COLUMNS} for S in SIZES}
    return out


def breakeven():
    """Break-even store size per session profile: doc full-load (cached) vs RAG tail+extract.

    Same scan as the spike: S in 1000..400000 step 1000, first S where doc_full > rag_tail.
    """
    out = {}
    for name, (c, t) in SESSIONS.items():
        lo = None
        for S in range(1000, 400001, 1000):
            if doc_full(S, c, t) > rag_tail(S, c, t):
                lo = S
                break
        out[SESSION_KEYS[name]] = lo
    return out


def render_terminal():
    """Reproduce the spike's printed tables and break-even lines as a string."""
    lines = []
    for name, (c, t) in SESSIONS.items():
        lines.append("")
        lines.append("## " + name)
        lines.append("| store S (tokens) | " + " | ".join(COLUMN_HEADERS) + " |")
        lines.append("|---|" + "---|" * len(COLUMN_HEADERS))
        for S in SIZES:
            cells = " | ".join(f"${fn(S, c, t):.4f}" for _, fn in COLUMNS)
            lines.append(f"| {S:,} | {cells} |")
    lines.append("")
    be = breakeven()
    for name in SESSIONS:
        lines.append(f"{name} breakeven S ≈ {be[SESSION_KEYS[name]]}")
    return "\n".join(lines)
