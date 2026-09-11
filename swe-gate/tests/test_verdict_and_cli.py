"""Determinism (AC #1), delta gating, output formats, exit codes, and
graceful degradation for non-Python changesets."""

import json
import subprocess
import sys

import pytest

from swe_gate.cli import main
from swe_gate.findings import Finding, LayerResult
from swe_gate.verdict import EXIT_ERROR, EXIT_FAIL, EXIT_PASS, Verdict

from .conftest import layer_result


def _mk_verdict(layers):
    return Verdict(layers=layers, baseline="deadbeef", repo="/tmp/x")


def _advisory(layer):
    return Finding(layer=layer, rule_id="adv", message="advisory", blocking=False)


def _blocking(layer):
    return Finding(layer=layer, rule_id="blk", message="blocking", blocking=True)


class TestDeterminism:
    """AC #1: stripping every advisory finding changes no verdict."""

    def test_advisory_findings_never_change_exit_code(self):
        with_advisory = _mk_verdict(
            [
                LayerResult(layer=0, status="", findings=[_advisory(0)] * 5).finalize(),
                LayerResult(layer=1, status="", findings=[_blocking(1)]).finalize(),
                LayerResult(layer=2, status="skipped"),
                LayerResult(layer=3, status="", findings=[_advisory(3)] * 9).finalize(),
            ]
        )
        without_advisory = _mk_verdict(
            [
                LayerResult(layer=0, status="", findings=[]).finalize(),
                LayerResult(layer=1, status="", findings=[_blocking(1)]).finalize(),
                LayerResult(layer=2, status="skipped"),
                LayerResult(layer=3, status="", findings=[]).finalize(),
            ]
        )
        assert with_advisory.exit_code == without_advisory.exit_code == EXIT_FAIL
        for lhs, rhs in zip(with_advisory.layers, without_advisory.layers):
            assert lhs.status == rhs.status

    def test_advisory_only_verdict_passes(self):
        verdict = _mk_verdict(
            [LayerResult(layer=3, status="", findings=[_advisory(3)] * 20).finalize()]
        )
        assert verdict.exit_code == EXIT_PASS

    def test_gate_output_is_reproducible(self, seeded_repo):
        seeded_repo.write("app/db.py", "import ghost_pkg_qqq\n")
        first = seeded_repo.gate().render("json")
        second = seeded_repo.gate().render("json")
        assert first == second


class TestExitCodes:
    def test_error_status_wins(self):
        verdict = _mk_verdict(
            [
                LayerResult(layer=1, status="", findings=[_blocking(1)]).finalize(),
                LayerResult(layer=2, status="error", detail="pyright exploded"),
            ]
        )
        assert verdict.exit_code == EXIT_ERROR

    def test_all_nonfail_statuses_pass(self):
        verdict = _mk_verdict(
            [
                LayerResult(layer=0, status="pass"),
                LayerResult(layer=1, status="n/a"),
                LayerResult(layer=2, status="skipped"),
                LayerResult(layer=3, status="unverifiable"),
            ]
        )
        assert verdict.exit_code == EXIT_PASS


class TestNonPythonChangeset:
    def test_docs_only_change_exits_zero(self, repo):
        repo.write("README.md", "hello\n")
        repo.commit()
        repo.write("README.md", "hello world\n")
        verdict = repo.gate()
        assert verdict.exit_code == EXIT_PASS
        for lr in verdict.layers:
            assert lr.status == "n/a"
            assert "no Python in scope" in lr.detail


class TestFormats:
    @pytest.fixture
    def failed_verdict(self, seeded_repo):
        seeded_repo.write("app/db.py", "import ghost_pkg_qqq\n")
        return seeded_repo.gate(layers=(1,))

    def test_json_format(self, failed_verdict):
        payload = json.loads(failed_verdict.render("json"))
        assert payload["verdict"] == "fail"
        assert payload["exit_code"] == 1
        l1 = next(l for l in payload["layers"] if l["layer"] == 1)
        assert l1["status"] == "fail"
        assert l1["blocking_findings"]
        assert "not a probability" in payload["advisory_note"]

    def test_terminal_leads_with_table(self, failed_verdict):
        text = failed_verdict.render("terminal")
        head = text.splitlines()[0]
        assert head.startswith("SWE-GATE: FAILED")
        assert "import hallucination" in text

    def test_md_format(self, failed_verdict):
        text = failed_verdict.render("md")
        assert text.startswith("### SWE-GATE: FAILED")
        assert "| L1 import hallucination |" in text

    def test_no_calibrated_confidence_language(self, failed_verdict):
        # the tmp repo path may contain arbitrary words; check output, not paths
        failed_verdict.repo = "/repo"
        for fmt in ("terminal", "json", "md"):
            text = failed_verdict.render(fmt).lower()
            assert "calibrated" not in text
            assert "confidence" not in text
            assert "probability" not in text.replace("not a probability", "")


class TestCLI:
    def test_cli_exit_codes_end_to_end(self, seeded_repo):
        assert main(["run", "--baseline", "HEAD", str(seeded_repo.root)]) == EXIT_PASS
        seeded_repo.write("app/db.py", "import ghost_pkg_qqq\n")
        assert (
            main(["run", "--baseline", "HEAD", "--layers", "1", str(seeded_repo.root)])
            == EXIT_FAIL
        )

    def test_cli_git_error_is_exit_2(self, tmp_path, capsys):
        (tmp_path / "not-a-repo.txt").write_text("x")
        code = main(["run", str(tmp_path)])
        assert code == EXIT_ERROR

    def test_layers_subset_skips_deselected(self, seeded_repo):
        seeded_repo.write("app/db.py", "import ghost_pkg_qqq\n")
        verdict = seeded_repo.gate(layers=(0,))
        assert layer_result(verdict, 1).status == "skipped"
        assert verdict.exit_code == EXIT_PASS  # L1 deselected, so nothing blocks

    def test_entry_point_installed(self):
        proc = subprocess.run(
            [sys.executable, "-m", "swe_gate", "run", "--help"],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        assert "--check-pypi" in proc.stdout
