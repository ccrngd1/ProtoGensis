"""The paper's 7 pre-install checks (arXiv:2607.15143 — the SOURCED core).

These are the package-install supply-chain checks the paper empirically
evaluated. They need structured parser output (package lists, index refs,
Makefile targets), so they are implemented programmatically rather than as
single-regex YAML rules — but they carry the same Finding schema and provenance.

Every check cites its paper scenario reference (R#/V#). CVE lookup (check 6) is
the one network-optional piece: it shells out to ``pip-audit`` only when the
caller passes ``check_cve=True`` and the tool is installed, and degrades to a
Warning-level "pinned version, not verified" note otherwise (FR3.8).

Paper scenario mapping (from the build brief, FR3):
  R-name   typosquat name check
  R-sep    separator confusion (azurecore <-> azure-core)
  R6a      source redirection: --index-url/--extra-index-url off PyPI / localhost
  R8       hidden index URL on its own line in requirements.txt
  R10      Makefile poisoning: install target with custom pip source
  V5       CVE-pinned version
  V7       error-message injection ("on error run pip install <x>")
"""

from __future__ import annotations

import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from setup_trap.model import Finding, Provenance, Severity
from setup_trap.scanner.parsers.base import ParsedFile

SOURCE_REF = "arXiv:2607.15143"

_DATA = Path(__file__).parent / "data" / "popular_packages.txt"

# Hosts that are legitimate PyPI / well-known mirrors — not a redirection.
_TRUSTED_INDEX_HOSTS = (
    "pypi.org",
    "pypi.python.org",
    "files.pythonhosted.org",
)
# Well-known legitimate alternate indexes (allowlisted, INFO not Critical).
_KNOWN_ALT_INDEX = re.compile(
    r"download\.pytorch\.org|"
    r"data\.pyg\.org|"
    r"pypi\.nvidia\.com|"
    r"developer\.download\.nvidia\.com|"
    r"\.pkg\.dev/|"  # Google Artifact Registry
    r"\.jfrog\.io|"
    r"pkgs\.dev\.azure\.com",
    re.IGNORECASE,
)
_PRIVATE_HOST = re.compile(
    r"^(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|"
    r"10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)",
    re.IGNORECASE,
)
# README/setup text telling the agent to install something when a command errors.
_ERROR_INJECT = re.compile(
    r"(?:if|when|should|on).{0,40}(?:error|fail|not found|missing|importerror|"
    r"modulenotfounderror).{0,60}(?:pip\s+install|pip3\s+install|"
    r"install\s+[\w.-]+)",
    re.IGNORECASE | re.DOTALL,
)


@lru_cache(maxsize=1)
def _popular() -> set:
    names = set()
    for line in _DATA.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            names.add(_normalize(line))
    return names


def _normalize(name: str) -> str:
    """PEP 503 normalization: lower-case, collapse runs of - _ . to a single -."""
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def _host(url: str) -> str:
    m = re.match(r"[a-z]+://([^/:]+)", url, re.IGNORECASE)
    return (m.group(1) if m else url).lower()


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(
                min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            )
        prev = cur
    return prev[-1]


def _finding(
    rule_id, name, severity, provenance, parsed, line, matched, message, fix, ref,
    note=None,
) -> Finding:
    lines = parsed.raw.splitlines()
    lo, hi = max(0, line - 3), min(len(lines), line + 2)
    return Finding(
        rule_id=rule_id,
        rule_name=name,
        category="tool-binding",
        severity=severity,
        provenance=provenance,
        file=str(parsed.path),
        line=line,
        matched_text=str(matched)[:200],
        context="\n".join(lines[lo:hi]),
        message=message,
        fix_guidance=fix,
        source_ref=ref,
        tags=["pre-install", "supply-chain"],
        note=note,
    )


# -- check 1 & 2: name typosquat + separator confusion ---------------------


