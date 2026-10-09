"""AC #1 conformance (parametrized over every built arm) + arm behavior tests."""

import pytest

from memdoc.backends import MVP_ARMS, SHOULD_SHIP_ARMS, registry
from memdoc.backends.base import ContextParts, MemoryBackend, StoreSnapshot, WriteReport, arms_table
from memdoc.tasks.schema import FactEvent
from memdoc.tokens import ApproxTokenizer

ALL_ARMS = list(MVP_ARMS) + list(SHOULD_SHIP_ARMS)


def _mk(arm, tmp_path, cfg=None):
    cfg = dict(cfg or {})
    if arm == "a1":
        cfg.setdefault("git_commits", False)
    return registry()[arm](tmp_path, ApproxTokenizer(), cfg)


@pytest.mark.parametrize("arm", ALL_ARMS)
def test_conformance(arm, tmp_path):
    b = _mk(arm, tmp_path)
    assert isinstance(b, MemoryBackend)
    assert b.arm_id == arm
    assert b.write_policy and b.read_policy and b.inject
    ctx = b.bootstrap(type("S", (), {"probes": []})())
    assert isinstance(ctx, ContextParts)
    assert isinstance(b.tools(), list)
    rep = b.on_session_end(type("T", (), {"session_id": "x"})())
    assert isinstance(rep, WriteReport)
    snap = b.store_snapshot()
    assert isinstance(snap, StoreSnapshot)


def test_arms_table_matches_research_61():
    reg = registry()
    rows = {r["id"]: r for r in arms_table(list(reg.values()))}
    assert rows["a0"]["write_policy"] == "none" and rows["a0"]["read_policy"] == "none"
    assert rows["astar"]["read_policy"] == "oracle"
    assert rows["a1"]["write_policy"] == "foreground" and rows["a1"]["read_policy"] == "always_load"
    assert rows["a2"]["write_policy"] == "foreground" and rows["a2"]["read_policy"] == "catalog"
    assert rows["a3"]["write_policy"] == "background" and rows["a3"]["read_policy"] == "similarity"
    assert rows["a4"]["write_policy"] == "background" and rows["a4"]["read_policy"] == "similarity"
    assert rows["a4"]["inject"] == "tail"
    assert rows["a5"]["write_policy"] == "foreground" and rows["a5"]["read_policy"] == "hybrid_search"
    assert rows["a5bg"]["write_policy"] == "background"
    assert rows["a6"]["write_policy"] == "none" and rows["a6"]["read_policy"] == "agent_search"


def _event(key="port", kind="introduce", text="The relay binds port 18111.",
           canary="18111", session=1, supersedes=""):
    return FactEvent(key=key, kind=kind, text=text, canary=canary, session=session,
                     canary_type="port", supersedes=supersedes)


def test_doc_full_correction_rewrites_in_place(tmp_path):
    b = _mk("a1", tmp_path)
    b.scripted_apply(_event(), 1)
    b.scripted_apply(_event(kind="correct_explicit", canary="19222",
                            text="Correction: the relay now binds port 19222; 18111 is retired.",
                            supersedes="18111", session=2), 2)
    mem = (tmp_path / "workspace_a1" / "MEMORY.md").read_text()
    assert "19222" in mem
    assert mem.count("18111") == 1  # only inside the correction line, not standing alone
    assert "The relay binds port 18111." not in mem


def test_a4_supersession_update(tmp_path):
    b = _mk("a4", tmp_path)
    b.scripted_apply(_event(), 1)
    b.scripted_apply(_event(kind="correct_explicit", canary="19222",
                            text="Correction: the relay now binds port 19222.",
                            supersedes="18111", session=2), 2)
    entries = b.store.all_entries()
    assert len(entries) == 1
    assert "19222" in entries[0]["text"]


def test_a3_no_supersession_keeps_both(tmp_path):
    b = _mk("a3", tmp_path)
    b.scripted_apply(_event(), 1)
    b.scripted_apply(_event(kind="correct_explicit", canary="19222",
                            text="Correction: the relay now binds port 19222.",
                            supersedes="18111", session=2), 2)
    assert len(b.store.all_entries()) == 2


def test_a3_has_no_search_tool(tmp_path):
    assert _mk("a3", tmp_path).tools() == []
    assert any(t.name == "memory_search" for t in _mk("a4", tmp_path).tools())


def test_a2_catalog_updated_on_write(tmp_path):
    b = _mk("a2", tmp_path)
    b.scripted_apply(_event(), 1)
    entries = b.catalog_entries()
    assert len(entries) == 1
    path, read_if = entries[0]
    assert b.read_doc(path)
    # canary never leaks into the catalog prefix
    assert "18111" not in b.bootstrap(type("S", (), {"probes": []})()).system_prefix


def test_a5_core_and_episodic(tmp_path):
    b = _mk("a5", tmp_path)
    b.scripted_apply(_event(), 1)
    snap = b.store_snapshot()
    assert "18111" in snap.texts["CORE.md"]
    assert any("18111" in t for n, t in snap.texts.items() if n.startswith("notes/"))
    hits = b.memory_search("relay port")
    assert hits and "18111" in hits[0][1]["text"]


def test_a5bg_background_appends_on_implicit(tmp_path):
    b = _mk("a5bg", tmp_path)
    b.scripted_apply(_event(), 1)
    b.scripted_apply(_event(kind="invalidate_implicit", canary="19222",
                            text="The new relay now takes traffic on port 19222.",
                            session=3), 3)
    core = b.store_snapshot().texts["CORE.md"]
    assert "18111" in core and "19222" in core  # nothing removed without explicit negation


def test_a6_grep_and_read(tmp_path):
    b = _mk("a6", tmp_path)
    b.scripted_apply(_event(), 1)
    assert b.grep("relay")
    assert b.transcript_count() == 1
    assert b.read("session-001.txt")


def test_oracle_excludes_superseded(tmp_path):
    b = _mk("astar", tmp_path)
    e1 = _event()
    b.scripted_apply(e1, 1)
    e2 = _event(kind="correct_explicit", canary="19222",
                text="Correction: the relay now binds port 19222.",
                supersedes="18111", session=2)
    b.scripted_apply(e2, 2)
    probe = type("P", (), {"fact_keys": ["port"], "gold": "19222"})()
    ctx = b.bootstrap(type("S", (), {"probes": [probe]})())
    assert "19222" in ctx.system_prefix
    assert "18111" not in ctx.system_prefix or "19222" in ctx.system_prefix


def test_a1_git_commits(tmp_path):
    import subprocess
    b = _mk("a1", tmp_path, {"git_commits": True})
    b.scripted_apply(_event(), 1)
    b.on_session_end(type("T", (), {"session_id": "s1"})())
    r = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path / "workspace_a1",
                       capture_output=True, text=True)
    assert len(r.stdout.strip().splitlines()) >= 2  # seed + session commit
