"""memdoc CLI. Exit codes: 0 ok; 1 check failed; 2 usage/config error;
3 report refused headline comparisons; 4 run refused (prereg); 5 budget abort."""

import argparse
import json
import sys
from pathlib import Path

from . import MECHANISM_BANNER

PKG_ROOT = Path(__file__).resolve().parent.parent


def _print(s):
    sys.stdout.write(s + "\n")


# ----------------------------------------------------------------- subcommands

def cmd_arms_list(args):
    from .backends import MVP_ARMS, SHOULD_SHIP_ARMS, registry
    from .backends.base import arms_table
    reg = registry()
    order = [a for a in ("a0", "astar", "a1", "a2", "a3", "a4", "a5", "a5bg", "a6")
             if a in reg]
    rows = arms_table([reg[a] for a in order])
    if args.format == "json":
        _print(json.dumps(rows, sort_keys=True, indent=1))
        return 0
    hdr = ["id", "name", "write policy", "read policy", "inject"]
    if args.format == "md":
        _print("| " + " | ".join(hdr) + " |")
        _print("|" + "---|" * len(hdr))
        for r in rows:
            note = " (weak baseline)" if r["id"] == "a3" else ""
            _print(f"| {r['id']} | {r['name']}{note} | {r['write_policy']} | "
                   f"{r['read_policy']} | {r['inject']} |")
    else:
        for r in rows:
            _print(f"{r['id']:6s} {r['name']:18s} write={r['write_policy']:11s} "
                   f"read={r['read_policy']:14s} inject={r['inject']}")
    return 0


def cmd_tasks_generate(args):
    from .tasks.generate import write_tree
    write_tree(args.out, args.seed)
    _print(f"wrote storylines to {args.out} (seed {args.seed})")
    return 0


def cmd_tasks_validate(args):
    from .tasks.validate import validate
    violations = validate(args.tasks)
    if violations:
        for v in violations:
            _print("VIOLATION: " + v)
        return 1
    _print("tasks validate: OK")
    return 0


def cmd_prereg_show(args):
    from . import prereg
    if args.format == "json":
        payload = json.loads(prereg.canonical_json())
        payload["hash"] = prereg.prereg_hash()
        _print(json.dumps(payload, sort_keys=True, indent=1))
    else:
        _print(prereg.render_markdown())
    return 0


def cmd_prereg_verify(args):
    from . import prereg
    ok, msg = prereg.verify()
    _print(msg)
    if ok and args.history:
        ok2, msg2 = prereg.verify_history()
        _print(msg2)
        return 0 if ok2 else 1
    return 0 if ok else 1


def cmd_demo_crossover(args):
    from .demos import demo_crossover, render_crossover
    seeds = [int(x) for x in args.seeds.split(",")] if args.seeds else None
    sizes = [int(x) for x in args.sizes.split(",")] if args.sizes else None
    arms = args.arms.split(",") if args.arms else None
    data = demo_crossover(seeds=seeds, sizes=sizes, arms=arms)
    out = render_crossover(data, args.format)
    if args.out:
        Path(args.out).write_text(out + "\n", encoding="utf-8")
        _print(f"wrote {args.out}")
    else:
        _print(out)
    return 0


def cmd_demo_cache(args):
    from .demos import demo_cache, render_cache
    _print(render_cache(demo_cache(), args.format))
    return 0


def cmd_demo_costmodel(args):
    from .demos import demo_costmodel, render_costmodel
    _print(render_costmodel(demo_costmodel(), args.format))
    return 0


def cmd_demo_stale(args):
    from .demos import demo_stale, render_stale
    live = args.live == "bedrock"
    data = demo_stale(live=live, region=args.region)
    _print(render_stale(data, args.format))
    return 0


