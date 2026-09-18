"""AC3: hooks path and transcript-replay path must yield the identical
actual_accessed set on the same recorded session."""

from conftest import FILES, make_transcript, make_hook_log

from honesty_gate.capture import hooks, transcript


def test_capture_parity_identical_sets(tmp_path):
    reads = FILES[:4]
    failed = [FILES[4]]
    bash = ["cat src/hidden.py", "grep -n TODO src/file9.py"]

    t = make_transcript(tmp_path / "t.jsonl", reads=reads, failed_reads=failed,
                        bash_commands=bash, final_text="done")
    h = make_hook_log(tmp_path / "h.jsonl", reads=reads, failed_reads=failed,
                      bash_commands=bash)

    from_transcript = transcript.collect_accessed(t)
    from_hooks = hooks.collect_accessed(h)
    assert from_transcript == from_hooks == set(reads)


def test_failed_reads_never_count(tmp_path):
    t = make_transcript(tmp_path / "t.jsonl", reads=[], failed_reads=FILES,
                        final_text="done")
    h = make_hook_log(tmp_path / "h.jsonl", reads=[], failed_reads=FILES)
    assert transcript.collect_accessed(t) == set()
    assert hooks.collect_accessed(h) == set()


def test_bash_reads_are_blind_spot_on_both_paths(tmp_path):
    # documents the disclosed blind spot: bash file access is invisible
    bash = [f"cat {FILES[0]}"]
    t = make_transcript(tmp_path / "t.jsonl", reads=[], bash_commands=bash,
                        final_text="done")
    h = make_hook_log(tmp_path / "h.jsonl", reads=[], bash_commands=bash)
    assert transcript.collect_accessed(t) == set()
    assert hooks.collect_accessed(h) == set()


def test_hook_handler_roundtrip(tmp_path, monkeypatch):
    """Events fed through the actual stdin handler produce the same set."""
    import io, json
    monkeypatch.setenv("HONESTY_GATE_LOG_DIR", str(tmp_path / "logs"))
    sid = "sess-roundtrip"
    for p in FILES[:2]:
        payload = {"session_id": sid, "cwd": "/work/demo", "tool_name": "Read",
                   "tool_input": {"file_path": p},
                   "tool_response": {"success": True}}
        hooks.run_handler("PreToolUse", stdin=io.StringIO(json.dumps(payload)))
        hooks.run_handler("PostToolUse", stdin=io.StringIO(json.dumps(payload)))
    hooks.run_handler("Stop", stdin=io.StringIO(json.dumps({"session_id": sid})))
    log = hooks.session_log_path(sid)
    assert hooks.collect_accessed(log) == set(FILES[:2])


def test_handler_never_fails_on_garbage(monkeypatch, tmp_path, capsys):
    import io
    monkeypatch.setenv("HONESTY_GATE_LOG_DIR", str(tmp_path / "logs"))
    assert hooks.run_handler("PostToolUse", stdin=io.StringIO("not json{")) == 0


def test_install_and_status_roundtrip(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text('{"model": "opus", "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "existing-hook"}]}]}}')
    info = hooks.install(str(settings))
    assert set(info["installed"]) == set(hooks.HOOK_EVENTS)
    # idempotent
    info2 = hooks.install(str(settings))
    assert info2["installed"] == []
    st = hooks.status(str(settings))
    assert all(st["registered"].values())
    # pre-existing unrelated hook and settings preserved
    import json
    data = json.loads(settings.read_text())
    assert data["model"] == "opus"
    cmds = [h["command"] for b in data["hooks"]["PreToolUse"] for h in b["hooks"]]
    assert "existing-hook" in cmds
