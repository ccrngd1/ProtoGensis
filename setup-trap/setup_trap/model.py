"""Core data model: severities, provenance, rules, and findings.

These types are shared across the engine, reporters, and simulator so that the
provenance honesty gate is enforced structurally: a Finding cannot exist without
a provenance tag inherited from its Rule.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional


class Severity(enum.IntEnum):
    """Finding severity. IntEnum so we can compare/sort and threshold on it."""

    INFO = 1
    WARNING = 2
    CRITICAL = 3

    @classmethod
    def from_str(cls, value: str) -> "Severity":
        try:
            return cls[value.strip().upper()]
        except KeyError as exc:
            raise ValueError(
                f"unknown severity {value!r}; expected one of "
                f"{[s.name.lower() for s in cls]}"
            ) from exc

    @property
    def label(self) -> str:
        return self.name.capitalize()


class Provenance(enum.Enum):
    """Where a rule's authority comes from — the honesty gate.

    SOURCED      empirically evaluated by arXiv:2607.15143 (package-install class)
    SYNTHESIZED  grounded in prompt-injection literature, NOT paper-proven
    INFERRED     reasonable deduction (e.g. undocumented runtime read-order)
    """

    SOURCED = "sourced"
    SYNTHESIZED = "synthesized"
    INFERRED = "inferred"

    @classmethod
    def from_str(cls, value: str) -> "Provenance":
        try:
            return cls(value.strip().lower())
        except ValueError as exc:
            raise ValueError(
                f"unknown provenance {value!r}; expected one of "
                f"{[p.value for p in cls]}"
            ) from exc

    @property
    def badge(self) -> str:
        return {
            Provenance.SOURCED: "🟢 sourced",
            Provenance.SYNTHESIZED: "🟡 synthesized",
            Provenance.INFERRED: "🔵 inferred",
        }[self]

    @property
    def short_badge(self) -> str:
        return {
            Provenance.SOURCED: "🟢",
            Provenance.SYNTHESIZED: "🟡",
            Provenance.INFERRED: "🔵",
        }[self]


@dataclass(frozen=True)
class Allowlist:
    """Compiled allowlist: a match is suppressed if any regex hits its context."""

    description: str
    regexes: tuple  # tuple[re.Pattern]

    def suppresses(self, text: str) -> bool:
        return any(pat.search(text) for pat in self.regexes)


@dataclass
class Rule:
    """A single detection rule loaded from YAML.

    A rule runs only against files matching ``file_patterns``. For performance
    the ``keywords`` pre-filter runs before the (compiled) ``regex``. A match is
    dropped if the rule-level or global allowlist suppresses it.
    """

    id: str
    name: str
    category: str
    severity: Severity
    provenance: Provenance
    description: str
    file_patterns: list  # list[str] globs / exact names
    regex: object  # re.Pattern
    message: str
    fix_guidance: str
    keywords: list = field(default_factory=list)
    context_lines: int = 2
    allowlist: Optional[Allowlist] = None
    tags: list = field(default_factory=list)
    source_ref: Optional[str] = None
    target: str = "any"  # any | prose | code — markdown-only refinement

    def __post_init__(self) -> None:
        # SOURCED rules must cite where they come from — the honesty gate has
        # teeth: a rule claiming paper authority without a source_ref is a bug.
        if self.provenance is Provenance.SOURCED and not self.source_ref:
            raise ValueError(
                f"rule {self.id}: provenance 'sourced' requires a source_ref"
            )


@dataclass
class Finding:
    """A single hit produced by a rule against a file."""

    rule_id: str
    rule_name: str
    category: str
    severity: Severity
    provenance: Provenance
    file: str
    line: int
    matched_text: str
    context: str
    message: str
    fix_guidance: str
    source_ref: Optional[str] = None
    tags: list = field(default_factory=list)
    # Optional advisory note attached by the self-audit calibration layer, e.g.
    # "legit n8n webhook — attacker could swap the host". Never overrides
    # severity; it explains why a match is INFO rather than Critical.
    note: Optional[str] = None

    @classmethod
    def from_rule(
        cls,
        rule: Rule,
        *,
        file: str,
        line: int,
        matched_text: str,
        context: str,
        note: Optional[str] = None,
    ) -> "Finding":
        return cls(
            rule_id=rule.id,
            rule_name=rule.name,
            category=rule.category,
            severity=rule.severity,
            provenance=rule.provenance,
            file=file,
            line=line,
            matched_text=matched_text,
            context=context,
            message=rule.message,
            fix_guidance=rule.fix_guidance,
            source_ref=rule.source_ref,
            tags=list(rule.tags),
            note=note,
        )

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "category": self.category,
            "severity": self.severity.name.lower(),
            "provenance": self.provenance.value,
            "file": self.file,
            "line": self.line,
            "matched_text": self.matched_text,
            "context": self.context,
            "message": self.message,
            "fix_guidance": self.fix_guidance,
            "source_ref": self.source_ref,
            "tags": self.tags,
            "note": self.note,
        }
