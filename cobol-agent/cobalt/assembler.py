"""Context-assembly engine.

Turns a cobalt-parser-v0 document + the raw source into the structured
context block the LLM prompts consume: copybook-resolved data dictionary
with decoded PIC/COMP-3 semantics and Java type mappings, the PERFORM
paragraph graph, and REDEFINES/88-level annotations.

This is deterministic code, not LLM output — the point of Cobalt is that
the model never has to guess what S9(7)V99 COMP-3 means.
"""

from __future__ import annotations

from pathlib import Path

from .types import JAVA_ROUNDED, JAVA_TRUNCATION, type_table


def render_data_dictionary(doc: dict) -> str:
    """Fixed-width table of every data item with its decoded meaning."""
    rows = type_table(doc)
    lines = [
        "NAME                            LVL PICTURE        USAGE    JAVA TYPE              NOTES",
        "-" * 110,
    ]
    for r in rows:
        notes = []
        if r["occurs"]:
            notes.append(f"OCCURS {r['occurs']}")
        if r["redefines"]:
            notes.append(f"REDEFINES {r['redefines']} (review both layouts)")
        if r["condition_names"]:
            notes.append("88s: " + ", ".join(r["condition_names"]))
        indent = "  " * max(0, (r["level"] - 1) // 4)
        lines.append(
            f"{(indent + r['name']):<32}{r['level']:<4}"
            f"{(r['picture'] or '(group)'):<15}{r['usage']:<9}"
            f"{r['java']:<23}{'; '.join(notes)}"
        )
    return "\n".join(lines)


def render_perform_graph(doc: dict) -> str:
    """Indented call tree from the first paragraph, plus flat edges."""
    graph = doc["perform_graph"]
    paragraphs = [p["name"] for p in doc["paragraphs"]]
    if not paragraphs:
        return "(no paragraphs found)"

    lines = ["PERFORM graph (call tree from entry paragraph):"]
    seen: set[str] = set()

    def _tree(name: str, depth: int) -> None:
        marker = " (already shown)" if name in seen and graph.get(name) else ""
        lines.append("  " * depth + name + marker)
        if name in seen:
            return
        seen.add(name)
        for callee in graph.get(name, []):
            _tree(callee, depth + 1)

    _tree(paragraphs[0], 0)
    unreached = [p for p in paragraphs if p not in seen]
    if unreached:
        lines.append("Paragraphs not reached from entry: " + ", ".join(unreached))
    return "\n".join(lines)


def render_semantics_notes(doc: dict) -> str:
    """The COBOL-semantics rules the model must not violate."""
    notes = [
        "COBOL semantics rules (non-negotiable for translation):",
        f"- COMP-3 (packed decimal) fields map to java.math.BigDecimal with the "
        f"scale shown in the data dictionary. NEVER use double or float for any "
        f"COMP-3-derived value.",
        f"- PIC S9(N)V9(M) means an assumed decimal point: N integer digits, "
        f"M fraction digits -> BigDecimal with scale=M.",
        f"- COBOL COMPUTE/arithmetic WITHOUT the ROUNDED phrase truncates the "
        f"result toward zero at the receiving field's scale. In Java use "
        f".setScale(scale, {JAVA_TRUNCATION}) after multiply/divide.",
        f"- COBOL ROUNDED is half-away-from-zero: use {JAVA_ROUNDED}.",
        "- 88-level condition names become boolean predicates (or an enum) on "
        "the owning field; SET <88-name> TO TRUE assigns the first VALUE.",
        "- OCCURS n becomes a fixed-length array/List of n elements; COBOL "
        "subscripts are 1-based — subtract 1 when indexing in Java.",
        "- REDEFINES items share storage. Pick the interpretation the "
        "procedure code actually uses, and document the discarded layout in "
        "a comment flagged for human review.",
    ]
    reds = [r for r in type_table(doc) if r["redefines"]]
    for r in reds:
        notes.append(
            f"- NOTE: {r['name']} REDEFINES {r['redefines']} in this program."
        )
    return "\n".join(notes)


def assemble_context(doc: dict, source_path: str | None = None,
                     paragraph: str | None = None) -> str:
    """Full context block for prompts.

    If `paragraph` is given, the source section is trimmed to that paragraph
    (the data dictionary and graph are always complete — cheap and load-
    bearing).
    """
    parts = [
        f"PROGRAM: {doc['program_id']}  (source: {doc['source_file']}, "
        f"parsed by: {doc['parser']})",
        "COPYBOOKS RESOLVED: "
        + (", ".join(c["name"] for c in doc["copybooks"]) or "(none)"),
        "",
        "=== DATA DICTIONARY (copybooks inlined, PIC decoded) ===",
        render_data_dictionary(doc),
        "",
        "=== " + render_perform_graph(doc).split("\n")[0] + " ===",
        "\n".join(render_perform_graph(doc).split("\n")[1:]),
        "",
        "=== SEMANTICS RULES ===",
        render_semantics_notes(doc),
    ]
    if doc["diagnostics"]:
        parts += ["", "=== PARSER DIAGNOSTICS ==="] + [
            f"- {d}" for d in doc["diagnostics"]
        ]

    if source_path:
        source = Path(source_path).read_text(errors="replace")
        if paragraph:
            source = extract_paragraph(source, paragraph) or source
            parts += ["", f"=== SOURCE (paragraph {paragraph.upper()}) ===", source]
        else:
            parts += ["", "=== FULL SOURCE ===", source]
    return "\n".join(parts)


def extract_paragraph(source: str, name: str) -> str | None:
    """Cut one paragraph's text out of fixed-format source."""
    lines = source.splitlines()
    name_u = name.upper()
    start = end = None
    for i, line in enumerate(lines):
        code = line[7:72] if len(line) >= 8 else line
        stripped = code.strip().rstrip(".")
        if start is None:
            if stripped.upper() == name_u and code[:1].strip() != "":
                start = i
        else:
            # Next paragraph header (name starting in area A, ends with .)
            if (stripped and code[:4].strip() != "" and
                    code.strip().endswith(".") and
                    " " not in code.strip().rstrip(".")):
                end = i
                break
    if start is None:
        return None
    return "\n".join(lines[start: end or len(lines)])
