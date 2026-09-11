"""swe-gate CLI.

    swe-gate run [--baseline <git-ref>] [--format terminal|json|md]
                 [--check-pypi] [--layers 0,1,2,3] [PATH]

Exit codes: 0 = pass, 1 = gate failed (new blocking findings), 2 = tool error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from swe_gate.findings import LayerResult
from swe_gate.gitdiff import GitError, collect_changeset
from swe_gate.layers import imports, security, signatures, tampering
from swe_gate.verdict import EXIT_ERROR, Verdict

ALL_LAYERS = (0, 1, 2, 3)


def _parse_layers(spec: str) -> tuple[int, ...]:
    try:
        chosen = tuple(sorted({int(p) for p in spec.split(",") if p.strip() != ""}))
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid --layers value: {spec!r}")
    bad = [l for l in chosen if l not in ALL_LAYERS]
    if bad or not chosen:
        raise argparse.ArgumentTypeError(
            f"--layers accepts a comma-separated subset of 0,1,2,3 (got {spec!r})"
        )
    return chosen


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="swe-gate",
        description=(
            "Post-test-pass deterministic verification gate for AI-specific "
            "coding defects. Run it after your test suite passes."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="run the gate against a repository")
    run_p.add_argument("path", nargs="?", default=".", help="path inside the target repo")
    run_p.add_argument("--baseline", default=None, help="git ref to diff against "
                       "(default: merge-base with the default branch)")
    run_p.add_argument("--format", choices=("terminal", "json", "md"),
                       default="terminal", dest="fmt")
    run_p.add_argument("--check-pypi", action="store_true",
                       help="verify unresolved imports against the PyPI JSON API "
                            "(opt-in; the offline default labels them 'unverified')")
    run_p.add_argument("--layers", type=_parse_layers, default=ALL_LAYERS,
                       help="comma-separated subset of layers to run (default 0,1,2,3)")
    return parser


def run_gate(
    path: str,
    baseline: str | None = None,
    layers: tuple[int, ...] = ALL_LAYERS,
    check_pypi: bool = False,
) -> Verdict:
    changeset = collect_changeset(Path(path).resolve(), baseline)

    runners = {
        0: lambda: tampering.run(changeset),
        1: lambda: imports.run(changeset, use_pypi=check_pypi),
        2: lambda: signatures.run(changeset),
        3: lambda: security.run(changeset),
    }
    results: list[LayerResult] = []
    for layer in ALL_LAYERS:
        if layer in layers:
            results.append(runners[layer]())
        else:
            results.append(
                LayerResult(layer=layer, status="skipped", detail="deselected via --layers")
            )

    notes = []
    if not changeset.python_files:
        notes.append("no Python files in changeset — all layers n/a, gate passes")
    return Verdict(
        layers=results,
        baseline=changeset.baseline,
        repo=str(changeset.repo),
        notes=notes,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        verdict = run_gate(
            args.path,
            baseline=args.baseline,
            layers=args.layers,
            check_pypi=args.check_pypi,
        )
    except GitError as exc:
        print(f"swe-gate: git error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(verdict.render(args.fmt), end="")
    return verdict.exit_code


if __name__ == "__main__":
    sys.exit(main())