def cmd_run(args):
    from . import prereg
    ok, msg = prereg.verify()
    if not ok:
        _print(f"run refused: {msg}")
        return 4
    arms = args.arms.split(",")
    sizes = [int(x) for x in args.sizes.split(",")]
    seeds = [int(x) for x in args.seeds.split(",")]
    categories = _parse_categories(args.categories) if args.categories else None

    if args.live:
        if args.live != "bedrock":
            _print("usage error: --live must be 'bedrock'")
            return 2
        if args.max_usd is None:
            _print("usage error: --live requires --max-usd")
            return 2
        if not args.model_id:
            _print("usage error: --live requires --model-id")
            return 2
        return _run_live(args, arms, sizes, seeds, categories)

    out = args.out or "/tmp/memdoc-mockrun"
    out_path = Path(out)
    if out_path.resolve() == (PKG_ROOT / "results").resolve() or \
            str(out_path.resolve()).startswith(str((PKG_ROOT / "results").resolve()) + "/"):
        _print("usage error: mock runs may not write to results/ (reserved for live logs)")
        return 2
    from .runner import run_mock
    _print(MECHANISM_BANNER)
    results, runlog = run_mock(arms, sizes, seeds, out, categories=categories,
                               profile=args.profile, p_forget=args.p_forget)
    _print(f"mock run complete: {len(results)} cells -> {runlog}")
    return 0


def _run_live(args, arms, sizes, seeds, categories):
    # Live loop: optional, budget-capped, never invoked by tests (AC #13).
    import importlib.util
    if importlib.util.find_spec("boto3") is None:
        _print("usage error: --live requires the [bedrock] extra (pip install -e '.[bedrock]')")
        return 2
    _print("live run path: budget-capped Bedrock run. Not executed in this build "
           "(no credentials; paid runs need CC's go-ahead with the dry-run projection).")
    _print(f"would run arms={arms} sizes={sizes} seeds={seeds} model={args.model_id} "
           f"region={args.region} max_usd={args.max_usd} dry_run={args.dry_run}")
    return 0


def _parse_categories(spec):
    out = set()
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return sorted(out)


def cmd_report(args):
    from .report import build_report, render
    report, code = build_report(args.runlog)
    _print(render(report, args.format))
    return code


def cmd_health(args):
    from .health import arm_invalid_rates, cell_validity
    from .runlog import read_events
    cells = [e for e in read_events(args.runlog) if e.get("event") == "cell"]
    if not cells:
        _print("no cell events in run log")
        return 1
    _print(MECHANISM_BANNER)
    for c in cells:
        status, reason = cell_validity(c)
        if status == "INVALID":
            _print(f"INVALID {c['arm']}@{c['size']} {c['storyline']} seed={c['seed']}: {reason}")
    for arm, r in arm_invalid_rates(cells).items():
        _print(f"{arm}: {r['invalid']}/{r['total']} invalid ({100 * r['rate']:.1f}%)")
    return 0


def cmd_decay(args):
    from .decay import analyze, render
    try:
        data = analyze(args.repo, args.file, args.until)
    except RuntimeError as e:
        _print(f"error: {e}")
        return 2
    _print(render(data, args.format))
    return 0


def cmd_reference_init(args):
    from .reference import init
    try:
        target = init(args.dir)
    except FileExistsError as e:
        _print(f"error: {e}")
        return 2
    _print(f"wrote synthetic hybrid-tiered template to {target}")
    return 0


def cmd_reference_check(args):
    from .reference import check
    violations = check(args.dir, core_budget=args.core_budget)
    if violations:
        for v in violations:
            _print("FAIL: " + v)
        return 1
    _print("reference check: OK")
    return 0


def cmd_claims_verify(args):
    from .claims import verify
    ok, lines = verify(ledger_path=args.ledger)
    for line in lines:
        _print(line)
    _print("claims verify: " + ("OK" if ok else "FAILED"))
    return 0 if ok else 1


# ---------------------------------------------------------------------- parser

