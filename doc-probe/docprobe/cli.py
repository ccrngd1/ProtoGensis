"""DocProbe CLI (typer + rich).

Exit codes: 0 = scan completed (low scores are findings, not failures);
2 = scan error (bad arguments, unreadable state, unexpected exception).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from docprobe.judge import DEFAULT_MODEL, Judge
from docprobe.models import ScanResult
from docprobe.output import render_json, render_markdown, render_rich
from docprobe.scanner import DEFAULT_GLOBS, run_scan

app = typer.Typer(
    name="docprobe",
    help="Audit AI-agent instruction files: will an agent actually comply with this?",
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)

EXIT_OK = 0
EXIT_ERROR = 2


def _build_judge(no_llm: bool, model: str, prepass: bool) -> Optional[Judge]:
    if no_llm:
        return None
    return Judge(model=model, prepass=prepass)


def _emit(result: ScanResult, format: str, output: Optional[Path]) -> None:
    if format not in ("rich", "json", "markdown", "both"):
        raise typer.BadParameter(f"unknown format {format!r}")
    if format in ("rich", "both") and output is None:
        render_rich(result, console)
    if format in ("json", "both"):
        payload = render_json(result)
        if output:
            output.write_text(payload, encoding="utf-8")
        else:
            if format == "json":
                print(payload)
            else:
                (Path("docprobe-report.json")).write_text(payload, encoding="utf-8")
                console.print("[dim]wrote docprobe-report.json[/dim]")
    if format == "markdown":
        payload = render_markdown(result)
        if output:
            output.write_text(payload, encoding="utf-8")
        else:
            print(payload)
    if format == "rich" and output is not None:
        # rich to a file degrades to markdown
        output.write_text(render_markdown(result), encoding="utf-8")


@app.command()
def scan(
    targets: list[str] = typer.Argument(None, help="Files to scan (default: common instruction files)"),
    glob: list[str] = typer.Option(None, "--glob", help="Glob pattern(s) to scan"),
    format: str = typer.Option("rich", "--format", help="rich | json | markdown | both"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", help="Judge model (litellm id)"),
    prepass: bool = typer.Option(False, "--prepass", help="Cheap Haiku prepass before the judge"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Deterministic dimensions only; fully offline"),
    output: Optional[Path] = typer.Option(None, "--output", help="Write the report to a file"),
) -> None:
    """Score instruction files on the five DocProbe dimensions."""
    patterns = list(targets or []) + list(glob or [])
    if not patterns:
        patterns = list(DEFAULT_GLOBS)
    try:
        judge = _build_judge(no_llm, model, prepass)
        result = run_scan(patterns, judge)
        _emit(result, format, output)
    except typer.BadParameter:
        raise
    except Exception as exc:  # scan error → exit 2
        err_console.print(f"[red]scan error:[/red] {exc}")
        raise typer.Exit(EXIT_ERROR)
    raise typer.Exit(EXIT_OK)


@app.command()
def report(
    targets: list[str] = typer.Argument(None),
    glob: list[str] = typer.Option(None, "--glob"),
    format: str = typer.Option("markdown", "--format", help="rich | json | markdown | both"),
    model: str = typer.Option(DEFAULT_MODEL, "--model"),
    prepass: bool = typer.Option(False, "--prepass"),
    no_llm: bool = typer.Option(False, "--no-llm"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    """Like scan, but defaults to a shareable markdown report."""
    scan(
        targets=targets,
        glob=glob,
        format=format,
        model=model,
        prepass=prepass,
        no_llm=no_llm,
        output=output,
    )


@app.command()
def fix(
    targets: list[str] = typer.Argument(None),
    glob: list[str] = typer.Option(None, "--glob"),
    model: str = typer.Option(DEFAULT_MODEL, "--model"),
    prepass: bool = typer.Option(False, "--prepass"),
    no_llm: bool = typer.Option(False, "--no-llm"),
    output: Optional[Path] = typer.Option(None, "--output", help="Write fixes as JSON"),
) -> None:
    """Propose edits for flagged passages.

    For contradiction flags, DocProbe prefers ATTACHING a rationale comment
    over deleting a directive (per arXiv:2608.11095): an orphaned directive's
    fix is the proposed rationale.
    """
    from docprobe.fixer import fixes_for

    patterns = list(targets or []) + list(glob or [])
    if not patterns:
        patterns = list(DEFAULT_GLOBS)
    try:
        judge = _build_judge(no_llm, model, prepass)
        result = run_scan(patterns, judge)
        all_fixes = [fx for f in result.files for fx in fixes_for(f)]
        if output:
            import json

            output.write_text(
                json.dumps([fx.model_dump() for fx in all_fixes], indent=2),
                encoding="utf-8",
            )
        else:
            if not all_fixes:
                console.print("No fixes to suggest.")
            for fx in all_fixes:
                loc = f":{fx.line}" if fx.line else ""
                console.print(f"\n[bold]{fx.path}{loc}[/bold] [{fx.dimension} · {fx.kind}]")
                if fx.original:
                    console.print(f'  [italic]"{fx.original}"[/italic]')
                console.print(f"  why: {fx.why}")
                console.print(f"  [cyan]→ {fx.suggestion}[/cyan]")
    except Exception as exc:
        err_console.print(f"[red]scan error:[/red] {exc}")
        raise typer.Exit(EXIT_ERROR)
    raise typer.Exit(EXIT_OK)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
