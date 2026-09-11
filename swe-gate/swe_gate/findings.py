"""Core data model shared by all layers.

The gate decision is a pure function of blocking findings: advisory findings
and any derived heuristic never influence layer status or exit code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

LAYER_NAMES = {
    0: "test tampering",
    1: "import hallucination",
    2: "signature mismatch",
    3: "security patterns",
}

# Layer statuses:
#   pass          — layer ran, no new blocking findings
#   fail          — layer ran, at least one new blocking finding
#   n/a           — nothing in scope for this layer (e.g. no Python in changeset)
#   skipped       — layer deselected via --layers, or required tool not installed
#   unverifiable  — layer ran but could not fully verify (e.g. missing type stubs)
#   error         — tool/scan error; maps to exit code 2
PASSING_STATUSES = {"pass", "n/a", "skipped", "unverifiable"}


@dataclass
class Finding:
    layer: int
    rule_id: str
    message: str
    file: str = ""
    line: int | None = None
    blocking: bool = False
    tool: str = "swe-gate"

    def sort_key(self) -> tuple:
        return (self.layer, self.file, self.line or 0, self.rule_id, self.message)

    def to_dict(self) -> dict:
        return {
            "layer": self.layer,
            "rule_id": self.rule_id,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "blocking": self.blocking,
            "tool": self.tool,
        }


@dataclass
class LayerResult:
    layer: int
    status: str
    findings: list[Finding] = field(default_factory=list)
    detail: str = ""

    @property
    def name(self) -> str:
        return LAYER_NAMES.get(self.layer, f"layer {self.layer}")

    @property
    def blocking(self) -> list[Finding]:
        return sorted((f for f in self.findings if f.blocking), key=Finding.sort_key)

    @property
    def advisory(self) -> list[Finding]:
        return sorted((f for f in self.findings if not f.blocking), key=Finding.sort_key)

    def finalize(self) -> "LayerResult":
        """Derive pass/fail from blocking findings when the layer actually ran."""
        if self.status in ("", "ran"):
            self.status = "fail" if self.blocking else "pass"
        self.findings.sort(key=Finding.sort_key)
        return self

    def to_dict(self) -> dict:
        return {
            "layer": self.layer,
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "blocking_findings": [f.to_dict() for f in self.blocking],
            "advisory_findings": [f.to_dict() for f in self.advisory],
        }
