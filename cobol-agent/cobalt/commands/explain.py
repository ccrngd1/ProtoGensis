"""cobalt explain — plain-English documentation for a COBOL program."""

from __future__ import annotations

from .. import assembler, prompts, provider
from ..parser import parse


def run(source: str, copy_dirs: list[str], parser: str = "auto") -> str:
    doc = parse(source, copy_dirs, prefer=parser)
    context = assembler.assemble_context(doc, source_path=source)
    return provider.complete(prompts.EXPLAIN_SYSTEM, context)
