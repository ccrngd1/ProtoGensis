"""coherence-gate CLI.

Exit codes:
  demo / report: 0 ran, 2 error.
  audit identifiability: 0 identifiable, 1 aliased fiber found, 2 error.
  lint ownership: 0 aligned, 1 OWN001/OWN002, 2 error.
  topology check: 0 acyclic, 1 cyclic, 2 error.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys


def _write(text: str, out_path: str | None) -> None:
    if out_path:
        with open(out_path, "w") as f:
            f.write(text + "\n")
    else:
        print(text)


def _parse_seeds(raw: str | None) -> list[int] | None:
    if raw is None:
        return None
    return [int(x) for x in raw.split(",") if x.strip() != ""]


def cmd_demo(args) -> int:
    fmt = args.format
    if args.name == "budget":
        from .demos import budget
        text, code = budget.main(seeds=_parse_seeds(args.seeds),
                                 arms=args.arms.split(",") if args.arms else None,
                                 fmt=fmt)
    elif args.name == "identifiability":
        if getattr(args, "live", None):
            print("live mode is opt-in and not implemented in the offline CLI path; "
                  "see adapters.toolloop.run_live_bedrock", file=sys.stderr)
            return 2
        from .demos import identifiability
        text, code = identifiability.main(n_tasks=args.tasks, fmt=fmt)
    elif args.name == "telecom":
        from .demos import telecom
        text, code = telecom.main(fmt=fmt)
    elif args.name == "single-agent":
        from .demos import single_agent
        text, code = single_agent.main(fmt=fmt)
    elif args.name == "warmup":
        from .demos import warmup_lost_update
        text, code = warmup_lost_update.main(fmt=fmt)
    else:
        print(f"unknown demo: {args.name}", file=sys.stderr)
        return 2
    _write(text, args.out)
    return code


def cmd_audit_identifiability(args) -> int:
    from .audit.identifiability import audit, generate_family
    if args.family:
        module_name, _, factory_name = args.family.partition(":")
        try:
            module = importlib.import_module(module_name)
            tasks = getattr(module, factory_name)()
        except (ImportError, AttributeError) as exc:
            print(f"cannot load family {args.family}: {exc}", file=sys.stderr)
            return 2
    else:
        tasks = generate_family()
    variant = args.variant
    result = audit(tasks, variant)
    payload = {
        "aliased_fibers": result.aliased_fibers,
        "bound": round(result.worst_bound, 6),
        "identifiable": result.identifiable,
        "max_k": result.max_k,
        "n_worlds": result.n_worlds,
        "variant": variant,
    }
    if args.format == "json":
        _write(json.dumps(payload, sort_keys=True, indent=2), args.out)
    else:
        lines = [f"identifiability audit ({variant})"]
        for key, value in payload.items():
            lines.append(f"  {key}: {value}")
        _write("\n".join(lines), args.out)
    return 0 if result.identifiable else 1


def cmd_lint(args) -> int:
    from .audit.ownership_lint import run
    result = run(args.config, args.runlog)
    if result.error:
        print(f"error: {result.error}", file=sys.stderr)
        return 2
    if result.findings:
        for finding in result.findings:
            print(finding["message"])
    else:
        print("ownership lint: aligned (guard unit == graded unit)")
    return result.exit_code


def cmd_report(args) -> int:
    from .report import render, summarize
    from .runlog import RunLog
    try:
        events = RunLog.load(args.runlog)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot load runlog: {exc}", file=sys.stderr)
        return 2
    _write(render(summarize(events), args.format), args.out)
    return 0


def cmd_topology_check(args) -> int:
    from .topology import Topology
    try:
        with open(args.config) as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot load config: {exc}", file=sys.stderr)
        return 2
    topo = Topology()
    try:
        for role, spec in config["roles"].items():
            topo.register(role, set(spec.get("reads", [])), set(spec.get("writes", [])))
    except (KeyError, TypeError, AttributeError) as exc:
        print(f"error: bad config shape: {exc}", file=sys.stderr)
        return 2
    result = topo.gyo_check()
    print(result["message"])
    for row in topo.bernstein_table():
        status = "parallel-safe" if row["parallel_safe"] else \
            f"conflicts on {row['conflict_keys']}"
        print(f"  {row['pair'][0]} x {row['pair'][1]}: {status}")
    return 0 if result["acyclic"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coherence-gate",
        description="Commit-time coherence harness for multi-agent systems "
                    "(an executable spec of the harness in arXiv 2610.02036).")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="run a deterministic offline demo")
    demo.add_argument("name", choices=["budget", "identifiability", "telecom",
                                       "single-agent", "warmup"])
    demo.add_argument("--seeds", default=None, help="comma-separated, e.g. 0,1,2,3,4")
    demo.add_argument("--arms", default=None)
    demo.add_argument("--tasks", type=int, default=40)
    demo.add_argument("--format", choices=["terminal", "md", "json"], default="terminal")
    demo.add_argument("--out", default=None)
    demo.add_argument("--live", choices=["bedrock"], default=None)
    demo.add_argument("--model-id", default=None)
    demo.set_defaults(func=cmd_demo)

    audit_parser = sub.add_parser("audit", help="run an audit")
    audit_sub = audit_parser.add_subparsers(dest="audit_name", required=True)
    ident = audit_sub.add_parser("identifiability")
    ident.add_argument("--family", default=None, help="module:factory")
    ident.add_argument("--variant", choices=["identifiable", "aliased", "fact"],
                       default="aliased")
    ident.add_argument("--format", choices=["terminal", "json"], default="terminal")
    ident.add_argument("--out", default=None)
    ident.set_defaults(func=cmd_audit_identifiability)

    lint = sub.add_parser("lint", help="run a lint")
    lint_sub = lint.add_subparsers(dest="lint_name", required=True)
    ownership = lint_sub.add_parser("ownership")
    ownership.add_argument("--config", required=True)
    ownership.add_argument("--runlog", default=None)
    ownership.set_defaults(func=cmd_lint)

    report = sub.add_parser("report", help="build a report from a JSONL run log")
    report.add_argument("--runlog", required=True)
    report.add_argument("--format", choices=["terminal", "md", "json"], default="terminal")
    report.add_argument("--out", default=None)
    report.set_defaults(func=cmd_report)

    topo = sub.add_parser("topology", help="topology checks")
    topo_sub = topo.add_subparsers(dest="topology_name", required=True)
    check = topo_sub.add_parser("check")
    check.add_argument("--config", required=True)
    check.set_defaults(func=cmd_topology_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
