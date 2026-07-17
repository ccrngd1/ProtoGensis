"""Calibration layer — the global allowlist / self-audit tuning (FR1.4, brief Q4).

Some patterns are genuinely legitimate in real agent configs and would otherwise
produce false Criticals: an n8n webhook URL in a HEARTBEAT file, a conditional
"if HEARTBEAT then..." check, PyTorch's ``--extra-index-url``. The brief requires
these register as INFO with an "attacker-could" note rather than Critical.

This runs after rules + pre-install checks. It never *creates* findings and
never *raises* severity — it only downgrades a known-legit finding to INFO and
attaches an explanatory note, so the self-audit stays honest ("this is fine now,
but here's what an attacker who could write this file would gain").

Downgrades are conservative and pattern-scoped so we don't mask real attacks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from setup_trap.model import Finding, Severity
from setup_trap.scanner.parsers.base import ParsedFile


@dataclass
class _CalibrationEntry:
    name: str
    # rule_ids this entry may downgrade (empty = any rule)
    rule_ids: tuple
    context_regex: re.Pattern
    note: str


# Ordered list; first matching entry wins.
_ENTRIES = [
    _CalibrationEntry(
        name="pytorch-extra-index",
        rule_ids=("TOOL-001", "PRE-SRC", "PRE-HIDDEN"),
        context_regex=re.compile(
            r"download\.pytorch\.org|data\.pyg\.org|pypi\.nvidia\.com|"
            r"developer\.download\.nvidia\.com",
            re.IGNORECASE,
        ),
        note="Recognized PyTorch/NVIDIA wheel index — legitimate. Attacker-could: "
        "swapping this host would silently redirect installs.",
    ),
    _CalibrationEntry(
        name="n8n-webhook",
        rule_ids=("EXFIL-001", "EXFIL-002", "EXFIL-005"),
        context_regex=re.compile(
            r"n8n|webhook|\.app\.n8n\.cloud|/webhook/", re.IGNORECASE
        ),
        note="Looks like an n8n automation webhook — legitimate integration in a "
        "HEARTBEAT/automation file. Attacker-could: repoint the webhook to an "
        "exfiltration endpoint.",
    ),
    _CalibrationEntry(
        name="heartbeat-conditional",
        rule_ids=("COND-001", "COND-005"),
        context_regex=re.compile(
            r"heartbeat|health\s*check|liveness|cron|schedule", re.IGNORECASE
        ),
        note="Conditional appears tied to a HEARTBEAT/health-check loop — normal "
        "operational logic. Attacker-could: attach a sensitive-keyword trigger to "
        "the same conditional.",
    ),
    _CalibrationEntry(
        name="sentry-telemetry",
        rule_ids=("EXFIL-002",),
        context_regex=re.compile(r"sentry\.io|sentry-sdk|ingest\.sentry", re.IGNORECASE),
        note="Recognized Sentry telemetry endpoint — legitimate error reporting. "
        "Attacker-could: piggyback additional data onto the telemetry payload.",
    ),
    _CalibrationEntry(
        # First-party service APIs a skill legitimately talks to. A curl/POST to
        # the vendor's own documented API host is the skill doing its job, not
        # exfiltration — downgrade to INFO with an attacker-could note.
        name="known-service-api",
        rule_ids=("EXFIL-001", "EXFIL-005"),
        context_regex=re.compile(
            r"api\.trello\.com|api\.notion\.com|slack\.com/api|api\.github\.com|"
            r"api\.openai\.com|api\.anthropic\.com|api\.telegram\.org|"
            r"api\.spotify\.com|graph\.microsoft\.com|googleapis\.com|"
            r"api\.twitter\.com|api\.x\.com|discord\.com/api|hooks\.slack\.com",
            re.IGNORECASE,
        ),
        note="Call to a first-party service API the skill integrates with — "
        "legitimate. Attacker-could: a modified skill could redirect the same "
        "call, or add fields, to exfiltrate via a look-alike host.",
    ),
    _CalibrationEntry(
        # Secret-manager / keychain CLIs (1Password `op`, macOS security) reading
        # a secret is the manager's purpose. The risk is real (a tampered skill
        # could read the wrong item and send it out) so we keep it visible — INFO.
        name="secret-manager-cli",
        rule_ids=("EXFIL-003", "MEM-004"),
        context_regex=re.compile(
            r"\bop://|\bop\s+read\b|\bop\s+item\b|1password|"
            r"security\s+find-(?:generic|internet)-password|keychain|"
            r"\bvault\s+(?:kv|read)\b|aws\s+secretsmanager",
            re.IGNORECASE,
        ),
        note="Secret-manager/keychain CLI access (e.g. 1Password `op`) — reading a "
        "secret is the manager's job. Attacker-could: a tampered skill could point "
        "the same CLI at a different item and forward it.",
    ),
    _CalibrationEntry(
        # A skill documenting a diagnostic curl to localhost (a debugger, a local
        # health endpoint) is not exfiltration.
        name="localhost-diagnostic",
        rule_ids=("EXFIL-005",),
        context_regex=re.compile(
            r"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])", re.IGNORECASE
        ),
        note="curl/wget targets localhost — a local diagnostic, not egress. "
        "Attacker-could: swap the localhost target for a remote host.",
    ),
]


# A directive is a PROHIBITION, not an instruction, when the line it sits on
# leads with a negation ("Never print secrets", "Do not ask for tokens"). Regex
# rules can't see this; the calibrator downgrades such matches to INFO. This is
# an honest limitation of static keyword matching, made explicit in the note.
_NEGATION_LINE = re.compile(
    r"^\s*[-*>#\d.)\s]*"
    r"(?:never|do\s*n['o]?t|don['o]?t|avoid|must\s+not|should\s+not|"
    r"you\s+(?:must|should|will)\s+not|no\s+need\s+to|refrain\s+from|"
    r"under\s+no\s+circumstances)\b",
    re.IGNORECASE,
)


class Calibrator:
    """Applies allowlist downgrades. Extensible: append entries or subclass."""

    def __init__(self, entries: list | None = None, *, enabled: bool = True):
        self.entries = entries if entries is not None else _ENTRIES
        self.enabled = enabled

    def apply(self, findings: list, parsed: ParsedFile) -> list:
        if not self.enabled:
            return findings
        for f in findings:
            if f.severity is Severity.INFO or f.note:
                continue
            # Negation guard first: a prohibition is the opposite of an attack.
            if self._is_negated(f):
                f.severity = Severity.INFO
                f.note = (
                    "The matched directive is phrased as a PROHIBITION (the line "
                    "leads with a negation like 'Never'/'Do not'). Regex matching "
                    "cannot read intent — treat as informational and confirm."
                )
                continue
            haystack = f"{f.context}\n{f.matched_text}"
            for entry in self.entries:
                if entry.rule_ids and f.rule_id not in entry.rule_ids:
                    continue
                if entry.context_regex.search(haystack):
                    f.severity = Severity.INFO
                    f.note = entry.note
                    break
        return findings

    @staticmethod
    def _is_negated(finding) -> bool:
        # Find the line within the context that carries the match, check its lead.
        match_head = finding.matched_text.splitlines()[0] if finding.matched_text else ""
        for line in finding.context.splitlines():
            if match_head and match_head[:30] in line:
                return bool(_NEGATION_LINE.match(line))
        return False
