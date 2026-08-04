"""CLI tests via click's CliRunner. LLM mocked; parser is the pure-Python
fallback (forced with --parser fallback) or the canned fixture — no JVM."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from cobalt.cli import main

SAMPLES = Path(__file__).resolve().parent.parent / "assets" / "samples"
SAMPLE_CBL = str(SAMPLES / "claimcalc.cbl")
SAMPLE_COPY = str(SAMPLES / "copy")


def _run(*args):
    return CliRunner().invoke(main, list(args))


class TestHelp:
    def test_root_help(self):
        res = _run("--help")
        assert res.exit_code == 0
        for cmd in ("explain", "translate", "test", "demo", "inspect"):
            assert cmd in res.output

    def test_version(self):
        res = _run("--version")
        assert res.exit_code == 0
        assert "cobalt" in res.output

    def test_subcommand_help(self):
        res = _run("translate", "--help")
        assert res.exit_code == 0
        assert "--to" in res.output
        assert "java" in res.output


class TestExplainCommand:
    def test_explain_runs_with_mock(self, mock_llm):
        res = _run("explain", SAMPLE_CBL, "-I", SAMPLE_COPY,
                   "--parser", "fallback")
        assert res.exit_code == 0, res.output
        assert "[MOCK LLM OUTPUT" in res.output
        assert len(mock_llm) == 1

    def test_explain_missing_file(self):
        res = _run("explain", "no/such/file.cbl")
        assert res.exit_code != 0


class TestTranslateCommand:
    def test_translate_requires_target(self, mock_llm):
        res = _run("translate", SAMPLE_CBL)
        assert res.exit_code != 0
        assert "--to" in res.output

    def test_translate_java(self, mock_llm):
        res = _run("translate", SAMPLE_CBL, "--to", "java",
                   "-I", SAMPLE_COPY, "--parser", "fallback")
        assert res.exit_code == 0, res.output
        assert "[MOCK LLM OUTPUT" in res.output

    def test_translate_rejects_non_java_target(self, mock_llm):
        res = _run("translate", SAMPLE_CBL, "--to", "python")
        assert res.exit_code != 0          # click Choice rejects it
        assert mock_llm == []

    def test_translate_output_file(self, tmp_path, mock_llm):
        out = tmp_path / "ClaimCalc.java"
        res = _run("translate", SAMPLE_CBL, "--to", "java",
                   "-I", SAMPLE_COPY, "--parser", "fallback",
                   "-o", str(out))
        assert res.exit_code == 0, res.output
        assert out.read_text().startswith("[MOCK LLM OUTPUT")


class TestTestCommand:
    def test_testgen_with_golden(self, mock_llm):
        golden = str(SAMPLES / "golden" / "expected_output.txt")
        res = _run("test", SAMPLE_CBL, "-I", SAMPLE_COPY,
                   "--parser", "fallback", "--golden", golden)
        assert res.exit_code == 0, res.output
        assert len(mock_llm) == 1
        _, user = mock_llm[0]
        assert "GnuCOBOL-verified" in user


class TestDemoCommand:
    @pytest.fixture(autouse=True)
    def _no_jvm(self, monkeypatch):
        # `demo` uses the auto parser; force the fallback so the suite
        # never shells out to java even when the JAR is installed.
        monkeypatch.setattr("cobalt.parser.java_parser_available", lambda: False)
        monkeypatch.setattr("cobalt.cli.java_parser_available", lambda: False)

    def test_demo_skip_llm_makes_no_api_calls(self, mock_llm):
        res = _run("demo", "--skip-llm")
        assert res.exit_code == 0, res.output
        assert "PROGRAM: CLAIMCALC" in res.output
        assert "GOLDEN MASTER" in res.output
        assert "stopping before API calls" in res.output
        assert mock_llm == []              # no LLM call was even attempted

    def test_demo_reports_parser_backend(self):
        res = _run("demo", "--skip-llm")
        assert "parser backend:" in res.output


class TestInspectCommand:
    def test_inspect_no_llm(self, mock_llm):
        res = _run("inspect", SAMPLE_CBL, "-I", SAMPLE_COPY,
                   "--parser", "fallback")
        assert res.exit_code == 0, res.output
        assert "=== DATA DICTIONARY" in res.output
        assert "BigDecimal(scale=2)" in res.output
        assert mock_llm == []
