"""CLI tests via typer's CliRunner. No LLM calls (--no-llm everywhere except
the mocked-judge case)."""

import json

from typer.testing import CliRunner

from docprobe.cli import app

runner = CliRunner()


def test_scan_exit_zero_even_on_low_scores(vague_file):
    """Low scores are findings, not failures — exit 0."""
    result = runner.invoke(app, ["scan", str(vague_file), "--no-llm"])
    assert result.exit_code == 0


def test_scan_json_format_schema(good_file):
    result = runner.invoke(app, ["scan", str(good_file), "--no-llm", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    # Stable schema shape (see README "JSON output schema").
    assert set(payload) == {"docprobe_version", "rubric_version", "llm", "files"}
    f = payload["files"][0]
    assert {"path", "overall_grade", "overall_score", "dimensions", "skipped_dimensions"} <= set(f)
    d = f["dimensions"][0]
    assert {"name", "grade", "score", "evidence_tier", "evidence_source", "weight", "method", "flags"} <= set(d)


def test_evidence_tiers_visible_in_output(good_file):
    result = runner.invoke(app, ["scan", str(good_file), "--no-llm", "--format", "json"])
    payload = json.loads(result.stdout)
    tiers = {d["name"]: d["evidence_tier"] for d in payload["files"][0]["dimensions"]}
    assert tiers["discovery_accessibility"] == "grounded"
    assert tiers["directive_density"] == "opinionated"
    assert tiers["hierarchy"] == "partial"


def test_scan_markdown_format(good_file):
    result = runner.invoke(app, ["scan", str(good_file), "--no-llm", "--format", "markdown"])
    assert result.exit_code == 0
    assert "| dimension | grade" in result.stdout
    assert "opinionated" in result.stdout  # tier is visible in markdown too


def test_scan_glob_no_match_exits_zero(tmp_path):
    result = runner.invoke(
        app, ["scan", "--glob", str(tmp_path / "none-*.md"), "--no-llm", "--format", "json"]
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["files"] == []


def test_bad_format_is_scan_error(good_file):
    result = runner.invoke(app, ["scan", str(good_file), "--no-llm", "--format", "bogus"])
    assert result.exit_code == 2


def test_output_file_written(good_file, tmp_path):
    out = tmp_path / "report.json"
    result = runner.invoke(
        app,
        ["scan", str(good_file), "--no-llm", "--format", "json", "--output", str(out)],
    )
    assert result.exit_code == 0
    assert json.loads(out.read_text())["files"]


def test_report_command_defaults_markdown(good_file):
    result = runner.invoke(app, ["report", str(good_file), "--no-llm"])
    assert result.exit_code == 0
    assert "DocProbe report" in result.stdout


def test_fix_command_no_llm(vague_file):
    result = runner.invoke(app, ["fix", str(vague_file), "--no-llm"])
    assert result.exit_code == 0


def test_fix_prefers_attaching_rationale_for_contradictions(tmp_path, monkeypatch):
    """fix mode: contradiction flags become attach_rationale, never deletion."""
    import litellm

    from tests.conftest import make_llm_response

    p = tmp_path / "AGENTS.md"
    p.write_text(
        "# R\n\n- Always use tabs for indentation.\n- Indent with 4 spaces always.\n",
        encoding="utf-8",
    )

    def fake(**kwargs):
        system = kwargs["messages"][0]["content"]
        if "contradiction" in system:
            return make_llm_response(
                {
                    "grade": "D",
                    "flags": [
                        {
                            "passage": "- Always use tabs for indentation.",
                            "related_passage": "- Indent with 4 spaces always.",
                            "rationale": "Cannot satisfy both",
                            "suggestion": "Attach a rationale stating which wins where",
                        }
                    ],
                }
            )
        return make_llm_response({"grade": "B", "flags": []})

    monkeypatch.setattr(litellm, "completion", fake)
    monkeypatch.setenv("DOCPROBE_CACHE_DIR", str(tmp_path / "cache"))

    out = tmp_path / "fixes.json"
    result = runner.invoke(app, ["fix", str(p), "--output", str(out)])
    assert result.exit_code == 0
    fixes = json.loads(out.read_text())
    contradiction_fixes = [f for f in fixes if f["dimension"] == "contradiction"]
    assert contradiction_fixes
    assert all(f["kind"] == "attach_rationale" for f in contradiction_fixes)
    assert all("delete" not in f["suggestion"].lower() for f in contradiction_fixes)
