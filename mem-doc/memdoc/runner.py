"""Runner (AC #4): fresh context per session, every model call recorded.

Mock mode: MockAgent + HashingEmbedder + CacheSimulator; every call event has
source=cache_simulator; token counts come from ApproxTokenizer (labeled
estimate). Each session emits exactly the profile's call count with identical
filler task tokens across arms, so mock costs are comparable to `costmodel`.

Live mode lives in agent/converse.py ([bedrock]); this module only enforces its
gating (prereg verify, --max-usd).

Size control (AC #3): distractor sessions from the committed pool are added
incrementally from a deterministic size ladder until A1's measured store lands
within ±15% of the target. The same distractor sequence is used for every arm.
"""

from dataclasses import dataclass, field
from pathlib import Path

from .backends import registry
from .cache_sim import CacheSimulator
from .cost import load_pricing
from .agent.mock import MockAgent, ToolPolicy, ContextReader
from .tasks.schema import SESSION_PROFILES, load_all, load_distractors
from .tasks.generate import remap_canaries
from .text import contains_canary
from .tokens import ApproxTokenizer
from .runlog import RunLog, deterministic_run_id, git_head

FILLER_TOKENS_PER_CALL = 400     # identical task tokens across arms
FILLER_OUT_TOKENS = 120
SIZE_TOLERANCE = 0.15


@dataclass
class SessionCtx:
    """What the runner hands to backend.bootstrap: no conversation history."""
    session_id: str
    index: int
    probes: list = field(default_factory=list)


@dataclass
class CellResult:
    arm: str
    size: int
    seed: int
    storyline: str
    category: int
    probes: list = field(default_factory=list)       # per-probe dicts
    usages: list = field(default_factory=list)       # per-call usage dicts
    health: dict = field(default_factory=dict)
    write_fidelity: list = field(default_factory=list)
    store_tokens: int = 0
    memory_tokens_per_call: float = 0.0


