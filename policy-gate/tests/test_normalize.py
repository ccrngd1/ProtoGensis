"""Normalizer tests incl. spike-parity unit test (AC #9)."""

import json
from pathlib import Path

import pytest

from policygate import normalize
from tests.spike_ref import spike_replay

CORPUS = Path(__file__).parent.parent / "fixtures" / "normalizer" / "cases.jsonl"


def _corpus_cmds():
    out = []
    with open(CORPUS, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if "cmd" in d:
                out.append(d["cmd"])
    return out


def test_corpus_precision_recall():
    r = normalize.score_corpus(CORPUS)
    assert r["precision"] >= 0.95
    assert r["recall"] >= 0.95
    assert r["cases"] >= 150
    assert r["negatives"] >= 60


def test_each_false_positive_family_has_8_negatives():
    cases = []
    with open(CORPUS, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if "cmd" in d:
                cases.append(d)
    families = {"help", "dry_run", "echo", "grep", "comment", "heredoc",
                "quoted_arg", "cat_heredoc_script"}
    for fam in families:
        n = sum(1 for c in cases if c["family"] == fam and not c["expect"])
        assert n >= 8, f"family {fam} has only {n} negatives"


def test_heredoc_and_help():
    cmd = ("cat > /tmp/x.sh <<'EOF'\nopenclaw gateway restart\nEOF\n"
           "openclaw cron disable abc --help")
    out = normalize.normalize_cmd(cmd)
    assert out["actions"] == []
    assert out["heredoc_lines_skipped"] == 1


def test_prefix_strip_service():
    out = normalize.normalize_cmd("sudo timeout 5 systemctl restart nginx")
    assert out["actions"] == [{"vtool": "service.restart", "args": {"unit": "nginx"}}]


def test_nested_unanalyzed_counted():
    out = normalize.normalize_cmd("bash -c 'openclaw gateway restart'")
    assert out["nested_unanalyzed"] == 1
    assert out["actions"] == []


def test_unparsed_reported():
    out = normalize.normalize_cmd('openclaw cron disable "unterminated')
    assert out["unparsed"] >= 1


def test_ablation_flags_change_counts():
    cmd = ("cat > /tmp/x.sh <<'EOF'\nopenclaw gateway restart\nEOF\n"
           "openclaw cron disable abc --help")
    with_handling = normalize.normalize_cmd(cmd)
    without = normalize.normalize_cmd(cmd, help_filter=False, heredoc_skip=False)
    assert len(without["actions"]) > len(with_handling["actions"])


def test_structured_cron_mapping():
    assert normalize.map_structured("cron", {"action": "disable", "jobId": "j1"}) == \
        {"vtool": "cron.disable", "args": {"jobId": "j1"}}


def test_structured_edit_removed_text():
    out = normalize.map_structured("edit", {"path": "MEMORY.md",
                                            "old_string": "DO NOT TOUCH\nkeep",
                                            "new_string": "keep"})
    assert out["vtool"] == "file.edit"
    assert out["args"]["path"] == "MEMORY.md"
    assert "DO NOT TOUCH" in out["args"]["removed_text"]


def test_structured_write_removed_text_null():
    out = normalize.map_structured("write", {"path": "x.md"})
    assert out == {"vtool": "file.edit", "args": {"path": "x.md", "removed_text": None}}


@pytest.mark.parametrize("cmd", _corpus_cmds())
def test_parity_with_spike(cmd):
    """The ported segments()/classify() must agree with the vendored spike's
    on every corpus command (AC #9 parity)."""
    ours = normalize.segments(cmd)[0]
    theirs = spike_replay.segments(cmd)
    assert ours == theirs
    for seg in ours:
        a_ours = normalize.classify(seg)
        a_theirs = spike_replay.classify(seg)
        assert a_ours == a_theirs
