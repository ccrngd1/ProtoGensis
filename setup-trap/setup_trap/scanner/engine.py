"""The detection engine (FR1).

Pipeline per file (matches the brief's scan pipeline):

    resolve file -> match file_patterns -> keyword pre-filter -> regex match
      -> allowlist check -> build Finding -> (calibration note) -> sort by severity

The engine also runs the paper's programmatic pre-install checks (see
``preinstall.py``) which need structured parser output (package lists, index
refs, Makefile targets) rather than a single regex.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

from setup_trap.model import Finding, Provenance, Rule, Severity
from setup_trap.scanner import preinstall
from setup_trap.scanner.calibration import Calibrator
from setup_trap.scanner.loader import load_rules
from setup_trap.scanner.parsers import ParsedFile, parse_file

# Files an init-time scan should never treat as agent config, to keep noise down.
_SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", ".mypy_cache",
    ".pytest_cache", "dist", "build", ".egg-info", "site-packages",
}
# Filenames the scanner considers "agent setup surface" when walking a directory.
_DEFAULT_TARGETS = (
    "*.md", "*.markdown", ".cursorrules", "requirements*.txt",
    "Makefile", "*.mk", "pyproject.toml",
)


@dataclass
class ScanResult:
    findings: list = field(default_factory=list)  # list[Finding]
    files_scanned: int = 0
    rules_loaded: int = 0
    notes: list = field(default_factory=list)  # non-fatal messages (skips, etc.)

    def by_severity(self) -> dict:
        out = {Severity.CRITICAL: [], Severity.WARNING: [], Severity.INFO: []}
        for f in self.findings:
            out[f.severity].append(f)
        return out

    def max_severity(self) -> Severity | None:
        return max((f.severity for f in self.findings), default=None)

    def exit_code(self, fail_on: Severity) -> int:
        """0 clean / below threshold, 1 when any finding >= fail_on (FR7.4)."""
        return 1 if any(f.severity >= fail_on for f in self.findings) else 0


class Engine:
    """Loads rules once, scans files or directories against them."""

    def __init__(
        self,
        rules: list | None = None,
        *,
        calibrator: Calibrator | None = None,
        check_cve: bool = False,
    ):
        self.rules: list[Rule] = rules if rules is not None else load_rules()
        self.calibrator = calibrator or Calibrator()
        self.check_cve = check_cve

    # -- file / directory resolution ---------------------------------------

    def _iter_files(self, path: Path):
        if path.is_file():
            yield path
            return
        for p in sorted(path.rglob("*")):
            if not p.is_file():
                continue
            # Only skip vendored/build dirs that appear BELOW the scan root — the
            # root's own ancestors (e.g. /usr/lib/node_modules/...) must not
            # exclude the target the user explicitly pointed us at.
            rel_parts = p.relative_to(path).parts
            if any(
                part in _SKIP_DIRS or part.endswith(".egg-info")
                for part in rel_parts
            ):
                continue
            name = p.name
            if any(fnmatch.fnmatch(name, pat) for pat in _DEFAULT_TARGETS):
                yield p

    @staticmethod
    def _rule_matches_file(rule: Rule, filename: str) -> bool:
        return any(
            fnmatch.fnmatch(filename, pat) or filename == pat
            for pat in rule.file_patterns
        )

    # -- core scan ----------------------------------------------------------

    def scan_file(self, path: Path) -> list:
        parsed = parse_file(path)
        findings: list[Finding] = []

        if parsed.parse_error:
            findings.append(
                Finding(
                    rule_id="PARSE-000",
                    rule_name="File parse warning",
                    category="engine",
                    severity=Severity.WARNING,
                    provenance=Provenance.INFERRED,
                    file=str(path),
                    line=1,
                    matched_text="",
                    context=parsed.parse_error,
                    message="File could not be fully parsed; scanned as raw text.",
                    fix_guidance="Verify the file is well-formed.",
                )
            )

        # 1) Regex/keyword rules.
        for rule in self.rules:
            if not self._rule_matches_file(rule, path.name):
                continue
            findings.extend(self._apply_rule(rule, parsed))

        # 2) Programmatic pre-install checks (paper's 7 checks).
        findings.extend(preinstall.run(parsed, check_cve=self.check_cve))

        # 3) Calibration: apply allowlist notes / severity downgrades for known
        #    legit patterns (n8n webhooks, HEARTBEAT conditionals, PyTorch index).
        findings = self.calibrator.apply(findings, parsed)
        return findings

    def _apply_rule(self, rule: Rule, parsed: ParsedFile) -> list:
        out: list[Finding] = []
        for seg in parsed.segments:
            if rule.target != "any" and seg.kind != rule.target:
                continue
            text = seg.text
            low = text.lower()
            # keyword pre-filter (FR1.3)
            if rule.keywords and not any(kw in low for kw in rule.keywords):
                continue
            for m in rule.regex.finditer(text):
                line = seg.start_line + text[: m.start()].count("\n")
                context = self._context(parsed, line, rule.context_lines)
                # allowlist check (FR1.4): suppress if rule- or global-allowlist
                # matches the surrounding context.
                if rule.allowlist and rule.allowlist.suppresses(context):
                    continue
                out.append(
                    Finding.from_rule(
                        rule,
                        file=str(parsed.path),
                        line=line,
                        matched_text=m.group(0).strip()[:200],
                        context=context,
                    )
                )
        return out

    @staticmethod
    def _context(parsed: ParsedFile, line: int, n: int) -> str:
        lines = parsed.lines
        lo = max(0, line - 1 - n)
        hi = min(len(lines), line + n)
        return "\n".join(lines[lo:hi])

    # -- directory scan -----------------------------------------------------

    def scan(self, path: Path) -> ScanResult:
        result = ScanResult(rules_loaded=len(self.rules))
        if not path.exists():
            result.notes.append(f"path does not exist: {path}")
            return result

        for f in self._iter_files(path):
            result.files_scanned += 1
            result.findings.extend(self.scan_file(f))

        # Sort by severity desc, then file, then line for stable reporting.
        result.findings.sort(key=lambda x: (-int(x.severity), x.file, x.line))
        return result


def scan_path(
    path: Path | str,
    *,
    category: str | None = None,
    severity: Severity | None = None,
    check_cve: bool = False,
    rules_dir: Path | None = None,
    calibrator: Calibrator | None = None,
) -> ScanResult:
    """Convenience entry: build an engine, optionally filter rules, scan."""

    from setup_trap.scanner.loader import load_rules as _load

    rules = _load(rules_dir) if rules_dir else _load()
    if category:
        rules = [r for r in rules if r.category == category]
    engine = Engine(rules, calibrator=calibrator, check_cve=check_cve)
    result = engine.scan(Path(path))
    if severity is not None:
        result.findings = [f for f in result.findings if f.severity >= severity]
    return result
