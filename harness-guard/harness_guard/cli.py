"""HarnessGuard CLI.

    harness-guard scan --target <path> [OPTIONS]

Exit codes:
    0  PASS — target hardened (all requested vectors blocked)
    1  FAIL — target vulnerable (a vector triggered a tool without a model turn)
    2  error / inconclusive
"""

from __future__ import annotations

import json
import shlex
import sys
from typing import Sequence

import click

from .adapters.mcp_stdio import McpStdioAdapter
from .observe.sidefx import CanaryWorkspace
from .scanner import ALL_VECTORS, scan

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERROR = 2


def _parse_vectors(vectors: str) -> list[str]:
    if not vectors or vectors.strip().lower() == "all":
        return list(ALL_VECTORS)
    chosen = [v.strip() for v in vectors.split(",") if v.strip()]
    unknown = [v for v in chosen if v not in ALL_VECTORS]
    if unknown:
        raise click.BadParameter(f"unknown vector(s): {', '.join(unknown)}")
    return chosen


def _target_cmd(target: str) -> list[str]:
    """Build the subprocess command for an MCP stdio target.

    If the target is a module path we know (the demos), run it with ``-m``;
    otherwise treat it as a shell command line.
    """
    if target in ("vulnerable", "hardened"):
        return [sys.executable, "-m", f"harness_guard.demo.{target}_harness"]
    return shlex.split(target)


def _render_rich(report: dict) -> None:
    from rich.console import Console
    from rich.table import Table

    console = Console()
    verdict = report["overall_verdict"]
    color = {"VULNERABLE": "bold red", "HARDENED": "bold green"}.get(verdict, "yellow")
    console.print(f"\n[b]HarnessGuard[/b] — target: [cyan]{report['target']}[/cyan] "
                  f"via [magenta]{report['adapter']}[/magenta]")
    console.print(f"Overall verdict: [{color}]{verdict}[/] "
                  f"(hardening tier {report['hardening_tier']})")

    vt = Table(title="Attack vectors")
    vt.add_column("vector")
    vt.add_column("verdict")
    vt.add_column("response")
    vt.add_column("side effects")
    for name, v in report["vectors"].items():
        vv = v["verdict"]
        vc = {"VULNERABLE": "red", "HARDENED": "green"}.get(vv, "yellow")
        vt.add_row(name, f"[{vc}]{vv}[/]", str(v.get("response_type")),
                   ", ".join(v.get("side_effects_detected") or []) or "-")
    console.print(vt)

    if report["tools"]:
        tt = Table(title="Tool risk tiers")
        tt.add_column("tool")
        tt.add_column("risk tier")
        for tool in report["tools"]:
            tt.add_row(tool["name"], tool["risk_tier"])
        console.print(tt)

    console.print("\n[b]Remediation[/b]:")
    for item in report["remediation"]:
        console.print(f"  • {item}")
    console.print()


def _emit(report: dict, output: str) -> None:
    if output in ("json", "both"):
        click.echo(json.dumps(report, indent=2, default=str))
    if output in ("rich", "both"):
        _render_rich(report)


def _exit_code(report: dict) -> int:
    verdict = report["overall_verdict"]
    if verdict == "HARDENED":
        return EXIT_PASS
    if verdict == "VULNERABLE":
        return EXIT_FAIL
    return EXIT_ERROR


def _scan_target(target: str, vectors: list[str], tool_name: str, tool_input: dict,
                 allow_destructive: bool) -> dict:
    env = {"HARNESS_GUARD_ALLOW_DESTRUCTIVE": "1"} if allow_destructive else {}
    with CanaryWorkspace() as ws:
        adapter = McpStdioAdapter(_target_cmd(target), workspace=ws, env=env)
        tools = adapter.list_tools()
        return scan(adapter, tool_name=tool_name, tool_input=tool_input,
                    vectors=vectors, tools=tools, target=target)


@click.group()
@click.version_option(package_name="harness-guard")
def cli() -> None:
    """HarnessGuard — agent harness bypass security tester (CoreBreak class)."""


@cli.command()
@click.option("--target", "target", help="Target harness: 'vulnerable'/'hardened' demo, "
              "or an MCP stdio server command line.")
@click.option("--adapter", default="mcp_stdio",
              type=click.Choice(["mcp_stdio", "openai", "agentcore"]), help="Transport adapter.")
@click.option("--vectors", default="all", help="Comma list: direct,replay,cross_session or 'all'.")
@click.option("--output", default="both", type=click.Choice(["rich", "json", "both"]))
@click.option("--allow-destructive", is_flag=True, default=False,
              help="Enable destructive canaries (outbound loopback callback). Off by default.")
@click.option("--self-test", "self_test", is_flag=True, default=False,
              help="Run the differential oracle against the demo vulnerable+hardened pair.")
@click.option("--tool", "tool_name", default="write_sentinel_file",
              help="Canary tool to attempt to trigger.")
def scan_cmd(target, adapter, vectors, output, allow_destructive, self_test, tool_name):
    """Scan a harness for the CoreBreak tool-dispatch bypass."""
    try:
        vector_list = _parse_vectors(vectors)
    except click.BadParameter as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(EXIT_ERROR)

    tool_input = {"content": "harness-guard-canary"}

    if self_test:
        code = _run_self_test(vector_list, output, tool_name, tool_input, allow_destructive)
        sys.exit(code)

    if not target:
        click.echo("error: --target is required (or use --self-test)", err=True)
        sys.exit(EXIT_ERROR)

    if adapter != "mcp_stdio":
        click.echo(
            "error: only the mcp_stdio adapter is wired for --target in this CLI; "
            "openai/agentcore adapters are available programmatically.",
            err=True,
        )
        sys.exit(EXIT_ERROR)

    try:
        report = _scan_target(target, vector_list, tool_name, tool_input, allow_destructive)
    except Exception as exc:  # noqa: BLE001 - surface as error exit
        click.echo(f"error: scan failed: {exc}", err=True)
        sys.exit(EXIT_ERROR)

    _emit(report, output)
    sys.exit(_exit_code(report))


def _run_self_test(vectors: list[str], output: str, tool_name: str, tool_input: dict,
                   allow_destructive: bool) -> int:
    """Differential oracle: vulnerable must FAIL, hardened must PASS."""
    vuln = _scan_target("vulnerable", vectors, tool_name, tool_input, allow_destructive)
    hard = _scan_target("hardened", vectors, tool_name, tool_input, allow_destructive)

    _emit(vuln, output)
    _emit(hard, output)

    vuln_ok = vuln["overall_verdict"] == "VULNERABLE"
    hard_ok = hard["overall_verdict"] == "HARDENED"
    click.echo(
        f"\nself-test: vulnerable={'FAIL(expected)' if vuln_ok else vuln['overall_verdict']} "
        f"hardened={'PASS(expected)' if hard_ok else hard['overall_verdict']}"
    )
    if vuln_ok and hard_ok:
        click.echo("self-test: differential oracle satisfied ✓")
        return EXIT_PASS
    click.echo("self-test: differential oracle FAILED", err=True)
    return EXIT_ERROR


# click group is the entry; expose scan as `scan`.
cli.add_command(scan_cmd, name="scan")


def main(argv: Sequence[str] | None = None) -> None:
    cli.main(args=list(argv) if argv is not None else None, standalone_mode=True)


if __name__ == "__main__":
    main()