def _check_names(parsed: ParsedFile) -> list:
    out = []
    popular = _popular()
    for pkg in parsed.packages:
        norm = _normalize(pkg.name)
        if norm in popular:
            continue
        # Separator confusion: normalized form collides with a known package
        # but the raw spelling differs only by - _ . grouping (R-sep — the
        # paper's hardest-to-catch class).
        raw_norm = pkg.name.strip().lower()
        for good in popular:
            good_collapsed = good.replace("-", "")
            if raw_norm.replace("-", "").replace("_", "").replace(".", "") == good_collapsed \
                    and raw_norm != good:
                out.append(_finding(
                    "PRE-SEP", "Separator-confusion package name", Severity.CRITICAL,
                    Provenance.SOURCED, parsed, pkg.line, pkg.raw,
                    f"Package '{pkg.name}' matches known package '{good}' but for "
                    f"separator/case differences — a separator-confusion typosquat.",
                    f"Confirm the intended package is '{good}' and pin the exact "
                    f"canonical name.",
                    f"{SOURCE_REF} R-sep",
                ))
                break
        else:
            # Typosquat: within edit distance 1 of a popular name (R-name).
            near = [
                g for g in popular
                if abs(len(g) - len(norm)) <= 1 and _levenshtein(norm, g) == 1
            ]
            if near:
                out.append(_finding(
                    "PRE-NAME", "Typosquat package name", Severity.CRITICAL,
                    Provenance.SOURCED, parsed, pkg.line, pkg.raw,
                    f"Package '{pkg.name}' is one edit away from popular package(s) "
                    f"{sorted(near)} — a likely typosquat.",
                    f"Verify the intended package name; did you mean {sorted(near)[0]!r}?",
                    f"{SOURCE_REF} R-name",
                ))
    return out


# -- check 3 & 4: source redirection + hidden index ------------------------


def _check_index(parsed: ParsedFile) -> list:
    out = []
    for ref in parsed.index_urls:
        host = _host(ref.url)
        if any(host == h or host.endswith("." + h) for h in _TRUSTED_INDEX_HOSTS):
            continue

        is_private = bool(_PRIVATE_HOST.match(host))
        is_known_alt = bool(_KNOWN_ALT_INDEX.search(ref.url))

        attacker_note = None
        if is_private:
            sev, prov, msg = Severity.CRITICAL, Provenance.SOURCED, (
                "Index URL points at localhost/private network — classic "
                "dependency-confusion redirection.")
        elif is_known_alt:
            # Legit alternate index (PyTorch CUDA wheels, cloud artifact repos).
            sev, prov, msg = Severity.INFO, Provenance.SOURCED, (
                "Alternate index recognized as a common legitimate source.")
            attacker_note = (
                "Recognized as a common legitimate index; verify it is the one you "
                "intend — an attacker could swap the host.")
        else:
            sev, prov, msg = Severity.CRITICAL, Provenance.SOURCED, (
                "Install source redirected to a non-PyPI host — anything served "
                "there is installed with full trust.")

        f = _finding(
            "PRE-SRC", f"Non-PyPI install source ({ref.kind})", sev, prov,
            parsed, ref.line, ref.raw, msg,
            "Remove the custom index or pin it to a source you control and trust; "
            "prefer hash-pinned dependencies.",
            f"{SOURCE_REF} R6a",
            note=attacker_note,
        )
        out.append(f)

        # Hidden index: an index flag on its own line inside requirements.txt
        # (R8) — easy to miss in review, applies to the whole file.
        if parsed.path.name.lower().startswith("requirements") and \
                ref.raw.strip().lower().startswith("--"):
            out.append(_finding(
                "PRE-HIDDEN", "Hidden index URL in requirements.txt", Severity.WARNING,
                Provenance.SOURCED, parsed, ref.line, ref.raw,
                "Index URL declared inside requirements.txt (not on the pip CLI); "
                "it silently redirects every install using this file.",
                "Move index configuration to an auditable, reviewed location and "
                "verify the host.",
                f"{SOURCE_REF} R8",
            ))
    return out


# -- check 5: Makefile poisoning -------------------------------------------

_PIP_SRC_FLAG = re.compile(
    r"\bpip3?\b.*\binstall\b.*(--(?:extra-)?index-url|--find-links|-i\s)",
    re.IGNORECASE,
)


