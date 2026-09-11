"""Verdict assembly and rendering.

The gate decision is purely deterministic: exit 1 iff any layer has status
"fail" (i.e. it produced at least one NEW blocking finding), exit 2 iff any
layer has status "error", else exit 0. Nothing else — not the advisory
finding count, not the heuristic risk tally — can change the exit code.

Output formats: terminal (default), json, md (for PR comments). All three
lead with the per-layer pass/fail table on new findings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from swe_gate.findings import LayerResult

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERROR = 2

_STATUS_ICON = {
    "pass": "PASS",
    "fail": "FAIL",
    "n/a": "n/a",
    "skipped": "SKIP",
    "unverifiable": "UNVERIFIABLE",
    "error": "ERROR",
}


@dataclass
class Verdict:
    layers: list[LayerResult]
    baseline: str
    repo: str
    notes: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        statuses = {lr.status for lr in self.layers}
        if "error" in statuses:
            return EXIT_ERROR
        if "fail" in statuses:
            return EXIT_FAIL
        return EXIT_PASS

    @property
    def blocking_count(self) -> int:
        return sum(len(lr.blocking) for lr in self.layers)

    @property
    def advisory_count(self) -> int:
        return sum(len(lr.advisory) for lr in self.layers)

    def advisory_risk_tally(self) -> int:
        """Count of advisory findings.

        ADVISORY ONLY. This is a plain count, not a probability and not a
        confidence measure. It never affects the gate decision or exit code.
        """
        return self.advisory_count

    # ------------------------------------------------------------------ #

    def render(self, fmt: str) -> str:
        if fmt == "json":
            return self._render_json()
        if fmt == "md":
            return self._render_md()
        return self._render_terminal()

    def _headline(self) -> str:
        if self.exit_code == EXIT_ERROR:
            return "SWE-GATE: ERROR (a scan failed — result unusable, exit 2)"
        if self.exit_code == EXIT_FAIL:
            return f"SWE-GATE: FAILED — {self.blocking_count} new blocking finding(s)"
        return "SWE-GATE: PASSED — no new blocking findings vs baseline"

    def _render_terminal(self) -> str:
        out = [self._headline(), f"baseline: {self.baseline[:12]}", ""]
        rows = [("layer", "name", "status", "new blocking", "detail")]
        for lr in self.layers:
            rows.append(
                (
                    f"L{lr.layer}",
                    lr.name,
                    _STATUS_ICON.get(lr.status, lr.status),
                    str(len(lr.blocking)),
                    lr.detail,
                )
            )
        widths = [max(len(r[i]) for r in rows) for i in range(4)]
        for i, r in enumerate(rows):
            line = "  ".join(r[j].ljust(widths[j]) for j in range(4)) + "  " + r[4]
            out.append(line)
            if i == 0:
                out.append("-" * (sum(widths) + 8 + len(rows[0][4])))
        out.append("")

        for lr in self.layers:
            for f in lr.blocking:
                loc = f"{f.file}:{f.line}" if f.line else f.file
                out.append(f"  BLOCKING [L{lr.layer}/{f.rule_id}] {loc}: {f.message}")
        for lr in self.layers:
            for f in lr.advisory:
                loc = f"{f.file}:{f.line}" if f.line else f.file
                out.append(f"  advisory [L{lr.layer}/{f.rule_id}] {loc}: {f.message}")

        if self.advisory_count:
            out.append("")
            out.append(
                f"advisory finding count: {self.advisory_risk_tally()} "
                "(advisory only — a plain count, not a probability; never gates)"
            )
        for note in self.notes:
            out.append(f"note: {note}")
        return "\n".join(out) + "\n"

    def _render_json(self) -> str:
        return json.dumps(
            {
                "verdict": ["pass", "fail", "error"][self.exit_code],
                "exit_code": self.exit_code,
                "baseline": self.baseline,
                "repo": self.repo,
                "layers": [lr.to_dict() for lr in self.layers],
                "blocking_count": self.blocking_count,
                "advisory_count": self.advisory_count,
                "advisory_note": (
                    "advisory_count is a plain count of non-blocking findings; "
                    "it is not a probability and never affects the gate"
                ),
                "notes": self.notes,
            },
            indent=2,
            sort_keys=True,
        ) + "\n"

    def _render_md(self) -> str:
        icon = {"pass": "✅", "fail": "❌", "n/a": "➖", "skipped": "⏭️",
                "unverifiable": "❓", "error": "💥"}
        out = [f"### {self._headline()}", "", f"baseline: `{self.baseline[:12]}`", ""]
        out.append("| layer | status | new blocking | detail |")
        out.append("|---|---|---|---|")
        for lr in self.layers:
            out.append(
                f"| L{lr.layer} {lr.name} | {icon.get(lr.status, '')} "
                f"{lr.status} | {len(lr.blocking)} | {lr.detail} |"
            )
        blocking = [(lr, f) for lr in self.layers for f in lr.blocking]
        advisory = [(lr, f) for lr in self.layers for f in lr.advisory]
        if blocking:
            out += ["", "**New blocking findings**", ""]
            for lr, f in blocking:
                loc = f"`{f.file}:{f.line}`" if f.line else f"`{f.file}`"
                out.append(f"- **L{lr.layer}/{f.rule_id}** {loc} — {f.message}")
        if advisory:
            out += ["", "<details><summary>Advisory findings "
                    "(never gate; plain count, not a probability)</summary>", ""]
            for lr, f in advisory:
                loc = f"`{f.file}:{f.line}`" if f.line else f"`{f.file}`"
                out.append(f"- L{lr.layer}/{f.rule_id} {loc} — {f.message}")
            out += ["", "</details>"]
        for note in self.notes:
            out.append(f"\n> {note}")
        return "\n".join(out) + "\n"
