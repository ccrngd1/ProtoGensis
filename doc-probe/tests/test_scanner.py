"""Scanner + aggregation + edge cases (empty, no headers, huge, non-markdown,
glob no-match). No LLM calls."""

from docprobe.scanner import expand_targets, run_scan, scan_file


def test_no_llm_scan_offline(good_file):
    result = run_scan([str(good_file)], judge=None)
    f = result.files[0]
    assert f.error is None
    assert [d.name for d in f.dimensions] == [
        "discovery_accessibility",
        "hierarchy",
        "directive_density",
    ]
    assert f.skipped_dimensions == ["specificity", "contradiction"]
    assert f.overall_grade in "ABCDF"


def test_weighted_aggregation_exact(good_file):
    result = run_scan([str(good_file)], judge=None)
    f = result.files[0]
    total_w = sum(d.weight for d in f.dimensions)
    expected = round(sum(d.score * d.weight for d in f.dimensions) / total_w, 1)
    assert f.overall_score == expected


def test_llm_dimensions_included_with_judge(good_file, mock_judge):
    result = run_scan([str(good_file)], judge=mock_judge)
    f = result.files[0]
    names = [d.name for d in f.dimensions]
    assert "specificity" in names and "contradiction" in names
    assert f.skipped_dimensions == []
    assert result.llm.enabled is True
    assert result.llm.model == mock_judge.model


def test_empty_file(tmp_path):
    p = tmp_path / "AGENTS.md"
    p.write_text("", encoding="utf-8")
    f = scan_file(str(p), judge=None)
    assert f.error is None
    assert f.overall_grade == "F"
    assert all(d.score == 0.0 for d in f.dimensions)


def test_file_with_no_headers(tmp_path):
    p = tmp_path / "AGENTS.md"
    p.write_text("\n".join(["- Always run tests."] * 3 + ["filler"] * 60), encoding="utf-8")
    f = scan_file(str(p), judge=None)
    hierarchy = next(d for d in f.dimensions if d.name == "hierarchy")
    assert hierarchy.score == 40.0


def test_huge_file_completes_and_is_capped(tmp_path):
    # 5000 directives — the O(n^2) contradiction pre-filter must stay capped.
    p = tmp_path / "AGENTS.md"
    p.write_text(
        "\n".join(f"- Always update module {i} carefully." for i in range(5000)),
        encoding="utf-8",
    )
    f = scan_file(str(p), judge=None)
    assert f.error is None
    assert f.stats["lines"] == 5000.0


def test_non_markdown_binary_file(tmp_path):
    p = tmp_path / "image.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n\x00\xff\xfe binary")
    f = scan_file(str(p), judge=None)
    assert f.error is not None
    assert "not a text" in f.error
    assert f.overall_grade is None


def test_non_markdown_text_file_still_scored(tmp_path):
    p = tmp_path / "rules.txt"
    p.write_text("- Always run tests.\n", encoding="utf-8")
    f = scan_file(str(p), judge=None)
    assert f.error is None
    assert f.stats.get("non_markdown") == 1.0
    assert f.overall_grade in "ABCDF"


def test_glob_no_match(tmp_path):
    result = run_scan([str(tmp_path / "nomatch-*.md")], judge=None)
    assert result.files == []


def test_expand_targets_dedupes(tmp_path):
    p = tmp_path / "AGENTS.md"
    p.write_text("x", encoding="utf-8")
    got = expand_targets([str(p), str(tmp_path / "*.md")])
    assert got == [str(p)]


def test_missing_file_reports_error():
    f = scan_file("/nonexistent/AGENTS.md", judge=None)
    assert f.error is not None
    assert "unreadable" in f.error