def _check_makefile(parsed: ParsedFile) -> list:
    out = []
    for target in parsed.make_targets:
        for line, cmd in target.commands:
            if _PIP_SRC_FLAG.search(cmd):
                out.append(_finding(
                    "PRE-MAKE", "Makefile target with custom pip source",
                    Severity.CRITICAL, Provenance.SOURCED, parsed, line, cmd,
                    f"Make target '{target.name}' runs pip install with a custom "
                    f"source flag — an install redirection hidden in build tooling.",
                    "Audit the index/find-links host; pin dependencies to a trusted "
                    "source and remove custom flags from build targets.",
                    f"{SOURCE_REF} R10",
                ))
    return out


# -- check 6: CVE-pinned version (optional pip-audit) ----------------------

_PINNED = re.compile(r"^==\s*([0-9][\w.+!-]*)$")


def _check_cve(parsed: ParsedFile, enabled: bool) -> list:
    out = []
    pinned = [
        p for p in parsed.packages
        if p.version_spec and _PINNED.match(p.version_spec.replace(" ", ""))
    ]
    if not pinned:
        return out

    audited = _run_pip_audit(parsed.path) if enabled else None

    for p in pinned:
        version = _PINNED.match(p.version_spec.replace(" ", "")).group(1)
        vuln = None
        if audited is not None:
            vuln = audited.get((_normalize(p.name), version))
        if vuln:
            out.append(_finding(
                "PRE-CVE", "Pinned version with known CVE", Severity.CRITICAL,
                Provenance.SOURCED, parsed, p.line, p.raw,
                f"'{p.name}=={version}' has known vulnerabilit(ies): "
                f"{', '.join(vuln)}. Pinning to a CVE-bearing version is the "
                f"paper's V5 attack.",
                f"Upgrade '{p.name}' to a patched release.",
                f"{SOURCE_REF} V5",
            ))
        else:
            note = (
                "Exact pin; no CVE found by pip-audit." if enabled and audited is not None
                else "Exact pin; CVE status NOT verified (run with --check-cve and "
                     "pip-audit installed to confirm)."
            )
            out.append(_finding(
                "PRE-PIN", "Exact-pinned dependency version", Severity.INFO,
                Provenance.SOURCED, parsed, p.line, p.raw,
                f"'{p.name}=={version}' is pinned. {note}",
                "Verify the pinned version is patched; the paper (V5) shows attackers "
                "pin to a version with a known exploit.",
                f"{SOURCE_REF} V5",
            ))
    return out


def _run_pip_audit(path: Path) -> dict | None:
    """Return {(normalized_name, version): [vuln_ids]} or None if unavailable."""
    if shutil.which("pip-audit") is None:
        return None
    try:
        proc = subprocess.run(
            ["pip-audit", "-r", str(path), "-f", "json", "--progress-spinner", "off"],
            capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    import json
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return None
    result: dict = {}
    deps = data.get("dependencies", data if isinstance(data, list) else [])
    for dep in deps:
        vulns = [v.get("id", "?") for v in dep.get("vulns", [])]
        if vulns:
            result[(_normalize(dep.get("name", "")), dep.get("version", ""))] = vulns
    return result


# -- check 7: error-message injection --------------------------------------


def _check_error_injection(parsed: ParsedFile) -> list:
    out = []
    # Only meaningful in prose/setup text (markdown), not dependency files.
    if parsed.path.suffix.lower() not in (".md", ".markdown", ""):
        return out
    for seg in parsed.segments:
        for m in _ERROR_INJECT.finditer(seg.text):
            line = seg.start_line + seg.text[: m.start()].count("\n")
            out.append(_finding(
                "PRE-ERRINJ", "Error-triggered install instruction", Severity.WARNING,
                Provenance.SOURCED, parsed, line, m.group(0),
                "Setup text instructs installing a package when a command errors — "
                "the paper's V7 error-message-injection vector (attacker supplies a "
                "malicious package to install 'to fix' the error).",
                "Never auto-install packages in response to errors; resolve "
                "dependencies explicitly and pin them.",
                f"{SOURCE_REF} V7",
            ))
    return out


def run(parsed: ParsedFile, *, check_cve: bool = False) -> list:
    """Run all seven pre-install checks against a parsed file."""
    findings: list = []
    findings.extend(_check_names(parsed))
    findings.extend(_check_index(parsed))
    findings.extend(_check_makefile(parsed))
    findings.extend(_check_cve(parsed, enabled=check_cve))
    findings.extend(_check_error_injection(parsed))
    return findings
