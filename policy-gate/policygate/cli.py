"""policygate CLI. The read-only guard is installed before argument dispatch."""

import argparse
import json
import sys

from . import guard

EXIT_OK = 0
EXIT_CHECK_FAILED = 1
EXIT_USAGE = 2
EXIT_GUARD = 3
EXIT_BUDGET = 5


def _collect_roots(ns):
    if ns.cmd == "guard":
        # `guard selftest` creates its own root first, then protects it
        return []
    roots = []
    for attr in ("root", "path", "against_archive", "verify_sources"):
        v = getattr(ns, attr, None)
        if v:
            roots.append(v)
    return roots


def build_parser():
    p = argparse.ArgumentParser(prog="policygate")
    sub = p.add_subparsers(dest="cmd", required=True)

    def fmt(sp, choices=("terminal", "md", "json")):
        sp.add_argument("--format", default="terminal", choices=choices)

    sp = sub.add_parser("vocab")
    sp.add_argument("action", choices=["list"])
    fmt(sp)

    sp = sub.add_parser("vtools")
    sp.add_argument("action", choices=["list"])
    fmt(sp)

    sp = sub.add_parser("guard")
    sp.add_argument("action", choices=["selftest"])
    sp.add_argument("--root", required=True)

    sp = sub.add_parser("bundle")
    sp.add_argument("action", choices=["show", "history"])
    sp.add_argument("--root", required=True)
    sp.add_argument("--bundle", required=True)
    sp.add_argument("--at")             # required for show
    sp.add_argument("--source")         # exit 2 if THIS source is ERROR
    sp.add_argument("--since")          # history only
    sp.add_argument("--until")          # history only
    fmt(sp)

    sp = sub.add_parser("parse")
    sp.add_argument("--root", required=True)
    sp.add_argument("--bundle", required=True)
    sp.add_argument("--at", required=True)
    fmt(sp)

    sp = sub.add_parser("compile")
    sp.add_argument("--root", required=True)
    sp.add_argument("--bundle", required=True)
    sp.add_argument("--at", required=True)
    sp.add_argument("--candidates", required=True)
    sp.add_argument("--out", required=True)
    fmt(sp)

    sp = sub.add_parser("extract")
    sp.add_argument("--live", required=True, choices=["bedrock"])
    sp.add_argument("--model-id", required=True)
    sp.add_argument("--votes", type=int, default=5)
    sp.add_argument("--max-usd", type=float, default=None)
    sp.add_argument("--bundle", required=True)
    sp.add_argument("--root")
    sp.add_argument("--at")
    sp.add_argument("--out")

    sp = sub.add_parser("rules")
    sp.add_argument("action", choices=["check"])
    sp.add_argument("rules_file")

    sp = sub.add_parser("candidates")
    sp.add_argument("action", choices=["check"])
    sp.add_argument("--parse-dump", action="append", required=True, dest="parse_dump")
    sp.add_argument("--candidates", required=True)
    fmt(sp, choices=("terminal", "json"))

    sp = sub.add_parser("normalize")
    g = sp.add_mutually_exclusive_group(required=True)
    g.add_argument("--cmd", dest="shell_cmd")
    g.add_argument("--corpus")
    sp.add_argument("--no-help-filter", action="store_true")
    sp.add_argument("--no-heredoc-skip", action="store_true")
    fmt(sp)

    sp = sub.add_parser("replay")
    sp.add_argument("--source", required=True, choices=["legacy-archive", "trajectory", "fixture"])
    sp.add_argument("--path", required=True)
    sp.add_argument("--root")
    sp.add_argument("--bundle")
    sp.add_argument("--candidates")
    sp.add_argument("--profile", required=True, choices=["pinned", "spike-parity"])
    sp.add_argument("--retroactive", action="store_true")
    sp.add_argument("--no-help-filter", action="store_true")
    sp.add_argument("--no-heredoc-skip", action="store_true")
    sp.add_argument("--baseline", choices=["keyword"])
    sp.add_argument("--out", required=True)
    fmt(sp)

    sp = sub.add_parser("report")
    sp.add_argument("--run", required=True)
    fmt(sp)

    sp = sub.add_parser("ambiguity")
    sp.add_argument("--run", required=True)
    sp.add_argument("--format", default="md", choices=["md", "json"])

    sp = sub.add_parser("amend")
    sp.add_argument("--run", required=True)
    sp.add_argument("--answers", required=True)
    sp.add_argument("--out", required=True)
    fmt(sp)

    sp = sub.add_parser("eval")
    sp.add_argument("--run", required=True)
    sp.add_argument("--labels", required=True)
    sp.add_argument("--baseline", choices=["keyword"])
    fmt(sp)

    sp = sub.add_parser("demo")
    sp.add_argument("which", choices=["compile", "feb19", "adversarial", "readings", "amend", "all"])
    sp.add_argument("--baseline", choices=["keyword"])
    sp.add_argument("--verify-sources", dest="verify_sources")
    fmt(sp)

    sp = sub.add_parser("scan-artifacts")
    sp.add_argument("--repo", required=True)
    sp.add_argument("--against-archive", dest="against_archive")
    sp.add_argument("--ids-only", action="store_true", dest="ids_only",
                    help="only the known-real-ID check (hashed banned list + redacted prefixes)")

    sp = sub.add_parser("results")
    sp.add_argument("action", choices=["lint", "get"])
    sp.add_argument("target")
    sp.add_argument("keypath", nargs="?")

    sp = sub.add_parser("claims")
    sp.add_argument("action", choices=["verify"])
    sp.add_argument("--ledger", default="docs/CLAIMS.md")

    return p


