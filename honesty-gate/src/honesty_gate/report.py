"""Report card rendering: terminal, Markdown, and JSON.

Layout rules (enforced by tests):
- Lead element is the per-file coverage x claim x class table.
- Coverage % is reported separately from the honesty verdict; the two are
  never merged into one number.
- Exactly one honesty verdict per run (PASS/FAIL).
- Advisory LLM-judge output, when present, is clearly labeled ADVISORY.
- The bash-read blind spot is disclosed in every report.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from .classify import RunVerdict, GATE_FAILING

BLIND_SPOT_NOTE = (
    "Coverage capture sees file tools (Read/Edit) only. Files read via "
    "bash (cat, grep, less, head, ...) are NOT captured and may be "
    "undercounted as unopened. A future opt-in strace mode could close "
    "this gap."
)


def _short(path: str, maxlen: int = 44) -> str:
    return path if len(path) <= maxlen else "..." + path[-(maxlen - 3):]


def render_terminal(run: RunVerdict) -> str:
    lines = []
    lines.append("HonestyGate report")
    lines.append("=" * 78)
    header = f"{'file':<44} {'opened':<7} {'claim':<17} {'class':<12}"
    lines.append(header)
    lines.append("-" * 78)
    for fv in run.files:
        lines.append(
            f"{_short(fv.path):<44} {('yes' if fv.accessed else 'NO'):<7} "
            f"{fv.claim:<17} {fv.honesty_class:<12}"
        )
    lines.append("-" * 78)
    lines.append(f"Coverage: {run.coverage_pct}% of asked files opened "
                 f"({sum(1 for f in run.files if f.accessed)}/{len(run.files)})")
    counts = ", ".join(f"{k}={v}" for k, v in run.counts.items())
    lines.append(f"Classes:  {counts}")
    lines.append(f"Honesty verdict: {run.verdict} "
                 f"(gate-failing files: {len(run.failing_files)}, threshold: {run.threshold})")
    if run.failing_files:
        for p in run.failing_files:
            fv = next(f for f in run.files if f.path == p)
            lines.append(f"  ! {fv.honesty_class}: {p}")
            if fv.claim_evidence:
                lines.append(f'      response says: "{fv.claim_evidence.strip()}"')
    if run.aggregate_claim:
        lines.append("Note: response makes an aggregate claim covering all asked files.")
    if run.extra_accessed:
        lines.append(f"Also opened (not in asked set): {len(run.extra_accessed)} file(s)")
    lines.append("")
    lines.append(_advisory_text(run))
    lines.append(f"Blind spot: {BLIND_SPOT_NOTE}")
    return "\n".join(lines)


def render_markdown(run: RunVerdict) -> str:
    lines = []
    lines.append("## HonestyGate report")
    lines.append("")
    lines.append("| file | opened | claim | class |")
    lines.append("|---|---|---|---|")
    for fv in run.files:
        lines.append(f"| `{fv.path}` | {'yes' if fv.accessed else '**NO**'} "
                     f"| {fv.claim} | {fv.honesty_class} |")
    lines.append("")
    lines.append(f"**Coverage:** {run.coverage_pct}% of asked files opened")
    lines.append("")
    lines.append(f"**Honesty verdict:** {run.verdict} "
                 f"(gate-failing files: {len(run.failing_files)}, threshold: {run.threshold})")
    if run.failing_files:
        lines.append("")
        for p in run.failing_files:
            fv = next(f for f in run.files if f.path == p)
            lines.append(f"- **{fv.honesty_class}** — `{p}`" +
                         (f' — response says: "{fv.claim_evidence.strip()}"' if fv.claim_evidence else ""))
    lines.append("")
    lines.append(f"_{_advisory_text(run)}_")
    lines.append("")
    lines.append(f"> Blind spot: {BLIND_SPOT_NOTE}")
    return "\n".join(lines)


def render_json(run: RunVerdict) -> str:
    payload = {
        "files": [asdict(f) for f in run.files],
        "coverage_pct": run.coverage_pct,
        "counts": run.counts,
        "honesty_verdict": run.verdict,
        "failing_files": run.failing_files,
        "gate_failing_classes": list(GATE_FAILING),
        "threshold": run.threshold,
        "aggregate_claim": run.aggregate_claim,
        "extra_accessed": run.extra_accessed,
        "advisory_llm_judge": run.advisory,   # null unless --llm-judge succeeded
        "advisory_note": run.advisory_note,
        "blind_spot": BLIND_SPOT_NOTE,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _advisory_text(run: RunVerdict) -> str:
    if run.advisory:
        n = len(run.advisory.get("files", {}))
        disagreements = _advisory_disagreements(run)
        base = (f"ADVISORY (LLM judge, {run.advisory.get('model')}): labeled {n} file(s); "
                "advisory labels never change the deterministic verdict.")
        if disagreements:
            base += " Differs from deterministic tier on: " + ", ".join(disagreements)
        return base
    if run.advisory_note:
        return f"ADVISORY (LLM judge): not available — {run.advisory_note}"
    return "ADVISORY (LLM judge): disabled (--llm-judge to enable)."


def _advisory_disagreements(run: RunVerdict) -> list[str]:
    out = []
    files = (run.advisory or {}).get("files", {})
    for fv in run.files:
        adv = files.get(fv.path)
        if adv and adv.get("label") != fv.claim:
            out.append(f"{fv.path} (advisory={adv['label']}, deterministic={fv.claim})")
    return out


RENDERERS = {
    "terminal": render_terminal,
    "md": render_markdown,
    "markdown": render_markdown,
    "json": render_json,
}


def render(run: RunVerdict, fmt: str = "terminal") -> str:
    try:
        return RENDERERS[fmt](run)
    except KeyError:
        raise ValueError(f"unknown format: {fmt!r} (choose terminal|md|json)") from None
