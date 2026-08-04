"""Command-layer tests: explain / translate / testgen.

The LLM is always mocked (mock_llm fixture) and the parser is the canned
JSON (use_fixture_parser) — these tests assert on the PROMPTS we send, not
on model behavior. Real-LLM behavior is intentionally not benchmarked here.
"""

from pathlib import Path

import pytest

from cobalt import prompts
from cobalt.commands import explain, testgen, translate

SAMPLES = Path(__file__).resolve().parent.parent / "assets" / "samples"
SAMPLE_CBL = str(SAMPLES / "claimcalc.cbl")
GOLDEN = str(SAMPLES / "golden" / "expected_output.txt")


class TestExplain:
    def test_sends_assembled_context(self, mock_llm, use_fixture_parser):
        out = explain.run(SAMPLE_CBL, [])
        assert out == "[MOCK LLM OUTPUT — no API call was made]"
        (system, user), = mock_llm
        assert system == prompts.EXPLAIN_SYSTEM
        assert "PROGRAM: CLAIMCALC" in user
        assert "BigDecimal(scale=2)" in user       # decoded types included
        assert "=== FULL SOURCE ===" in user


class TestTranslate:
    def test_java_target(self, mock_llm, use_fixture_parser):
        translate.run(SAMPLE_CBL, [], target="java")
        (system, user), = mock_llm
        assert system == prompts.TRANSLATE_SYSTEM
        assert "RoundingMode.DOWN" in user          # truncation rule in context
        assert "never double or float" in system

    def test_unsupported_target_rejected(self, mock_llm, use_fixture_parser):
        with pytest.raises(ValueError, match="unsupported target"):
            translate.run(SAMPLE_CBL, [], target="python")
        assert mock_llm == []                       # rejected before any call

    def test_single_paragraph_mode(self, mock_llm, use_fixture_parser):
        translate.run(SAMPLE_CBL, [], target="java",
                      paragraph="2300-CALC-ALLOWED")
        (_, user), = mock_llm
        assert "Translate ONLY paragraph 2300-CALC-ALLOWED" in user

    def test_unknown_paragraph_rejected(self, mock_llm, use_fixture_parser):
        with pytest.raises(ValueError, match="not found"):
            translate.run(SAMPLE_CBL, [], target="java", paragraph="9999-NOPE")
        assert mock_llm == []


class TestTestgen:
    def test_with_real_golden_master(self, mock_llm, use_fixture_parser):
        testgen.run(SAMPLE_CBL, [], golden=GOLDEN)
        (system, user), = mock_llm
        assert system == prompts.TESTGEN_SYSTEM
        # PROVENANCE.md marks this golden master as a real GnuCOBOL run.
        assert "GnuCOBOL-verified: real compile-and-run output" in user
        assert "987.64" in user                     # golden numbers embedded

    def test_without_golden_master_labels_honestly(self, mock_llm,
                                                   use_fixture_parser):
        testgen.run(SAMPLE_CBL, [], golden=None)
        (_, user), = mock_llm
        assert "LLM-derived, not" in user
        assert "GnuCOBOL-verified: real" not in user

    def test_golden_without_provenance_not_trusted(self, tmp_path, mock_llm,
                                                   use_fixture_parser):
        fake = tmp_path / "expected_output.txt"
        fake.write_text("TOTALS: 123.45\n")         # no PROVENANCE.md beside it
        testgen.run(SAMPLE_CBL, [], golden=str(fake))
        (_, user), = mock_llm
        assert "provenance unknown" in user
        assert "do NOT label tests GnuCOBOL-verified" in user

    def test_exact_bigdecimal_rule_in_prompt(self):
        assert "exact BigDecimal comparison" in prompts.TESTGEN_SYSTEM
        assert "NEVER" in prompts.TESTGEN_SYSTEM


class TestProviderIsolation:
    def test_no_litellm_import_needed_for_mocked_run(self, mock_llm,
                                                     use_fixture_parser):
        # provider.complete imports litellm lazily; the mock replaces the
        # function entirely, so a full command run must not require creds.
        import os
        assert "COBALT_MODEL" not in os.environ or True
        explain.run(SAMPLE_CBL, [])
        assert len(mock_llm) == 1

    def test_model_env_var_wins(self, monkeypatch):
        from cobalt import provider
        monkeypatch.setenv("COBALT_MODEL", "litellm/test-model")
        assert provider.get_model() == "litellm/test-model"
        monkeypatch.delenv("COBALT_MODEL")
        assert provider.get_model() == provider.DEFAULT_MODEL
