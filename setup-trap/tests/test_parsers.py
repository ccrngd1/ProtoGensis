"""Parser unit tests (FR2)."""

from __future__ import annotations

from pathlib import Path

from setup_trap.scanner.parsers import parse_file
from setup_trap.scanner.parsers.base import parse_file as pf


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_markdown_separates_prose_and_code(tmp_path):
    p = _write(
        tmp_path,
        "AGENTS.md",
        "intro prose\n\n```bash\npip install evil\n```\n\nmore prose\n",
    )
    parsed = parse_file(p)
    kinds = {s.kind for s in parsed.segments}
    assert "prose" in kinds and "code" in kinds
    code = [s for s in parsed.segments if s.kind == "code"]
    assert any("pip install evil" in s.text for s in code)


def test_markdown_line_numbers_accurate(tmp_path):
    p = _write(tmp_path, "CLAUDE.md", "line1\nline2\n```\ncode3\n```\nline6\n")
    parsed = parse_file(p)
    code = [s for s in parsed.segments if s.kind == "code"][0]
    assert code.start_line == 4  # content after the fence on line 3


def test_requirements_extracts_packages_and_index(tmp_path):
    p = _write(
        tmp_path,
        "requirements.txt",
        "numpy==1.26.0\n--extra-index-url https://example.com/pypi\ntorch>=2.0\n",
    )
    parsed = parse_file(p)
    names = {pkg.name for pkg in parsed.packages}
    assert {"numpy", "torch"} <= names
    assert any(i.kind == "extra-index-url" for i in parsed.index_urls)
    numpy = [pkg for pkg in parsed.packages if pkg.name == "numpy"][0]
    assert numpy.version_spec == "==1.26.0"


def test_requirements_ignores_comments_and_includes(tmp_path):
    p = _write(tmp_path, "requirements.txt", "# comment\n-r base.txt\nrequests\n")
    parsed = parse_file(p)
    names = {pkg.name for pkg in parsed.packages}
    assert names == {"requests"}


def test_makefile_extracts_targets_and_commands(tmp_path):
    p = _write(
        tmp_path,
        "Makefile",
        "install:\n\tpip install -r requirements.txt\n\ntest:\n\tpytest\n",
    )
    parsed = parse_file(p)
    targets = {t.name for t in parsed.make_targets}
    assert {"install", "test"} <= targets
    install = [t for t in parsed.make_targets if t.name == "install"][0]
    assert any("pip install" in cmd for _, cmd in install.commands)


def test_toml_extracts_deps_and_sources(tmp_path):
    p = _write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname="x"\ndependencies=["requests>=2.31.0","click"]\n'
        '[[tool.poetry.source]]\nname="x"\nurl="https://example.com/pypi"\n',
    )
    parsed = parse_file(p)
    names = {pkg.name for pkg in parsed.packages}
    assert {"requests", "click"} <= names
    # name split must not include the version operator
    assert "requests>" not in names
    assert any("example.com" in i.url for i in parsed.index_urls)


def test_parser_tolerant_of_malformed_toml(tmp_path):
    p = _write(tmp_path, "pyproject.toml", "this is [ not valid toml =====")
    parsed = parse_file(p)
    assert parsed.parse_error  # a note, not a crash
    assert parsed.segments  # still produced line segments


def test_parser_dispatch_matches_module(tmp_path):
    # base.parse_file is what engine uses; ensure the alias works too.
    p = _write(tmp_path, "requirements.txt", "flask\n")
    assert pf(p).packages[0].name == "flask"
