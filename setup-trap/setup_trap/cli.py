"""SetupTrap CLI (FR entry point).

Commands:
  setup-trap scan <path> [--category C] [--severity S] [--check-cve]
                         [--format cli|json|html] [--fail-on critical|warning]
                         [--simulate] [--simulate-all] [--no-calibrate]
  setup-trap surface --runtime claude_code|cursor|copilot|openclaw [--format ...]
  setup-trap audit <path> --runtime openclaw   # self-audit convenience wrapper
  setup-trap simulate <path>                    # LLM behavioral pass only
  setup-trap report ...                         # alias of scan with --format

Baseline `scan` is offline and credential-free. --check-cve and --simulate are
optional add-ons that degrade gracefully when their tooling/creds are absent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from setup_trap import __version__
from setup_trap.model import Severity


def _add_common_scan_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("path", help="file or directory to scan")
    p.add_argument("--category", help="only run rules in this category")
    p.add_argument(
        "--severity",
        choices=["info", "warning", "critical"],
        help="only show findings at or above this severity",
    )
    p.add_argument(
        "--check-cve",
        action="store_true",
        help="run pip-audit against pinned versions (optional; degrades if absent)",
    )
    p.add_argument(
        "--format",
        choices=["cli", "json", "html"],
        default="cli",
        help="output format (default: cli)",
    )
    p.add_argument(
        "--fail-on",
        choices=["critical", "warning"],
        default="critical",
        help="exit non-zero when a finding at/above this severity exists",
    )
    p.add_argument(
        "--no-calibrate",
        action="store_true",
        help="disable allowlist calibration (show raw severities)",
    )
    p.add_argument("--output", "-o", help="write report to a file instead of stdout")
    p.add_argument(
        "--simulate",
        action="store_true",
        help="add an LLM behavioral pass on files with findings (opt-in)",
    )
    p.add_argument(
        "--simulate-all",
        action="store_true",
        help="run the LLM behavioral pass on ALL scanned files (opt-in)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="setup-trap",
        description="Scan AI coding-agent setup/config files for injection attacks.",
    )
    parser.add_argument("--version", action="version", version=f"setup-trap {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="static scan of setup files")
    _add_common_scan_args(p_scan)

    p_report = sub.add_parser("report", help="scan and emit a report (alias of scan)")
    _add_common_scan_args(p_report)

    p_audit = sub.add_parser(
        "audit", help="self-audit: resolve a runtime's init files and scan them"
    )
    _add_common_scan_args(p_audit)
    p_audit.add_argument(
        "--runtime",
        default="openclaw",
        help="runtime whose init-file set to audit (default: openclaw)",
    )

    p_surface = sub.add_parser("surface", help="print a runtime's attack surface")
    p_surface.add_argument(
        "--runtime",
        required=True,
        help="claude_code | cursor | copilot | openclaw",
    )
    p_surface.add_argument(
        "--format", choices=["cli", "json"], default="cli"
    )
    p_surface.add_argument("--output", "-o", help="write to a file instead of stdout")

    p_sim = sub.add_parser("simulate", help="LLM behavioral simulation only")
    p_sim.add_argument("path", help="file or directory to simulate")
    p_sim.add_argument("--model", help="Bedrock model id override")
    p_sim.add_argument("--region", help="AWS region override")
    p_sim.add_argument("--format", choices=["cli", "json"], default="cli")

    return parser


# -- command handlers -------------------------------------------------------


def _run_scan(args, *, audit_runtime: str | None = None) -> int:
    from setup_trap.reporter import render_cli, render_html, render_json
    from setup_trap.scanner.calibration import Calibrator
    from setup_trap.scanner.engine import scan_path

    severity = Severity.from_str(args.severity) if args.severity else None
    calibrator = Calibrator(enabled=not args.no_calibrate)

    scan_target = args.path
    banner = None
    if audit_runtime:
        banner = f"[audit] runtime={audit_runtime} — scanning init-file surface"

    result = scan_path(
        scan_target,
        category=args.category,
        severity=severity,
        check_cve=args.check_cve,
        calibrator=calibrator,
    )

    # Optional LLM simulation pass (advisory).
    sim_results = []
    if args.simulate or args.simulate_all:
        sim_results = _run_simulation_pass(result, scan_target, args)

    fmt = args.format
    if fmt == "json":
        import json as _json

        from setup_trap.reporter.json_reporter import result_to_dict

        payload = result_to_dict(result, path=scan_target)
        if sim_results:
            payload["simulation"] = [s.to_dict() for s in sim_results]
        out = _json.dumps(payload, indent=2)
    elif fmt == "html":
        out = render_html(result, path=scan_target)
    else:
        if banner:
            print(banner)
        out = render_cli(result, path=scan_target)
        if sim_results:
            out += "\n" + _format_sim_cli(sim_results)

    _emit(out, getattr(args, "output", None))

    fail_on = Severity.from_str(args.fail_on)
    return result.exit_code(fail_on)


def _run_simulation_pass(result, scan_target, args) -> list:
    from setup_trap.scanner.engine import Engine
    from setup_trap.simulator import Simulator, is_available

    if not is_available():
        print(
            "[simulate] boto3 not installed — simulation skipped. "
            "Install with `pip install -e '.[simulate]'` and configure AWS "
            "credentials. Static findings above are unaffected.",
            file=sys.stderr,
        )
        return []

    sim = Simulator(
        model=getattr(args, "model", None), region=getattr(args, "region", None)
    )
    # Cost guard (FR6.4): only files with findings unless --simulate-all.
    if args.simulate_all:
        engine = Engine()
        files = list(engine._iter_files(Path(scan_target)))
    else:
        files = sorted({Path(f.file) for f in result.findings})
    return [sim.simulate_file(f) for f in files]


def _format_sim_cli(sim_results) -> str:
    lines = [
        "",
        "=== LLM behavioral simulation (ADVISORY, non-deterministic) ===",
        "Augments static findings; never overrides them. Accuracy vs real LLMs "
        "is NOT benchmarked.",
    ]
    for s in sim_results:
        lines.append(f"\n  file: {s.file}")
        if not s.available:
            lines.append(f"    unavailable: {s.error}")
            continue
        lines.append(f"    model: {s.model}   worst: {s.worst_rating}")
        for b in s.behaviors:
            lines.append(f"    [{b.rating}] {b.behavior}")
            if b.reason:
                lines.append(f"        reason: {b.reason}")
    return "\n".join(lines)


def _run_surface(args) -> int:
    from setup_trap.reporter.cli_reporter import render_surface_cli
    from setup_trap.reporter.json_reporter import surface_to_json
    from setup_trap.surface_mapper import get_inventory, list_runtimes

    try:
        inv = get_inventory(args.runtime)
    except KeyError:
        print(
            f"unknown runtime {args.runtime!r}; known: {list_runtimes()}",
            file=sys.stderr,
        )
        return 2

    out = surface_to_json(inv) if args.format == "json" else render_surface_cli(inv)
    _emit(out, getattr(args, "output", None))
    return 0


def _run_simulate(args) -> int:
    from setup_trap.scanner.engine import Engine
    from setup_trap.simulator import Simulator, is_available

    if not is_available():
        print(
            "boto3 not installed — install with `pip install -e '.[simulate]'` "
            "and configure AWS credentials.",
            file=sys.stderr,
        )
        return 3

    sim = Simulator(model=args.model, region=args.region)
    path = Path(args.path)
    if path.is_dir():
        engine = Engine()
        files = list(engine._iter_files(path))
    else:
        files = [path]
    results = [sim.simulate_file(f) for f in files]

    if args.format == "json":
        import json as _json

        print(_json.dumps([r.to_dict() for r in results], indent=2))
    else:
        print(_format_sim_cli(results))
    return 0


def _emit(text: str, output: str | None) -> None:
    if output:
        Path(output).write_text(text, encoding="utf-8")
        print(f"wrote report to {output}")
    else:
        print(text)


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in ("scan", "report"):
        return _run_scan(args)
    if args.command == "audit":
        return _run_scan(args, audit_runtime=args.runtime)
    if args.command == "surface":
        return _run_surface(args)
    if args.command == "simulate":
        return _run_simulate(args)
    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
