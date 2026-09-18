"""honesty-gate CLI.

Commands:
  capture-hooks install [--settings PATH]   register Claude Code hooks
  capture-hooks status  [--settings PATH]   show hook registration + logs
  capture-hooks handle EVENT                (hook target; reads stdin JSON)
  run   --asked FILE (--transcript FILE | --session-log FILE)
        [--response FILE] [--llm-judge] [--judge-model M]
        [--threshold N] [--format terminal|md|json] [--root DIR]
  harness run (--transcript FILE | --session-log FILE) --response FILE
        [--format ...]                       score planted-defect detection
  harness list                               print the defect registry

Exit codes:
  0  honesty verdict PASS
  1  honesty gate failed (FALSE_CLAIM/SILENT_SKIP over threshold)
  2  capture/parse/tool error (bad inputs, unreadable files, ...)
"""

from __future__ import annotations

import argparse
import sys

from . import harness as harness_mod
from .capture import hooks as hooks_mod
from .capture import transcript as transcript_mod
from .classify import classify_run, gate
from .parse import claims as claims_mod
from .report import render

EXIT_PASS = 0
EXIT_GATE_FAILED = 1
EXIT_TOOL_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="honesty-gate",
                                description="Coverage-honesty gate for code-review agents.")
    sub = p.add_subparsers(dest="command", required=True)

    ch = sub.add_parser("capture-hooks", help="manage Claude Code capture hooks")
    chsub = ch.add_subparsers(dest="hooks_command", required=True)
    chi = chsub.add_parser("install", help="register hooks in Claude Code settings")
    chi.add_argument("--settings", default=None, help="settings JSON path")
    chs = chsub.add_parser("status", help="show hook registration and session logs")
    chs.add_argument("--settings", default=None)
    chh = chsub.add_parser("handle", help="(internal) hook handler, reads stdin")
    chh.add_argument("event", choices=hooks_mod.HOOK_EVENTS)

    run = sub.add_parser("run", help="classify a review session")
    _add_capture_args(run)
    run.add_argument("--asked", required=True,
                     help="file listing asked paths, one per line ('-' for stdin)")
    run.add_argument("--response", default=None,
                     help="file with the agent's final response text "
                          "(default: last assistant text in --transcript)")
    run.add_argument("--llm-judge", action="store_true",
                     help="also run the ADVISORY LLM claim judge")
    run.add_argument("--judge-model", default=None, help="litellm model id for the judge")
    run.add_argument("--threshold", type=int, default=0,
                     help="max gate-failing files tolerated (default 0)")
    run.add_argument("--format", default="terminal", choices=["terminal", "md", "json"])
    run.add_argument("--root", default=None, help="root for resolving relative paths")

    hn = sub.add_parser("harness", help="planted-defect harness")
    hnsub = hn.add_subparsers(dest="harness_command", required=True)
    hnr = hnsub.add_parser("run", help="score a review of the fixture set")
    _add_capture_args(hnr)
    hnr.add_argument("--response", required=True,
                     help="file with the agent's final response text")
    hnr.add_argument("--threshold", type=int, default=0)
    hnr.add_argument("--format", default="terminal", choices=["terminal", "md", "json"])
    hnsub.add_parser("list", help="print the defect registry")

    return p


def _add_capture_args(sp: argparse.ArgumentParser) -> None:
    grp = sp.add_mutually_exclusive_group(required=True)
    grp.add_argument("--transcript", default=None,
                     help="Claude Code session transcript JSONL to replay")
    grp.add_argument("--session-log", default=None,
                     help="honesty-gate hook session log JSONL")


def _read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as f:
        return f.read()


def _collect_accessed(args, root=None) -> set[str]:
    if args.transcript:
        return transcript_mod.collect_accessed(args.transcript, root)
    return hooks_mod.collect_accessed(args.session_log, root)


def _resolve_response(args) -> str:
    if args.response:
        return _read_text(args.response)
    if getattr(args, "transcript", None):
        return transcript_mod.final_response(args.transcript)
    raise ValueError("--response is required when using --session-log")


def cmd_capture_hooks(args) -> int:
    if args.hooks_command == "handle":
        return hooks_mod.run_handler(args.event)
    if args.hooks_command == "install":
        info = hooks_mod.install(args.settings)
        print(f"settings: {info['settings_path']}")
        print(f"installed: {info['installed'] or 'nothing (all present)'}")
        print(f"already present: {info['already_present']}")
        return EXIT_PASS
    info = hooks_mod.status(args.settings)
    print(f"settings: {info['settings_path']}")
    for event, ok in info["registered"].items():
        print(f"  {event}: {'registered' if ok else 'NOT registered'}")
    print(f"log dir: {info['log_dir']}")
    print(f"session logs: {len(info['sessions'])}")
    for s in info["sessions"]:
        print(f"  {s}")
    return EXIT_PASS


def cmd_run(args) -> int:
    asked = [ln.strip() for ln in _read_text(args.asked).splitlines() if ln.strip()]
    if not asked:
        raise ValueError("--asked produced an empty file list")
    accessed = _collect_accessed(args, args.root)
    response = _resolve_response(args)
    claim_result = claims_mod.parse(response, asked, llm_judge=args.llm_judge,
                                    model=args.judge_model, root=args.root)
    run = classify_run(asked, accessed, claim_result,
                       threshold=args.threshold, root=args.root)
    print(render(run, args.format))
    return gate(run)


def cmd_harness(args) -> int:
    if args.harness_command == "list":
        for d in harness_mod.load_registry():
            print(f"{d.id:<26} {d.file:<20} lines {d.lines[0]}-{d.lines[1]:<4} "
                  f"{d.cwe:<8} {d.bug_class}")
        return EXIT_PASS
    asked = harness_mod.fixture_paths()
    accessed = _collect_accessed(args)
    response = _read_text(args.response)
    claim_result = claims_mod.parse(response, asked)
    run = classify_run(asked, accessed, claim_result, threshold=args.threshold)
    score = harness_mod.score(run, response)
    print(render(run, args.format))
    print()
    print(harness_mod.render_score(score))
    return gate(run)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "capture-hooks":
            return cmd_capture_hooks(args)
        if args.command == "run":
            return cmd_run(args)
        if args.command == "harness":
            return cmd_harness(args)
        return EXIT_TOOL_ERROR
    except (OSError, ValueError, KeyError) as exc:
        print(f"honesty-gate error: {exc}", file=sys.stderr)
        return EXIT_TOOL_ERROR


if __name__ == "__main__":
    sys.exit(main())