def build_parser():
    p = argparse.ArgumentParser(prog="memdoc",
                                description="MemDoc: agent-written memory benchmark harness")
    sub = p.add_subparsers(dest="cmd", required=True)

    def fmt_arg(sp, choices=("terminal", "md", "json")):
        sp.add_argument("--format", choices=choices, default="terminal")

    sp = sub.add_parser("arms"); s2 = sp.add_subparsers(dest="sub", required=True)
    x = s2.add_parser("list"); fmt_arg(x); x.set_defaults(fn=cmd_arms_list)

    sp = sub.add_parser("tasks"); s2 = sp.add_subparsers(dest="sub", required=True)
    x = s2.add_parser("generate")
    x.add_argument("--seed", type=int, default=41)
    x.add_argument("--out", default="tasks")
    x.set_defaults(fn=cmd_tasks_generate)
    x = s2.add_parser("validate")
    x.add_argument("--tasks", default="tasks")
    x.set_defaults(fn=cmd_tasks_validate)

    sp = sub.add_parser("prereg"); s2 = sp.add_subparsers(dest="sub", required=True)
    x = s2.add_parser("show"); fmt_arg(x, ("md", "json")); x.set_defaults(fn=cmd_prereg_show)
    x = s2.add_parser("verify")
    x.add_argument("--history", action="store_true")
    x.set_defaults(fn=cmd_prereg_verify)

    sp = sub.add_parser("demo"); s2 = sp.add_subparsers(dest="sub", required=True)
    x = s2.add_parser("crossover")
    x.add_argument("--seeds"); x.add_argument("--sizes"); x.add_argument("--arms")
    x.add_argument("--out"); fmt_arg(x); x.set_defaults(fn=cmd_demo_crossover)
    x = s2.add_parser("cache"); fmt_arg(x); x.set_defaults(fn=cmd_demo_cache)
    x = s2.add_parser("costmodel"); fmt_arg(x); x.set_defaults(fn=cmd_demo_costmodel)
    x = s2.add_parser("stale")
    x.add_argument("--live", choices=["bedrock"])
    x.add_argument("--region", default="us-east-1")
    fmt_arg(x); x.set_defaults(fn=cmd_demo_stale)

    x = sub.add_parser("run")
    x.add_argument("--arms", default="a0,astar,a1,a2,a4,a5,a6")
    x.add_argument("--sizes", default="25000")
    x.add_argument("--seeds", default="0,1,2")
    x.add_argument("--categories")
    x.add_argument("--profile", choices=["short", "medium", "long"])
    x.add_argument("--p-forget", type=float, default=0.0,
                   help="seeded write-skip sweep (exploratory)")
    x.add_argument("--live", choices=["bedrock"])
    x.add_argument("--model-id")
    x.add_argument("--region", default="us-east-1")
    x.add_argument("--max-usd", type=float)
    x.add_argument("--dry-run", type=int, nargs="?", const=20)
    x.add_argument("--out")
    x.set_defaults(fn=cmd_run)

    x = sub.add_parser("report")
    x.add_argument("--runlog", required=True); fmt_arg(x); x.set_defaults(fn=cmd_report)
    x = sub.add_parser("health")
    x.add_argument("--runlog", required=True); x.set_defaults(fn=cmd_health)

    x = sub.add_parser("decay")
    x.add_argument("--repo", required=True)
    x.add_argument("--file", required=True)
    x.add_argument("--until")
    fmt_arg(x); x.set_defaults(fn=cmd_decay)

    sp = sub.add_parser("reference"); s2 = sp.add_subparsers(dest="sub", required=True)
    x = s2.add_parser("init"); x.add_argument("dir"); x.set_defaults(fn=cmd_reference_init)
    x = s2.add_parser("check")
    x.add_argument("dir"); x.add_argument("--core-budget", type=int, default=5000)
    x.set_defaults(fn=cmd_reference_check)

    sp = sub.add_parser("claims"); s2 = sp.add_subparsers(dest="sub", required=True)
    x = s2.add_parser("verify")
    x.add_argument("--ledger", default=str(PKG_ROOT / "docs" / "CLAIMS.md"))
    x.set_defaults(fn=cmd_claims_verify)

    return p


def main(argv=None):
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        # argparse uses exit 2 for usage errors already
        raise
    return sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
