"""CLI reporter (FR7.1) — rich terminal output.

Findings are grouped by severity then file, each carrying a provenance badge
(🟢 sourced / 🟡 synthesized / 🔵 inferred) and remediation guidance. The
provenance badge is intentionally prominent: the honesty gate must be visible in
the primary human output, not buried.
"""

from __future__ import annotations

import io

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from setup_trap.model import Provenance, Severity

_SEV_STYLE = {
    Severity.CRITICAL: "bold red",
    Severity.WARNING: "bold yellow",
    Severity.INFO: "cyan",
}
_SEV_ICON = {
    Severity.CRITICAL: "🔴",
    Severity.WARNING: "🟡",
    Severity.INFO: "🔵",
}


def render_cli(result, *, path: str = "", show_context: bool = True) -> str:
    """Render a ScanResult to the terminal; return the plain-text transcript.

    Returning the text (via a recording console) lets callers capture the exact
    output for the blog / snapshot tests.
    """

    # Render into a buffer (not the terminal): the caller prints the returned
    # text. record=True lets us export a clean plain-text transcript.
    console = Console(record=True, width=100, file=io.StringIO())

    console.print()
    console.rule("[bold]SetupTrap scan[/bold]")
    header = Text()
    header.append(f"path: {path or '.'}\n")
    header.append(
        f"files scanned: {result.files_scanned}    rules: {result.rules_loaded}"
    )
    console.print(header)
    console.print()

    if not result.findings:
        console.print(
            Panel(
                "[green]No findings. Clean.[/green]",
                border_style="green",
                title="Result",
            )
        )
        _print_legend(console)
        return console.export_text()

    grouped = result.by_severity()
    for sev in (Severity.CRITICAL, Severity.WARNING, Severity.INFO):
        findings = grouped[sev]
        if not findings:
            continue
        console.print(
            f"{_SEV_ICON[sev]} [{_SEV_STYLE[sev]}]{sev.label}[/] "
            f"({len(findings)})"
        )
        for f in findings:
            _print_finding(console, f, show_context=show_context)
        console.print()

    _print_summary(console, result)
    _print_legend(console)
    return console.export_text()


def _print_finding(console: Console, f, *, show_context: bool) -> None:
    prov = Provenance(f.provenance) if isinstance(f.provenance, str) else f.provenance
    badge = prov.badge
    title = Text()
    title.append(f"  [{f.rule_id}] ", style="bold")
    title.append(f.rule_name)
    console.print(title)
    console.print(f"      {badge}", style="dim")
    console.print(f"      file: {f.file}:{f.line}", style="dim")
    console.print(f"      match: {f.matched_text!r}")
    console.print(f"      {f.message.strip()}")
    if f.source_ref:
        console.print(f"      source: {f.source_ref}", style="dim")
    if f.note:
        console.print(f"      note: {f.note}", style="italic cyan")
    if f.fix_guidance:
        console.print(f"      fix: {f.fix_guidance.strip()}", style="green")
    console.print()


def _print_summary(console: Console, result) -> None:
    table = Table(title="Summary", show_edge=True)
    table.add_column("Severity")
    table.add_column("Count", justify="right")
    grouped = result.by_severity()
    for sev in (Severity.CRITICAL, Severity.WARNING, Severity.INFO):
        table.add_row(
            f"{_SEV_ICON[sev]} {sev.label}",
            str(len(grouped[sev])),
        )
    table.add_row("[bold]Total[/bold]", f"[bold]{len(result.findings)}[/bold]")
    console.print(table)

    # Provenance breakdown — keep the honesty gate visible in the summary.
    prov_counts = {p: 0 for p in Provenance}
    for f in result.findings:
        prov = Provenance(f.provenance) if isinstance(f.provenance, str) else f.provenance
        prov_counts[prov] += 1
    ptable = Table(title="Provenance", show_edge=True)
    ptable.add_column("Provenance")
    ptable.add_column("Count", justify="right")
    for p in Provenance:
        ptable.add_row(p.badge, str(prov_counts[p]))
    console.print(ptable)


def _print_legend(console: Console) -> None:
    console.print()
    console.print(
        Panel(
            "🟢 sourced   = package-install supply-chain checks empirically "
            "evaluated by arXiv:2607.15143\n"
            "🟡 synthesized = behavior-hijacking rules grounded in "
            "prompt-injection literature, NOT paper-proven\n"
            "🔵 inferred  = reasonable deduction (e.g. undocumented runtime "
            "read-order)",
            title="Provenance legend (honesty gate)",
            border_style="blue",
        )
    )


def render_surface_cli(inventory) -> str:
    """Render a surface inventory to the terminal; return the transcript."""

    console = Console(record=True, width=100, file=io.StringIO())
    console.print()
    console.rule(f"[bold]Attack surface — {inventory.display_name}[/bold]")
    console.print(inventory.summary)
    console.print()

    table = Table(show_lines=True, width=98)
    table.add_column("File / surface", style="bold", overflow="fold")
    table.add_column("When read", overflow="fold")
    table.add_column("Scope")
    table.add_column("Prov.")
    table.add_column("Attacker can write THIS → do THAT", overflow="fold")
    for e in inventory.entries:
        prov = e.provenance
        table.add_row(
            e.path,
            e.when_read,
            e.scope,
            prov.short_badge,
            e.risk + (f"\n[dim]{e.note}[/dim]" if e.note else ""),
        )
    console.print(table)
    _print_legend(console)
    return console.export_text()
