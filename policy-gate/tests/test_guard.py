"""Guard tests (AC #2). Each planted violation raises; allowed reads pass."""

import os
import sqlite3
import subprocess

import pytest

from policygate import guard


@pytest.fixture()
def protected(tmp_path):
    root = tmp_path / "guard_root"
    root.mkdir()
    guard.install()
    guard.add_roots([str(root)])
    return root


def test_selftest_blocks_all_nine(tmp_path):
    ok, lines = guard.selftest(str(tmp_path / "fresh_root"))
    assert ok
    assert lines[0] == "GUARD OK: 9/9 planted violations blocked"


def test_selftest_on_existing_empty_dir(tmp_path):
    d = tmp_path / "already_there"
    d.mkdir()
    ok, lines = guard.selftest(str(d))
    assert ok


def test_write_open_blocked(protected):
    with pytest.raises(guard.GuardViolation):
        open(protected / "x.txt", "w")


def test_append_open_blocked(protected):
    with pytest.raises(guard.GuardViolation):
        open(protected / "x.txt", "a")


def test_read_open_allowed_elsewhere(tmp_path, protected):
    p = tmp_path / "outside.txt"
    p.write_text("ok")
    assert p.read_text() == "ok"


def test_rename_blocked(protected):
    with pytest.raises(guard.GuardViolation):
        os.rename(protected / "a", protected / "b")


def test_mkdir_blocked(protected):
    with pytest.raises(guard.GuardViolation):
        os.mkdir(protected / "sub")


def test_sqlite_blocked(protected):
    with pytest.raises(guard.GuardViolation):
        sqlite3.connect(protected / "db.sqlite")


def test_git_status_blocked(protected):
    with pytest.raises(guard.GuardViolation):
        subprocess.run(["git", "-C", str(protected), "status"])


def test_git_checkout_blocked(protected):
    with pytest.raises(guard.GuardViolation):
        subprocess.run(["git", "-C", str(protected), "checkout", "main"])


def test_git_log_allowed(protected):
    # allowed read subcommand: must not raise GuardViolation (git itself may
    # fail since the dir is not a repo; that is fine)
    subprocess.run(["git", "-C", str(protected), "log", "-1"], capture_output=True)


def test_git_show_allowed(protected):
    subprocess.run(["git", "-C", str(protected), "show", "HEAD"], capture_output=True)


def test_openclaw_blocked_everywhere(protected):
    with pytest.raises(guard.GuardViolation):
        subprocess.run(["openclaw", "--version"])


def test_bash_c_write_into_root_blocked(protected):
    with pytest.raises(guard.GuardViolation):
        subprocess.run(["bash", "-c", f"echo x > {protected}/f"])


def test_writes_outside_roots_pass(tmp_path):
    guard.install()
    out = tmp_path / "out"
    out.mkdir()
    (out / "r.json").write_text("{}")
    assert (out / "r.json").exists()


# ---- test-isolation regression (phase 5): a guard-installing test must not
# block a later test's subprocess calls. The two tests below run in definition
# order in one process and simulate the real suite ordering that broke the
# checklist line "pytest offline, empty HOME, no creds": guard tests install
# the hook in-process, then the host tests spawn
# `python -m policygate.cli ... --root /root/.openclaw` and the leaked roots
# made the spawn itself a violation. The autouse _guard_roots_isolated fixture
# clears the registered roots between tests; these tests prove it.

def test_isolation_step1_installs_guard_and_roots(tmp_path):
    root = tmp_path / "leaky_root"
    root.mkdir()
    guard.install()
    guard.add_roots([str(root)])
    with pytest.raises(guard.GuardViolation):
        open(root / "x.txt", "w")


def test_isolation_step2_subprocess_naming_root_passes(tmp_path):
    # offline stand-in for the host tests' CLI spawn: argv NAMES the protected
    # root (as `--root /root/.openclaw` does) but only prints; without the
    # fixture's reset, step 1's leaked roots make this spawn raise.
    import sys as _sys
    r = subprocess.run(
        [_sys.executable, "-c", "print('spawned-ok')", "--root", "/root/.openclaw"],
        capture_output=True, text=True)
    assert r.stdout.strip() == "spawned-ok"
    # the reset never weakens the openclaw-binary block (root-independent)
    with pytest.raises(guard.GuardViolation):
        subprocess.run(["openclaw", "--version"])
    # and a fresh install() re-registers the always-protected roots in full:
    # the same spawn raises again while they are registered
    guard.install()
    with pytest.raises(guard.GuardViolation):
        subprocess.run(
            [_sys.executable, "-c", "print('x')", "--root", "/root/.openclaw"],
            capture_output=True, text=True)
    guard._reset_registered_roots()


def test_gitread_rejects_non_allowlisted(tmp_path):
    from policygate import gitread
    with pytest.raises(gitread.GitReadError):
        gitread.run(tmp_path, ["status"])
    with pytest.raises(gitread.GitReadError):
        gitread.run(tmp_path, ["checkout", "x"])
    with pytest.raises(gitread.GitReadError):
        gitread.run(tmp_path, ["config", "safe.directory", "x"])
