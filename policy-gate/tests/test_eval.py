"""Eval tests (AC #19, #20)."""

import json
import subprocess
import sys
from pathlib import Path

from policygate import evaluate

REPO = Path(__file__).parent.parent
FIX = REPO / "fixtures" / "eval"


def test_matches_expected():
    out = evaluate.eval_cmd(str(FIX / "run"), str(FIX / "labels.jsonl"), baseline="keyword")
    expected = json.loads((FIX / "expected.json").read_text())
    assert out == expected


def test_eval_diff_byte_identical():
    r = subprocess.run([sys.executable, "-m", "policygate.cli", "eval",
                        "--run", str(FIX / "run"), "--labels", str(FIX / "labels.jsonl"),
                        "--baseline", "keyword", "--format", "json"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.stdout == (FIX / "expected.json").read_text()


def test_label_status_rule():
    # if a policy-silent row lacks cc_confirmed -> provisional
    import tempfile
    import os
    labels = [
        {"action_key": "k1", "label": "policy-silent", "cc_confirmed": False},
    ]
    with tempfile.TemporaryDirectory() as d:
        run = os.path.join(d, "run")
        os.makedirs(run)
        with open(os.path.join(run, "actions.jsonl"), "w") as f:
            f.write(json.dumps({"action_key": "k1", "readings": {"strict": "ALLOW",
                    "plan": "ALLOW", "lenient": "ALLOW"}}) + "\n")
        with open(os.path.join(run, "ambiguity.json"), "w") as f:
            f.write('{"items": []}')
        lp = os.path.join(d, "labels.jsonl")
        with open(lp, "w") as f:
            for lab in labels:
                f.write(json.dumps(lab) + "\n")
        out = evaluate.eval_cmd(run, lp)
        assert out["label_status"] == "provisional"


def test_keyword_baseline_label():
    out = evaluate.eval_cmd(str(FIX / "run"), str(FIX / "labels.jsonl"), baseline="keyword")
    assert out["baselines"]["keyword"]["label"] == \
        "agenthook-style keyword baseline (our reimplementation, not agenthook)"


def test_label_breakdowns_aggregate_only(tmp_path):
    # blocked_by_label / fired_by_label / borderline_counts: label names and
    # rule IDs with counts only (the eval-strict-fp and fbd08 claim rows)
    run = tmp_path / "run"
    run.mkdir()
    acts = [
        {"action_key": "a", "readings": {"strict": "BLOCK", "plan": "BLOCK", "lenient": "ALLOW"},
         "fired_by_reading": {"strict": ["R-FBD-08"], "plan": ["R-FBD-08"], "lenient": []}},
        {"action_key": "b", "readings": {"strict": "BLOCK", "plan": "ALLOW", "lenient": "ALLOW"},
         "fired_by_reading": {"strict": ["R-FBD-08", "R-PRE-01"], "plan": [], "lenient": []}},
        {"action_key": "c", "readings": {"strict": "ALLOW", "plan": "ALLOW", "lenient": "ALLOW"}},
    ]
    (run / "actions.jsonl").write_text("".join(json.dumps(a) + "\n" for a in acts))
    labels = [
        {"action_key": "a", "label": "unauthorized", "borderline": True},
        {"action_key": "b", "label": "authorized-plan", "borderline": True},
        {"action_key": "c", "label": "policy-silent"},
    ]
    lp = tmp_path / "labels.jsonl"
    lp.write_text("".join(json.dumps(l) + "\n" for l in labels))
    out = evaluate.eval_cmd(str(run), str(lp))
    s = out["readings"]["strict"]
    assert s["fp"] == 1 and s["blocked_by_label"] == {"authorized-plan": 1, "unauthorized": 1}
    assert s["fired_by_label"]["R-FBD-08"] == {"authorized-plan": 1, "unauthorized": 1}
    assert s["fired_by_label"]["R-PRE-01"] == {"authorized-plan": 1}
    assert out["readings"]["lenient"]["blocked_by_label"] == {}
    assert out["borderline_counts"] == {"authorized-plan": 1, "unauthorized": 1}
