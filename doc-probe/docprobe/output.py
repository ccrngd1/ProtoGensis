"""Rendering: rich terminal report, JSON, and markdown."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from docprobe.models import ScanResult

TIER_STYLE = {"grounded": "green", "partial": "yellow", "opinionated": "magenta"}
GRADE_STYLE = {"A": "green", "B": "green", "C": "yellow", "D": "red", "F": "bold red"}


def render_rich(result: ScanResult, console: Console) -> None:
    console.print(
        Panel(
            f"DocProbe v{result.docprobe_version} · rubric v{result.rubric_version} · "
            + (
                f"LLM: {result.llm.model} ({result.llm.calls} calls, "
                f"{result.llm.cache_hits} cache hits)"
                if result.llm.enabled
                else "LLM: off (--no-llm) — deterministic dimensions only"
            ),
            title="docprobe scan",
        )
    )
    for f in result.files:
        if f.error:
            console.print(f"[red]✗ {f.path}[/red] — {f.error}")
            continue
        grade = f.overall_grade or "?"
        console.print(
            f"\n[bold]{f.path}[/bold] — overall "
            f"[{GRADE_STYLE.get(grade, 'white')}]{grade}[/] ({f.overall_score})"
        )
        table = Table(show_header=True, header_style="bold")
        table.add_column("dimension")
        table.add_column("grade")
        table.add_column("score")
        table.add_column("evidence tier")
        table.add_column("weight")
        table.add_column("flags")
        for d in f.dimensions:
            table.add_row(
                d.name,
                f"[{GRADE_STYLE.get(d.grade, 'white')}]{d.grade}[/]",
                f"{d.score:.0f}",
                f"[{TIER_STYLE[d.evidence_tier]}]{d.evidence_tier}[/]",
                f"{d.weight}",
                str(len(d.flags)),
            )
        console.print(table)
        for d in f.dimensions:
            for flag in d.flags:
                loc = f":{flag.line}" if flag.line else ""
                console.print(f"  [dim]{d.name}{loc}[/dim] {flag.rationale}")
                if flag.passage:
                    console.print(f'    [italic]"{_trunc(flag.passage)}"[/italic]')
                if flag.related_passage:
                    console.print(f'    [italic]vs "{_trunc(flag.related_passage)}"[/italic]')
                if flag.suggestion:
                    console.print(f"    [cyan]→ {flag.suggestion}[/cyan]")
        if f.skipped_dimensions:
            console.print(
                f"  [dim]skipped (no LLM): {', '.join(f.skipped_dimensions)}[/dim]"
            )
    if not result.files:
        console.print("[yellow]No files matched.[/yellow]")


def render_json(result: ScanResult) -> str:
    return result.model_dump_json(indent=2)


def render_markdown(result: ScanResult) -> str:
    lines = [
        f"# DocProbe report (v{result.docprobe_version}, rubric v{result.rubric_version})",
        "",
        (
            f"LLM judge: `{result.llm.model}` — {result.llm.calls} calls, "
            f"{result.llm.cache_hits} cache hits"
            if result.llm.enabled
            else "LLM judge: **off** (`--no-llm`) — deterministic dimensions only"
        ),
        "",
    ]
    for f in result.files:
        if f.error:
            lines += [f"## {f.path}", "", f"**Error:** {f.error}", ""]
            continue
        lines += [f"## {f.path} — {f.overall_grade} ({f.overall_score})", ""]
        lines.append("| dimension | grade | score | evidence tier | weight | flags |")
        lines.append("|---|---|---|---|---|---|")
        for d in f.dimensions:
            lines.append(
                f"| {d.name} | {d.grade} | {d.score:.0f} | {d.evidence_tier} "
                f"| {d.weight} | {len(d.flags)} |"
            )
        lines.append("")
        for d in f.dimensions:
            for flag in d.flags:
                loc = f" (line {flag.line})" if flag.line else ""
                lines.append(f"- **{d.name}**{loc}: {flag.rationale}")
                if flag.passage:
                    lines.append(f'  - passage: "{_trunc(flag.passage)}"')
                if flag.related_passage:
                    lines.append(f'  - vs: "{_trunc(flag.related_passage)}"')
                if flag.suggestion:
                    lines.append(f"  - suggestion: {flag.suggestion}")
        if f.skipped_dimensions:
            lines.append(f"- skipped (no LLM): {', '.join(f.skipped_dimensions)}")
        lines.append("")
    if not result.files:
        lines.append("No files matched.")
    return "\n".join(lines)


def _trunc(text: str, limit: int = 100) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
