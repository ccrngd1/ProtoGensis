"""Cobalt CLI (click)."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from . import __version__
from .parser import PARSER_JAR, java_parser_available, parse

_ASSETS = Path(__file__).resolve().parent.parent / "assets"
SAMPLE = _ASSETS / "samples" / "claimcalc.cbl"
SAMPLE_COPY = _ASSETS / "samples" / "copy"
SAMPLE_GOLDEN = _ASSETS / "samples" / "golden" / "expected_output.txt"

_copy_opt = click.option(
    "--copy-dir", "-I", "copy_dirs", multiple=True,
    type=click.Path(exists=True, file_okay=False),
    help="Directory to resolve COPY members from (repeatable).",
)
_parser_opt = click.option(
    "--parser", type=click.Choice(["auto", "java", "fallback"]),
    default="auto", show_default=True,
    help="Parser backend: ProLeap JAR, pure-Python fallback, or auto.",
)


@click.group()
@click.version_option(__version__, prog_name="cobalt")
def main() -> None:
    """Cobalt: AI-powered COBOL comprehension and translation.

    Model selection is via the COBALT_MODEL env var (LiteLLM format),
    e.g. COBALT_MODEL=litellm/sonnet45 with COBALT_API_BASE=http://localhost:4000
    for a local LiteLLM proxy.
    """


@main.command()
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
@_copy_opt
@_parser_opt
def explain(source: str, copy_dirs: tuple[str, ...], parser: str) -> None:
    """Explain a COBOL program in plain English."""
    from .commands import explain as cmd

    click.echo(cmd.run(source, list(copy_dirs), parser=parser))


@main.command()
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
@click.option("--to", "target", type=click.Choice(["java"]), required=True,
              help="Translation target language (v0.1: java only).")
@click.option("--paragraph", default=None,
              help="Translate a single paragraph by name.")
@click.option("--output", "-o", type=click.Path(dir_okay=False), default=None,
              help="Write output to a file instead of stdout.")
@_copy_opt
@_parser_opt
def translate(source: str, target: str, paragraph: str | None,
              output: str | None, copy_dirs: tuple[str, ...],
              parser: str) -> None:
    """Translate a COBOL program (or one paragraph) to Java."""
    from .commands import translate as cmd

    result = cmd.run(source, list(copy_dirs), target=target,
                     paragraph=paragraph, parser=parser)
    if output:
        Path(output).write_text(result)
        click.echo(f"wrote {output}")
    else:
        click.echo(result)


@main.command("test")
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
@click.option("--java-file", type=click.Path(exists=True, dir_okay=False),
              default=None, help="The Java translation to write tests against.")
@click.option("--golden", type=click.Path(exists=True, dir_okay=False),
              default=None, help="Golden-master output file from the COBOL run.")
@click.option("--output", "-o", type=click.Path(dir_okay=False), default=None)
@_copy_opt
@_parser_opt
def test_cmd(source: str, java_file: str | None, golden: str | None,
             output: str | None, copy_dirs: tuple[str, ...],
             parser: str) -> None:
    """Generate JUnit 5 characterization tests for a translation."""
    from .commands import testgen as cmd

    result = cmd.run(source, list(copy_dirs), java_file=java_file,
                     golden=golden, parser=parser)
    if output:
        Path(output).write_text(result)
        click.echo(f"wrote {output}")
    else:
        click.echo(result)


@main.command()
@click.option("--skip-llm", is_flag=True,
              help="Only show the parsed context (no API calls).")
def demo(skip_llm: bool) -> None:
    """Run the pipeline on the bundled healthcare-claims sample.

    Parses assets/samples/claimcalc.cbl (real parse), shows the assembled
    context, then — unless --skip-llm — calls the configured model to
    explain and translate it (real API calls).
    """
    from . import assembler

    if not SAMPLE.is_file():
        click.echo("bundled sample not found; is this a source checkout?", err=True)
        sys.exit(1)

    backend = "java (ProLeap JAR)" if java_parser_available() else \
        f"fallback (pure Python; JAR not present at {PARSER_JAR})"
    click.echo(f"# Cobalt demo — parser backend: {backend}\n")

    doc = parse(str(SAMPLE), [str(SAMPLE_COPY)])
    click.echo(assembler.assemble_context(doc))

    if SAMPLE_GOLDEN.is_file():
        click.echo("\n=== GOLDEN MASTER (GnuCOBOL compile-and-run output) ===")
        click.echo(SAMPLE_GOLDEN.read_text())

    if skip_llm:
        click.echo("\n(--skip-llm set: stopping before API calls)")
        return

    from .commands import explain as explain_cmd
    from .commands import translate as translate_cmd
    from .provider import get_model

    click.echo(f"\n=== LLM EXPLAIN (model: {get_model()}) ===\n")
    click.echo(explain_cmd.run(str(SAMPLE), [str(SAMPLE_COPY)]))
    click.echo(f"\n=== LLM TRANSLATE --to java (model: {get_model()}) ===\n")
    click.echo(translate_cmd.run(str(SAMPLE), [str(SAMPLE_COPY)], target="java"))


@main.command()
@click.argument("source", type=click.Path(exists=True, dir_okay=False))
@_copy_opt
@_parser_opt
def inspect(source: str, copy_dirs: tuple[str, ...], parser: str) -> None:
    """Show the assembled context for a program (no LLM call)."""
    from . import assembler

    doc = parse(source, list(copy_dirs), prefer=parser)
    click.echo(assembler.assemble_context(doc, source_path=source))


if __name__ == "__main__":
    main()
