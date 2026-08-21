"""Deterministic parser tests — exact values, no LLM."""

from docprobe.parser import Directive, looks_like_markdown, parse

DOC = """\
# Title

Intro sentence with no keywords here.

## Rules

- Always run the linter.
- Never commit to main.
- Prefer pathlib in new code.

```bash
never mind this fenced never keyword
```

## Notes

Plain narrative sentence.
"""


def test_headings_exact():
    doc = parse("AGENTS.md", DOC)
    assert [(h.level, h.text, h.line) for h in doc.headings] == [
        (1, "Title", 1),
        (2, "Rules", 5),
        (2, "Notes", 15),
    ]


def test_directives_exact():
    doc = parse("AGENTS.md", DOC)
    assert [d.line for d in doc.directives] == [7, 8, 9]
    assert doc.directives[0].text == "- Always run the linter."
    assert doc.directives[0].strong is True
    assert doc.directives[2].strong is False  # "prefer" is weak


def test_code_fences_excluded_from_directives():
    doc = parse("AGENTS.md", DOC)
    # The "never" inside the fence must not create a directive.
    assert all("fenced" not in d.text for d in doc.directives)
    assert doc.code_fence_lines == 3  # two fence markers + one body line


def test_prose_line_count_exact():
    doc = parse("AGENTS.md", DOC)
    # intro, 3 bullets, narrative = 5 prose lines (headings/fences/blank excluded)
    assert doc.prose_lines == 5


def test_sections_built_with_bodies():
    doc = parse("AGENTS.md", DOC)
    names = [s.heading for s in doc.sections]
    assert names == ["Title", "Rules", "Notes"]
    assert "Always run the linter" in doc.sections[1].body


def test_preamble_before_first_heading_is_a_section():
    doc = parse("AGENTS.md", "some preamble text\n\n# Head\n\nbody\n")
    assert doc.sections[0].heading == "(preamble)"
    assert doc.sections[0].body == "some preamble text"


def test_looks_like_markdown():
    assert looks_like_markdown("AGENTS.md")
    assert looks_like_markdown("notes.MDX".lower())
    assert looks_like_markdown(".cursorrules")
    assert not looks_like_markdown("script.py")


def test_vague_qualifier_detection():
    doc = parse("AGENTS.md", "- Always handle errors appropriately.\n")
    assert len(doc.directives) == 1
    assert doc.directives[0].vague is True


def test_empty_file_parses():
    doc = parse("AGENTS.md", "")
    assert doc.total_lines == 0
    assert doc.headings == []
    assert doc.directives == []
    assert doc.sections == []
