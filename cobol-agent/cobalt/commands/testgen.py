"""cobalt test — generate JUnit 5 characterization tests."""

from __future__ import annotations

from pathlib import Path

from .. import assembler, prompts, provider
from ..parser import parse


def run(source: str, copy_dirs: list[str], java_file: str | None = None,
        golden: str | None = None, parser: str = "auto") -> str:
    doc = parse(source, copy_dirs, prefer=parser)
    context = assembler.assemble_context(doc, source_path=source)

    if golden and Path(golden).is_file():
        golden_text = Path(golden).read_text(errors="replace")
        provenance = _golden_provenance(golden)
        context += (
            f"\n\n=== GOLDEN MASTER OUTPUT ({provenance}) ===\n{golden_text}"
        )
    else:
        context += (
            "\n\n=== GOLDEN MASTER OUTPUT ===\n(none available — generate "
            "SCENARIO tests only and label them LLM-derived, not "
            "machine-verified)"
        )

    if java_file and Path(java_file).is_file():
        context += (
            "\n\n=== JAVA TRANSLATION UNDER TEST ===\n"
            + Path(java_file).read_text(errors="replace")
        )
    else:
        context += (
            "\n\n=== JAVA TRANSLATION UNDER TEST ===\n(not provided — write "
            "tests against the class/method shape a faithful translation "
            "would have, following the data dictionary)"
        )
    return provider.complete(prompts.TESTGEN_SYSTEM, context, max_tokens=16000)


def _golden_provenance(golden_path: str) -> str:
    """Honest label: only claim GnuCOBOL-verified if PROVENANCE.md says so."""
    prov = Path(golden_path).parent / "PROVENANCE.md"
    if prov.is_file() and "real golden master" in prov.read_text(errors="replace"):
        return "GnuCOBOL-verified: real compile-and-run output"
    return "provenance unknown — do NOT label tests GnuCOBOL-verified"
