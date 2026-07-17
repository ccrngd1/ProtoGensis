"""Load and validate YAML rules into :class:`Rule` objects.

Rules ship as YAML under ``scanner/rules/`` (FR1.1/FR1.6): adding a rule is a
YAML edit, no code change. This module compiles regexes/allowlists once at load
time and validates the schema, so a malformed rule fails loudly at startup
rather than silently not firing.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from setup_trap.model import Allowlist, Provenance, Rule, Severity

RULES_DIR = Path(__file__).parent / "rules"

_REQUIRED = ("id", "name", "category", "severity", "provenance", "regex", "message")


class RuleLoadError(ValueError):
    """Raised when a rule file is malformed — surfaced at startup, not scan time."""


def _compile(pattern: str, rule_id: str, field: str) -> re.Pattern:
    try:
        return re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    except re.error as exc:
        raise RuleLoadError(f"rule {rule_id}: bad regex in {field}: {exc}") from exc


def _build_rule(doc: dict, source_file: Path) -> Rule:
    missing = [k for k in _REQUIRED if k not in doc or doc[k] in (None, "")]
    if missing:
        raise RuleLoadError(
            f"{source_file.name}: rule {doc.get('id', '<no id>')} "
            f"missing required fields: {missing}"
        )

    rule_id = str(doc["id"])
    allowlist = None
    al = doc.get("allowlist")
    if al:
        regexes = tuple(
            _compile(p, rule_id, "allowlist") for p in al.get("regexes", [])
        )
        allowlist = Allowlist(
            description=al.get("description", ""), regexes=regexes
        )

    try:
        severity = Severity.from_str(doc["severity"])
        provenance = Provenance.from_str(doc["provenance"])
    except ValueError as exc:
        raise RuleLoadError(f"rule {rule_id}: {exc}") from exc

    target = doc.get("target", "any")
    if target not in ("any", "prose", "code"):
        raise RuleLoadError(
            f"rule {rule_id}: target must be any|prose|code, got {target!r}"
        )

    try:
        return Rule(
            id=rule_id,
            name=str(doc["name"]),
            category=str(doc["category"]),
            severity=severity,
            provenance=provenance,
            description=str(doc.get("description", "")),
            file_patterns=list(doc.get("file_patterns", ["*"])),
            regex=_compile(str(doc["regex"]), rule_id, "regex"),
            message=str(doc["message"]),
            fix_guidance=str(doc.get("fix_guidance", "")),
            keywords=[str(k).lower() for k in doc.get("keywords", [])],
            context_lines=int(doc.get("context_lines", 2)),
            allowlist=allowlist,
            tags=list(doc.get("tags", [])),
            source_ref=doc.get("source_ref"),
            target=target,
        )
    except ValueError as exc:  # e.g. sourced-without-source_ref from __post_init__
        raise RuleLoadError(str(exc)) from exc


def load_rules(rules_dir: Path | None = None) -> list[Rule]:
    """Load all rules from every ``*.yml`` under the rules directory.

    Each YAML file holds a top-level ``rules:`` list. Duplicate rule IDs are an
    error (a copy-paste mistake would otherwise silently shadow a rule).
    """

    rules_dir = rules_dir or RULES_DIR
    rules: list[Rule] = []
    seen: dict[str, str] = {}

    for path in sorted(rules_dir.glob("*.yml")):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise RuleLoadError(f"{path.name}: invalid YAML: {exc}") from exc

        for rule_doc in doc.get("rules", []):
            rule = _build_rule(rule_doc, path)
            if rule.id in seen:
                raise RuleLoadError(
                    f"duplicate rule id {rule.id!r} in {path.name} "
                    f"(already defined in {seen[rule.id]})"
                )
            seen[rule.id] = path.name
            rules.append(rule)

    if not rules:
        raise RuleLoadError(f"no rules found under {rules_dir}")
    return rules
