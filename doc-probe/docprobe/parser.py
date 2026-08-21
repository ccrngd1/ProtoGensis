"""Deterministic parsing and feature extraction for instruction files.

Everything in this module is computed WITHOUT any LLM call and is
unit-tested for exact values. It powers the three mechanical dimensions:
directive density, discovery accessibility, and hierarchy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from markdown_it import MarkdownIt

# Words that mark a sentence/line as a directive (an instruction the agent is
# expected to follow). Opinionated list; see rubric.md §directive-density.
DIRECTIVE_KEYWORDS = re.compile(
    r"\b(must(?: not)?|never|always|do not|don't|should(?: not)?|shall|"
    r"required|forbidden|prohibited|ensure|use|avoid|prefer|only|"
    r"run|call|write|read|check|verify|follow|keep|set|add|remove|update|"
    r"indent|name|format|test)\b",
    re.IGNORECASE,
)

STRONG_DIRECTIVE_KEYWORDS = re.compile(
    r"\b(must(?: not)?|never|always|do not|don't|shall|required|forbidden|prohibited)\b",
    re.IGNORECASE,
)

# Vague qualifiers that weaken a directive (used as a deterministic hint;
# the semantic judgment lives in the LLM specificity dimension).
VAGUE_QUALIFIERS = re.compile(
    r"\b(appropriate(?:ly)?|properly|as needed|if necessary|when possible|"
    r"generally|usually|reasonable|good|clean|best practices|etc\.?)\b",
    re.IGNORECASE,
)


@dataclass
class Heading:
    level: int
    text: str
    line: int  # 1-based


@dataclass
class Directive:
    text: str
    line: int  # 1-based
    strong: bool
    vague: bool


@dataclass
class Section:
    """A heading plus the body text under it (until the next heading)."""

    heading: str
    level: int
    start_line: int
    body: str


@dataclass
class ParsedDoc:
    path: str
    text: str
    lines: list[str] = field(default_factory=list)
    is_markdown: bool = True
    headings: list[Heading] = field(default_factory=list)
    directives: list[Directive] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    total_lines: int = 0
    prose_lines: int = 0  # non-blank, non-heading, non-code-fence lines
    code_fence_lines: int = 0
    word_count: int = 0


_MD = MarkdownIt("commonmark")

MARKDOWN_SUFFIXES = (".md", ".markdown", ".mdx")
# Common agent instruction files without a .md suffix are still treated as
# markdown-ish plain text (e.g. .cursorrules).
KNOWN_PLAINTEXT_RULES = (".cursorrules", ".windsurfrules", ".clinerules")


def looks_like_markdown(path: str) -> bool:
    lower = path.lower()
    if lower.endswith(MARKDOWN_SUFFIXES):
        return True
    return any(lower.endswith(name) for name in KNOWN_PLAINTEXT_RULES)


def parse(path: str, text: str) -> ParsedDoc:
    """Parse an instruction file into deterministic features."""
    lines = text.splitlines()
    doc = ParsedDoc(
        path=path,
        text=text,
        lines=lines,
        is_markdown=looks_like_markdown(path),
        total_lines=len(lines),
        word_count=len(text.split()),
    )

    tokens = _MD.parse(text)
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.map:
            level = int(tok.tag[1])
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            heading_text = inline.content if inline is not None else ""
            doc.headings.append(Heading(level=level, text=heading_text, line=tok.map[0] + 1))

    in_fence = False
    for idx, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            doc.code_fence_lines += 1
            continue
        if in_fence:
            doc.code_fence_lines += 1
            continue
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        doc.prose_lines += 1
        if DIRECTIVE_KEYWORDS.search(stripped):
            doc.directives.append(
                Directive(
                    text=stripped,
                    line=idx,
                    strong=bool(STRONG_DIRECTIVE_KEYWORDS.search(stripped)),
                    vague=bool(VAGUE_QUALIFIERS.search(stripped)),
                )
            )

    doc.sections = _build_sections(doc)
    return doc


def _build_sections(doc: ParsedDoc) -> list[Section]:
    if not doc.headings:
        if doc.text.strip():
            return [Section(heading="(no heading)", level=0, start_line=1, body=doc.text)]
        return []
    sections: list[Section] = []
    # Preamble before the first heading counts as its own section.
    first = doc.headings[0]
    if first.line > 1:
        preamble = "\n".join(doc.lines[: first.line - 1]).strip()
        if preamble:
            sections.append(Section(heading="(preamble)", level=0, start_line=1, body=preamble))
    for i, h in enumerate(doc.headings):
        end = doc.headings[i + 1].line - 1 if i + 1 < len(doc.headings) else len(doc.lines)
        body = "\n".join(doc.lines[h.line : end]).strip()
        sections.append(Section(heading=h.text, level=h.level, start_line=h.line, body=body))
    return sections
