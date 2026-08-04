"""Parser front-door selection logic — all without touching a JVM."""

from pathlib import Path

import pytest

import cobalt.parser as frontdoor

SAMPLES = Path(__file__).resolve().parent.parent / "assets" / "samples"
SAMPLE_CBL = str(SAMPLES / "claimcalc.cbl")
SAMPLE_COPY = str(SAMPLES / "copy")


@pytest.fixture(autouse=True)
def no_jar(monkeypatch, tmp_path):
    """Point PARSER_JAR at a nonexistent path so java is never chosen."""
    monkeypatch.setattr(frontdoor, "PARSER_JAR", tmp_path / "no.jar")


def test_java_unavailable_without_jar():
    assert frontdoor.java_parser_available() is False


def test_auto_falls_back_to_python():
    doc = frontdoor.parse(SAMPLE_CBL, [SAMPLE_COPY], prefer="auto")
    assert doc["parser"] == "fallback"
    assert doc["program_id"] == "CLAIMCALC"


def test_prefer_java_raises_when_unavailable():
    with pytest.raises(frontdoor.ParserUnavailable, match="build.sh"):
        frontdoor.parse_with_java(SAMPLE_CBL, [])


def test_prefer_fallback_is_explicit():
    doc = frontdoor.parse(SAMPLE_CBL, [SAMPLE_COPY], prefer="fallback")
    assert doc["parser"] == "fallback"


def test_fallback_output_passes_schema_validation():
    # parse() runs validate() internally; reaching here means it passed.
    doc = frontdoor.parse(SAMPLE_CBL, [SAMPLE_COPY])
    assert doc["schema_version"] == "cobalt-parser-v0"