def _distractor_ladder(distractors, target_tokens, tok, probe_fn):
    """Deterministic ladder: add distractor sessions until probe_fn() lands in
    the ±15% band. Returns the chosen count. probe_fn(count) -> measured tokens."""
    lo_ok = target_tokens * (1 - SIZE_TOLERANCE)
    hi_ok = target_tokens * (1 + SIZE_TOLERANCE)
    count = 0
    measured = probe_fn(0)
    if measured >= lo_ok:
        return 0, measured
    step = max(1, len(distractors) // 64)
    while count < len(distractors):
        count = min(len(distractors), count + step)
        measured = probe_fn(count)
        if measured > hi_ok:
            # overshot: back off one step and finish with single steps
            count = max(0, count - step)
            measured = probe_fn(count)
            if step == 1:
                break
            step = 1
            continue
        if measured >= lo_ok:
            break
    return count, measured


class _DistractorSizer:
    """Measures A1 store size at a distractor count, deterministically, by
    summing the token estimate of the seed docs + fact lines + distractor files.
    This mirrors exactly what DocFullBackend.fill_distractors writes."""

    def __init__(self, storyline, distractors, tok):
        self.tok = tok
        from .backends.doc_full import AGENTS_SEED, MEMORY_SEED
        base = self.tok.count(AGENTS_SEED) + self.tok.count(MEMORY_SEED)
        base += sum(self.tok.count(f"- {f.text}\n") for f in storyline.facts)
        self.base = base
        self.d_tokens = [self.tok.count(f"# Session notes {d.id}\n\n" +
                                        "\n".join(f"- {ln}" for ln in d.lines) + "\n")
                         for d in distractors]
        self._prefix = [0]
        for t in self.d_tokens:
            self._prefix.append(self._prefix[-1] + t)

    def measure(self, count):
        return self.base + self._prefix[count]


def run_mock(arms, sizes, seeds, out_dir, tasks_dir="tasks", categories=None,
             profile=None, p_forget=0.0, log_name="runlog.jsonl",
             storyline_ids=None, arm_configs=None):
    """Run the full mock matrix; returns (results, runlog_path)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tok = ApproxTokenizer()
    prices = load_pricing()
    base_storylines = load_all(tasks_dir)
    distractors = load_distractors(tasks_dir)
    if categories:
        base_storylines = [s for s in base_storylines if s.category in categories]
    if storyline_ids:
        base_storylines = [s for s in base_storylines if s.id in storyline_ids]

    from . import prereg
    log = RunLog(out_dir / log_name)
    run_id = deterministic_run_id({"arms": list(arms), "sizes": list(sizes),
                                   "seeds": list(seeds), "p_forget": p_forget})
    log.write({"event": "run_header", "run_id": run_id, "mode": "mock",
               "prereg_hash": prereg.prereg_hash(), "git_head": git_head(Path.cwd()),
               "arms": sorted(arms), "sizes": sorted(sizes), "seeds": sorted(seeds),
               "token_source": tok.label, "banner": _banner()})

    reg = registry()
    results = []
    for seed in seeds:
        storylines = remap_canaries(base_storylines, seed) if seed != 41 else base_storylines
        for storyline in storylines:
            prof = profile or storyline.session_profile
            calls_per_session, turns = SESSION_PROFILES[prof]
            sizer = _DistractorSizer(storyline, distractors, tok)
            for size in sizes:
                d_count, measured = _distractor_ladder(
                    distractors, size, tok, sizer.measure)
                d_slice = distractors[:d_count]
                for arm in arms:
                    cell = _run_cell(reg, arm, storyline, d_slice, seed, size,
                                     calls_per_session, turns, tok, prices, log,
                                     run_id, p_forget, out_dir,
                                     (arm_configs or {}).get(arm))
                    cell.store_tokens = cell.store_tokens or measured
                    results.append(cell)
    log.write({"event": "run_end", "run_id": run_id, "cells": len(results)})
    log.close()
    return results, out_dir / log_name


def _banner():
    from . import MECHANISM_BANNER
    return MECHANISM_BANNER


def _blocks_tokens(tok, text):
    return tok.count(text)


def _run_cell(reg, arm, storyline, distractors, seed, size, calls_per_session,
              turns, tok, prices, log, run_id, p_forget, out_dir, arm_config=None):
    import tempfile
    workdir = Path(tempfile.mkdtemp(prefix=f"memdoc-{arm}-"))
    cfg = dict(arm_config or {})
    if arm == "a1":
        cfg.setdefault("git_commits", False)  # speed: per-session commits exercised in tests
    backend = reg[arm](workdir, tok, cfg)
    agent = MockAgent(p_forget=p_forget, seed=seed)
    sim = CacheSimulator(ttl_seconds=prices.ttl_seconds,
                         min_cache_tokens=prices.min_cache_tokens,
                         max_cache_points=prices.max_cache_points, tokenizer=tok)
    cell = CellResult(arm=arm, size=size, seed=seed, storyline=storyline.id,
                      category=storyline.category)

    # ---- distractor fill (same sequence for every arm) ----
    fill = getattr(backend, "fill_distractors", None)
    if fill:
        fill(distractors)

    clock = 0.0
    write_sessions = [s for s in storyline.sessions if s.kind == "write"]
    probe_sessions = [s for s in storyline.sessions if s.kind == "probe"]
    mem_tokens_total, call_count = 0, 0
    sess_probes = {}
    for p in storyline.probes:
        sess_probes.setdefault(p.session, []).append(p)

    history_keys = {}   # session -> list of history block keys (fresh-context check)

    def run_session(sess, probes):
        nonlocal clock, mem_tokens_total, call_count
        ctx = SessionCtx(session_id=f"{storyline.id}-s{sess.index}", index=sess.index,
                         probes=probes)
        parts = backend.bootstrap(ctx)
        history = []        # this session's own blocks; never carried across
        history_keys[sess.index] = []
        prefix_text = parts.system_prefix
        prefix_tokens = _blocks_tokens(tok, prefix_text)
        gathered_lines = []
        if probes:
            for p in probes:
                gathered_lines.extend(ToolPolicy.gather(backend, p))
        # tail/head injection from on_turn (A3/A4 style)
        for t in range(turns):
            turn_text = f"turn {t}: filler task content for session {sess.index}"
            inj = backend.on_turn(type("Turn", (), {"text": turn_text})())
            calls_this_turn = calls_per_session // turns + (1 if t < calls_per_session % turns else 0)
            for c in range(calls_this_turn):
                blocks = [{"tokens": prefix_tokens,
                           "key": f"prefix:{arm}:{storyline.id}:{sess.index}:{_hash(prefix_text)}"}]
                if inj.head:
                    blocks.append({"tokens": tok.count(inj.head),
                                   "key": f"head:{sess.index}:{t}:{_hash(inj.head)}"})
                blocks.append({"cachePoint": True})
                for hk, htok in history:
                    blocks.append({"tokens": htok, "key": hk})
                blocks.append({"cachePoint": True})
                tail_extra = tok.count(inj.tail) if inj.tail and c == 0 else 0
                blocks.append({"tokens": FILLER_TOKENS_PER_CALL + tail_extra,
                               "key": f"call:{sess.index}:{t}:{c}"})
                usage = sim.simulate_call(blocks, now=clock,
                                          output_tokens=FILLER_OUT_TOKENS)
                clock += 2.0
                u = usage.as_dict()
                u.update({"source": "cache_simulator", "call_type": "task"})
                cell.usages.append(u)
                mem_blocks = prefix_tokens + (tok.count(inj.head) if inj.head else 0) \
                    + (tok.count(inj.tail) if inj.tail else 0)
                mem_tokens_total += mem_blocks
                call_count += 1
                log.write({"event": "call", "run_id": run_id, "arm": arm, "size": size,
                           "storyline": storyline.id, "seed": seed,
                           "session": sess.index, "call_idx": call_count,
                           "source": "cache_simulator", "call_type": "task", **usage.as_dict()})
                hk = f"hist:{sess.index}:{t}:{c}"
                history.append((hk, FILLER_TOKENS_PER_CALL + FILLER_OUT_TOKENS + tail_extra))
                history_keys[sess.index].append(hk)
            if inj.tail:
                # injected snippets ride along in history for later calls
                pass
        return parts, gathered_lines

    # ---- write phase ----
    for sess in write_sessions:
        parts, _ = run_session(sess, [])
        agent.writer.apply_session(backend, storyline, sess.index)
        report = backend.on_session_end(
            type("Transcript", (), {"session_id": f"{storyline.id}-s{sess.index}"})())
        if report.extraction_calls or report.output_tokens or report.input_tokens:
            u = {"inputTokens": report.input_tokens, "cacheReadInputTokens": 0,
                 "cacheWriteInputTokens": 0, "outputTokens": report.output_tokens,
                 "source": "cache_simulator", "call_type": "write_path"}
            cell.usages.append(u)
            call_count += 1
            log.write({"event": "call", "run_id": run_id, "arm": arm, "size": size,
                       "storyline": storyline.id, "seed": seed, "session": sess.index,
                       "call_idx": call_count, **u})
        # write fidelity (AC #9): canary present in store; superseded removed/marked
        snapshot = backend.store_snapshot()
        store_text = "\n".join(snapshot.texts.values())
        for f in storyline.facts:
            if f.session != sess.index:
                continue
            present = contains_canary(store_text, f.canary)
            superseded_gone = True
            if f.kind == "correct_explicit" and f.supersedes:
                superseded_gone = not _stored_as_current(snapshot, backend, f.supersedes)
            fid = {"event": "write_fidelity", "run_id": run_id, "arm": arm, "size": size,
                   "storyline": storyline.id, "seed": seed, "session": sess.index,
                   "fact_key": f.key, "present": present,
                   "superseded_handled": superseded_gone}
            cell.write_fidelity.append(fid)
            log.write(fid)

    # ---- probe phase (fresh context per session) ----
    snapshot = backend.store_snapshot()
    cell.store_tokens = snapshot.token_estimate
    store_text_full = "\n".join(snapshot.texts.values())
    for sess in probe_sessions:
        probes = sess_probes.get(sess.index, [])
        parts, gathered = run_session(sess, probes)
        context_lines = (parts.system_prefix.splitlines() + gathered)
        for p in probes:
            if arm == "astar":
                # AC #1: the oracle injects the current gold facts *for the
                # probe*, so its scoring context is rebuilt per probe
                p_parts = backend.bootstrap(SessionCtx(
                    session_id=f"{storyline.id}-s{sess.index}", index=sess.index,
                    probes=[p]))
                context_lines_p = p_parts.system_prefix.splitlines()
            else:
                context_lines_p = context_lines
            inj = backend.on_turn(type("Turn", (), {"text": p.prompt})())
            p_context = context_lines_p + inj.head.splitlines() + inj.tail.splitlines()
            answer = ContextReader.answer(p_context, p)
            ctx_text = "\n".join(p_context)
            gold_in_ctx = p.gold != "ABSTAIN" and contains_canary(ctx_text, p.gold)
            stale_in_ctx = bool(p.stale) and contains_canary(ctx_text, p.stale)
            stale_first = False
            if gold_in_ctx and stale_in_ctx:
                stale_first = ctx_text.find(p.stale) < ctx_text.find(p.gold)
            rec = {"event": "probe", "run_id": run_id, "arm": arm, "size": size,
                   "storyline": storyline.id, "seed": seed, "category": storyline.category,
                   "session": sess.index, "probe_id": p.id, "kind": p.kind,
                   "gold": p.gold, "stale": p.stale, "answer": answer,
                   "depth": p.depth, "unknown_unknown": p.unknown_unknown,
                   "fact_in_context": gold_in_ctx, "stale_in_context": stale_in_ctx,
                   "stale_first": stale_first,
                   "gold_in_store": p.gold != "ABSTAIN" and contains_canary(store_text_full, p.gold),
                   "stale_stored_current": bool(p.stale) and _stored_as_current(snapshot, backend, p.stale),
                   "read_policy": backend.read_policy}
            cell.probes.append(rec)
            log.write(rec)

    # ---- health signals (AC #6) ----
    cell.memory_tokens_per_call = round(mem_tokens_total / call_count, 2) if call_count else 0.0
    health = {"event": "cell", "run_id": run_id, "arm": arm, "size": size,
              "storyline": storyline.id, "seed": seed,
              "embedding_calls": getattr(backend, "embedding_calls", 0),
              "retrieval_hits": getattr(backend, "retrieval_hits", 0),
              "catalog_nonempty": _catalog_nonempty(backend),
              "transcript_count": getattr(backend, "transcript_count", lambda: 0)()
              if arm == "a6" else 0,
              "core_loaded": _core_loaded(backend),
              "store_tokens": cell.store_tokens,
              "memory_tokens_per_call": cell.memory_tokens_per_call,
              "tools_registered": [t.name for t in backend.tools()]}
    cell.health = health
    log.write(health)
    _cleanup(workdir)
    return cell


def _hash(text):
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _stored_as_current(snapshot, backend, canary):
    """True if the superseded canary is still stored as a current value."""
    if snapshot.kind == "entries":
        store = getattr(backend, "store", None)
        if store:
            return any(canary in e["text"] and not e["superseded"]
                       for e in store.all_entries())
    if snapshot.kind == "tiered":
        # the budgeted core is the curated current tier; episodic notes are history
        core = snapshot.texts.get("CORE.md", "")
        return contains_canary(core, canary)
    if snapshot.kind == "transcripts":
        return False   # transcripts are raw history, nothing is "current"
    text = "\n".join(snapshot.texts.values())
    return contains_canary(text, canary)


def _catalog_nonempty(backend):
    if backend.arm_id != "a2":
        return True
    return len(backend.catalog_entries()) > 0


def _core_loaded(backend):
    if backend.arm_id in ("a1",):
        return bool(backend.store_snapshot().texts)
    if backend.arm_id in ("a5", "a5bg"):
        return "CORE.md" in backend.store_snapshot().texts
    return True


def _cleanup(workdir):
    import shutil
    shutil.rmtree(workdir, ignore_errors=True)
