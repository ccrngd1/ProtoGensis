"""Sandbox: timeout, memory bomb, network attempt, basic I/O, empty env."""

import os

import pytest

from grading.code_sandbox import run_untrusted

IS_ROOT = os.geteuid() == 0


def test_basic_stdout():
    r = run_untrusted("print(6 * 7)")
    assert r.ok
    assert r.stdout.strip() == "42"


def test_stdin_round_trip():
    r = run_untrusted("import sys; print(sys.stdin.read().strip().upper())",
                      stdin_data="hello\n")
    assert r.ok
    assert r.stdout.strip() == "HELLO"


def test_wall_timeout():
    r = run_untrusted("import time\ntime.sleep(60)", wall_timeout_s=3)
    assert r.timed_out
    assert not r.ok


def test_cpu_spin_is_killed():
    r = run_untrusted("while True: pass", wall_timeout_s=5)
    assert not r.ok


def test_memory_bomb_killed():
    # 2 GiB AS limit: allocating ~4 GiB must fail, not OOM the host.
    r = run_untrusted(
        "x = bytearray(4 * 1024**3)\nprint('allocated')", wall_timeout_s=20
    )
    assert not r.ok
    assert "allocated" not in r.stdout


@pytest.mark.skipif(not IS_ROOT, reason="network namespace isolation requires root")
def test_network_attempt_blocked():
    code = (
        "import socket\n"
        "s = socket.create_connection(('1.1.1.1', 443), timeout=5)\n"
        "print('CONNECTED')\n"
    )
    r = run_untrusted(code, wall_timeout_s=15)
    assert not r.ok
    assert "CONNECTED" not in r.stdout


@pytest.mark.skipif(not IS_ROOT, reason="privilege drop requires root")
def test_runs_as_nobody_not_root():
    r = run_untrusted("import os; print(os.geteuid())")
    assert r.ok
    assert r.stdout.strip() != "0"


def test_env_is_empty():
    r = run_untrusted("import os; print(len([k for k in os.environ if k != 'LC_CTYPE']))")
    assert r.ok
    assert r.stdout.strip() == "0"


def test_nonzero_exit_reported():
    r = run_untrusted("raise SystemExit(3)")
    assert r.returncode == 3
    assert not r.ok
