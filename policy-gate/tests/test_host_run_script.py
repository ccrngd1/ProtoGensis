"""scripts/host_run.sh failure handling (phase 2a Bug 3). Offline: exercises
the script's own step/finish helpers in a bash subshell, no host data."""

import os
import subprocess

REPO = os.path.dirname(os.path.dirname(__file__))
SCRIPT = os.path.join(REPO, "scripts", "host_run.sh")


def _helpers():
    """Extract the top-level helper functions from the real script."""
    out = subprocess.run(
        ["sed", "-n", "/^say()/,/^}/p; /^step()/,/^}/p; /^step_sh()/,/^}/p; /^finish()/,/^}/p",
         SCRIPT], capture_output=True, text=True, check=True)
    assert "STEP FAILED" in out.stdout
    return out.stdout


def _run(snippet):
    return subprocess.run(["bash", "-c", _helpers() + "\nFAILED=0\n" + snippet],
                          capture_output=True, text=True)


def test_set_euo_pipefail():
    with open(SCRIPT, encoding="utf-8") as f:
        head = f.read(2000)
    assert "set -euo pipefail" in head


def test_failing_step_prints_and_exits_nonzero():
    r = _run('step_sh "demo step" "false"\nstep_sh "later step" "echo still-ran"\nfinish')
    assert "STEP FAILED: demo step" in r.stdout
    # independent steps still run after a failure...
    assert "still-ran" in r.stdout
    # ...but the script exits non-zero at the end
    assert r.returncode == 1
    assert "one or more steps FAILED" in r.stdout


def test_all_steps_ok_exits_zero():
    r = _run('step_sh "a" "true"\nstep ok_step true\nfinish')
    assert r.returncode == 0
    assert "STEP FAILED" not in r.stdout
    assert "all steps OK" in r.stdout


def test_usage_exits_2():
    r = subprocess.run(["bash", SCRIPT], capture_output=True, text=True)
    assert r.returncode == 2


def test_stage_b_writes_eval_results_then_lints():
    with open(SCRIPT, encoding="utf-8") as f:
        body = f.read()
    assert "results/eval-pinned-$DATE.json" in body
    assert "results/eval-pinned-latest.json" in body
    # the eval write happens before the results lint step
    assert body.index("eval-pinned-latest.json") < body.index(
        'say "stage-b: results lint"')


def test_stage_a_uses_bundle_history_with_window():
    with open(SCRIPT, encoding="utf-8") as f:
        body = f.read()
    assert "bundle history" in body
    assert "--since 2026-02-01T00:00:00Z" in body
    assert "--until 2026-09-28T00:00:00Z" in body
    assert "local/host/bundle-history.json" in body