def _dispatch(ns):
    if ns.cmd == "guard":
        ok, lines = guard.selftest(ns.root)
        print("\n".join(lines))
        return EXIT_OK if ok else EXIT_CHECK_FAILED

    if ns.cmd == "vocab":
        from . import vocab
        print(vocab.render_list(ns.format))
        return EXIT_OK

    if ns.cmd == "vtools":
        from . import vtools
        print(vtools.render_list(ns.format))
        return EXIT_OK

    if ns.cmd == "bundle":
        from . import bundle
        b = bundle.PolicyBundle.load(ns.bundle, ns.root)
        if ns.action == "history":
            hist = bundle.history(b, since=ns.since, until=ns.until)
            print(bundle.render_history(b, hist, since=ns.since, until=ns.until,
                                        fmt=ns.format))
            if ns.source and hist.get(ns.source, {}).get("status") == "ERROR":
                print(f"error: source {ns.source!r}: {hist[ns.source]['error']}",
                      file=sys.stderr)
                return EXIT_USAGE
            return EXIT_OK
        if not ns.at:
            print("error: bundle show requires --at", file=sys.stderr)
            return EXIT_USAGE
        at = b.at(ns.at)
        print(bundle.render_show(at, ns.format))
        # exit 2 only if the user asked for a specific source and IT errored
        if ns.source:
            src = at.sources.get(ns.source)
            if src is None or src.status == "ERROR":
                msg = src.error if src else "not in bundle"
                print(f"error: source {ns.source!r}: {msg}", file=sys.stderr)
                return EXIT_USAGE
        return EXIT_OK

    if ns.cmd == "parse":
        from . import bundle, parse
        b = bundle.PolicyBundle.load(ns.bundle, ns.root)
        clauses = parse.parse_bundle(b.at(ns.at))
        print(parse.render(clauses, ns.format))
        return EXIT_OK

    if ns.cmd == "compile":
        from . import emit
        report = emit.compile_cmd(ns.root, ns.bundle, ns.at, ns.candidates, ns.out)
        print(emit.render_report(report, ns.format))
        return EXIT_OK

    if ns.cmd == "extract":
        if ns.max_usd is None:
            print("error: --max-usd is required for live extraction (CC-D2)", file=sys.stderr)
            return EXIT_USAGE
        from .extract import live_bedrock
        return live_bedrock.run_live(ns)

    if ns.cmd == "rules":
        from . import resolve, rules
        loaded = rules.load_candidates(ns.rules_file)
        _, report = resolve.resolve(loaded)
        bad = [r for r in report if r["outcome"] in ("REJECT", "REPAIR")]
        for r in report:
            print(f"RESOLVE {r['id']}: {r['outcome']} {r['class']}: {r['detail']}")
        if bad:
            print(f"rules check: {len(bad)} rejected or repaired")
            return EXIT_CHECK_FAILED
        print("rules check: OK")
        return EXIT_OK

    if ns.cmd == "candidates":
        from . import candidates_check
        return candidates_check.check_cmd(ns)

    if ns.cmd == "normalize":
        from . import normalize
        if ns.corpus:
            out = normalize.score_corpus(ns.corpus, help_filter=not ns.no_help_filter,
                                         heredoc_skip=not ns.no_heredoc_skip)
        else:
            out = normalize.normalize_cmd(ns.shell_cmd, help_filter=not ns.no_help_filter,
                                          heredoc_skip=not ns.no_heredoc_skip)
        print(normalize.render(out, ns.format))
        return EXIT_OK

    if ns.cmd == "replay":
        from . import replay
        return replay.replay_cmd(ns)

    if ns.cmd == "report":
        from . import report
        print(report.render_run(ns.run, ns.format))
        return EXIT_OK

    if ns.cmd == "ambiguity":
        from . import ambiguity
        print(ambiguity.render_run(ns.run, ns.format))
        return EXIT_OK

    if ns.cmd == "amend":
        from . import amend
        out = amend.amend_cmd(ns.run, ns.answers, ns.out)
        print(amend.render(out, ns.format))
        return EXIT_OK

    if ns.cmd == "eval":
        from . import evaluate
        out = evaluate.eval_cmd(ns.run, ns.labels, baseline=ns.baseline)
        print(evaluate.render(out, ns.format))
        return EXIT_OK

    if ns.cmd == "demo":
        from . import demos
        return demos.run(ns)

    if ns.cmd == "scan-artifacts":
        from . import scan
        if ns.ids_only:
            ok, lines = scan.scan_ids(ns.repo)
        else:
            ok, lines = scan.scan_repo(ns.repo, against_archive=ns.against_archive)
        print("\n".join(lines))
        return EXIT_OK if ok else EXIT_CHECK_FAILED

    if ns.cmd == "results":
        from . import results_lint
        if ns.action == "lint":
            ok, lines = results_lint.lint_dir(ns.target)
            print("\n".join(lines))
            return EXIT_OK if ok else EXIT_CHECK_FAILED
        value = results_lint.get_key(ns.target, ns.keypath)
        print(value)
        return EXIT_OK

    if ns.cmd == "claims":
        from . import claims
        ok, lines = claims.verify(ledger_path=ns.ledger)
        print("\n".join(lines))
        print("CLAIMS OK" if ok else "CLAIMS FAIL")
        return EXIT_OK if ok else EXIT_CHECK_FAILED

    return EXIT_USAGE  # pragma: no cover


def main(argv=None):
    parser = build_parser()
    try:
        ns = parser.parse_args(argv)
    except SystemExit as e:
        return EXIT_USAGE if e.code not in (0, None) else EXIT_OK
    guard.install(_collect_roots(ns))
    try:
        rc = _dispatch(ns)
    except guard.GuardViolation as e:
        print(f"GUARD VIOLATION: {e}", file=sys.stderr)
        return EXIT_GUARD
    except BrokenPipeError:
        return EXIT_OK
    return rc


if __name__ == "__main__":
    sys.exit(main())
