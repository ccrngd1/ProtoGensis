"""Coherence report, computed only from the JSONL run log (AC #11).

Covers reads by key@version, proposals, accepts, repairs, rejects by reason,
notices emitted/acted-on, invariant headroom over time, and a
violations_prevented count. Formats: terminal, Markdown, --json with stable
key order.
"""
from __future__ import annotations

import json


def summarize(events: list[dict]) -> dict:
    """Reduce a run-log event list to the report dict. Log-only, by design."""
    reads: dict[str, int] = {}
    rejects_by_reason: dict[str, int] = {}
    headroom_series: list[dict] = []
    counts = {"proposals": 0, "accepts": 0, "repairs": 0, "rejects": 0,
              "draws": 0, "notices": 0, "notices_acted_on": 0, "env_changes": 0}
    violations_prevented = 0
    would_be_violations = 0
    unseen_premises: list[str] = []
    lint_findings: list[dict] = []
    draw_totals: dict[str, int] = {}

    for ev in events:
        kind = ev.get("kind")
        payload = ev.get("payload", {})
        if kind == "read":
            for key, ver in payload.get("read_set", {}).items():
                reads[f"{key}@v{ver}"] = reads.get(f"{key}@v{ver}", 0) + 1
        elif kind == "propose":
            counts["proposals"] += 1
            for key, ver in payload.get("read_set", {}).items():
                reads[f"{key}@v{ver}"] = reads.get(f"{key}@v{ver}", 0) + 1
            unseen_premises.extend(payload.get("unseen_premises", []))
        elif kind == "accept":
            counts["accepts"] += 1
        elif kind == "repair":
            counts["repairs"] += 1
        elif kind == "reject":
            counts["rejects"] += 1
            reason = payload.get("reason", "unknown")
            rejects_by_reason[reason] = rejects_by_reason.get(reason, 0) + 1
            if "headroom" in payload:
                headroom_series.append({"seq": ev.get("seq"),
                                        "headroom": payload["headroom"]})
            if reason == "invariant":
                if payload.get("observed_only"):
                    would_be_violations += 1
                else:
                    violations_prevented += 1
        elif kind == "draw":
            counts["draws"] += 1
            resource = payload.get("resource", "")
            draw_totals[resource] = draw_totals.get(resource, 0) + payload.get("amount", 0)
        elif kind == "notice":
            counts["notices"] += 1
            if payload.get("acted_on"):
                counts["notices_acted_on"] += 1
        elif kind == "env_change":
            counts["env_changes"] += 1
        elif kind == "lint":
            lint_findings.append(dict(sorted(payload.items())))

    return {
        "counts": counts,
        "draw_totals": dict(sorted(draw_totals.items())),
        "headroom_series": headroom_series,
        "lint_findings": lint_findings,
        "reads_by_key_version": dict(sorted(reads.items())),
        "rejects_by_reason": dict(sorted(rejects_by_reason.items())),
        "unseen_premises": sorted(set(unseen_premises)),
        "violations_prevented": violations_prevented,
        "would_be_violations": would_be_violations,
    }


def to_json(report: dict) -> str:
    return json.dumps(report, sort_keys=True, indent=2)


def to_markdown(report: dict) -> str:
    lines = ["# Coherence report", "", "## Counts", "",
             "| metric | value |", "|---|---|"]
    for key, value in sorted(report["counts"].items()):
        lines.append(f"| {key} | {value} |")
    lines += ["", "## Rejects by reason", ""]
    if report["rejects_by_reason"]:
        lines += ["| reason | count |", "|---|---|"]
        lines += [f"| {r} | {c} |" for r, c in report["rejects_by_reason"].items()]
    else:
        lines.append("(none)")
    lines += ["", f"**Violations prevented:** {report['violations_prevented']}", ""]
    if report["reads_by_key_version"]:
        lines += ["## Reads by key@version", ""]
        lines += [f"- `{kv}`: {n}" for kv, n in report["reads_by_key_version"].items()]
    if report["unseen_premises"]:
        lines += ["", "## Unseen premises (cited but never shown)", ""]
        lines += [f"- `{k}`" for k in report["unseen_premises"]]
    if report["lint_findings"]:
        lines += ["", "## Lint findings", ""]
        lines += [f"- {json.dumps(f, sort_keys=True)}" for f in report["lint_findings"]]
    return "\n".join(lines)


def to_terminal(report: dict) -> str:
    lines = ["coherence report"]
    for key, value in sorted(report["counts"].items()):
        lines.append(f"  {key:18s} {value}")
    if report["rejects_by_reason"]:
        lines.append("  rejects by reason:")
        for reason, count in report["rejects_by_reason"].items():
            lines.append(f"    {reason:16s} {count}")
    lines.append(f"  violations_prevented {report['violations_prevented']}")
    if report["unseen_premises"]:
        lines.append(f"  unseen_premises    {', '.join(report['unseen_premises'])}")
    return "\n".join(lines)


def render(report: dict, fmt: str) -> str:
    if fmt == "json":
        return to_json(report)
    if fmt == "md":
        return to_markdown(report)
    return to_terminal(report)
