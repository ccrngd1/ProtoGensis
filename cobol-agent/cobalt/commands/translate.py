"""cobalt translate — COBOL to Java translation.

The `target` parameter exists so a Python target can slot in at v0.2, but
only "java" is implemented in v0.1.
"""

from __future__ import annotations

from .. import assembler, prompts, provider
from ..parser import parse

SUPPORTED_TARGETS = ("java",)


def run(source: str, copy_dirs: list[str], target: str = "java",
        paragraph: str | None = None, parser: str = "auto") -> str:
    if target not in SUPPORTED_TARGETS:
        raise ValueError(
            f"unsupported target {target!r}; v0.1 supports: "
            f"{', '.join(SUPPORTED_TARGETS)} (python planned for v0.2)"
        )
    doc = parse(source, copy_dirs, prefer=parser)
    if paragraph:
        names = {p["name"] for p in doc["paragraphs"]}
        if paragraph.upper() not in names:
            raise ValueError(
                f"paragraph {paragraph!r} not found; program has: "
                + ", ".join(sorted(names))
            )
    context = assembler.assemble_context(
        doc, source_path=source, paragraph=paragraph
    )
    if paragraph:
        context += (
            f"\n\nTranslate ONLY paragraph {paragraph.upper()} as a single "
            "Java method (plus any record classes its fields require)."
        )
    return provider.complete(prompts.TRANSLATE_SYSTEM, context, max_tokens=16000)
