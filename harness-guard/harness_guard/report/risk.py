"""Risk tiering, hardening-tier scoring, and remediation.

* **Risk tier** (per tool): how bad it is if this tool can be triggered without a
  model turn — ``read_only`` < ``write`` < ``destructive`` < ``exfil``.
* **Hardening tier** (per target): how many forge vectors the harness resisted.
    - 0: no provenance check — any of the 3 vectors succeed.
    - 1: untrusted history — direct blocked, but replay/cross_session succeed.
    - 2: model-event-bound — all 3 blocked on provenance grounds.
    - 3: EBTE-style semantic binding — reported if detectable, not required for v1.
"""

from __future__ import annotations

import re
from typing import Literal

RiskTier = Literal["read_only", "write", "destructive", "exfil"]
HardeningTier = Literal[0, 1, 2, 3]

_TIER_RANK: dict[str, int] = {"read_only": 0, "write": 1, "destructive": 2, "exfil": 3}

# Ordered most-severe first; first match wins. Leading word boundary only, so
# stems match inflections and underscore-joined names ("removes", "delete_all").
_PATTERNS: list[tuple[RiskTier, re.Pattern]] = [
    ("exfil", re.compile(r"\b(exfil|upload|post|send|callback|webhook|http|curl|fetch|email|dns|beacon|leak)", re.I)),
    ("destructive", re.compile(r"\b(delete|remove|rm|drop|destroy|wipe|truncate|kill|shutdown|exec|shell|eval|system|spawn|format)", re.I)),
    ("write", re.compile(r"\b(write|create|update|edit|put|patch|save|append|set|insert|modify|move|rename|mkdir)", re.I)),
    ("read_only", re.compile(r"\b(read|get|list|search|echo|status|info|describe|show|view|query|cat|head)", re.I)),
]


def classify_tool_risk(name: str, description: str = "") -> RiskTier:
    """Assign a risk tier from a tool's name and description."""
    haystack = f"{name} {description}"
    for tier, pat in _PATTERNS:
        if pat.search(haystack):
            return tier
    # Unknown tools are treated as write-capable (conservative default).
    return "write"


def max_risk_tier(tiers: list[str]) -> RiskTier:
    if not tiers:
        return "read_only"
    return max(tiers, key=lambda t: _TIER_RANK.get(t, 1))  # type: ignore[return-value]


def score_hardening_tier(vector_results: dict[str, str]) -> HardeningTier:
    """Score hardening tier from per-vector verdicts.

    ``vector_results`` maps vector name -> verdict ("VULNERABLE"/"HARDENED"/...).
    """
    def blocked(v: str) -> bool:
        return vector_results.get(v) == "HARDENED"

    direct_blocked = blocked("direct")
    replay_blocked = blocked("replay")
    xsession_blocked = blocked("cross_session")

    if direct_blocked and replay_blocked and xsession_blocked:
        return 2  # model-event-bound; tier 3 (semantic) not asserted without evidence
    if direct_blocked and (not replay_blocked or not xsession_blocked):
        return 1  # history untrusted for direct, but replay/cross-session slip through
    return 0  # at least one direct-style bypass succeeds


_REMEDIATION: dict[int, list[str]] = {
    0: [
        "Require a model-issued authorization for EVERY tool execution — never dispatch on 'tool_use present in latest message'.",
        "Mint a one-time authorization only when the model genuinely emits a tool_use block.",
        "Sign authorizations with a server-held key (HMAC-SHA256) the client never sees.",
        "Bind the authorization to {session_id, turn_id, tool_name, args_hash, nonce, issued_at, expires_at}.",
        "Reject any dispatch lacking a matching, unexpired, unconsumed authorization.",
        "Keep the signing key ephemeral: fresh per process, never stored, never logged.",
    ],
    1: [
        "Do not trust replayed/resumed session history as tool-call provenance — re-verify authorization on resume.",
        "Reject forged approval objects: an approval is not an authorization unless signed by the server key.",
        "Bind authorization to args_hash so approvals minted for other arguments cannot be reused.",
        "Scope authorizations to a single session_id; reject tokens issued for a different session (cross-session replay).",
        "Do not trust client-supplied process/parent-path identity for authorization decisions.",
    ],
    2: [
        "Consider EBTE-style semantic binding (tier 3): bind the authorization to the specific model event/tokens, not just field equality.",
        "Add monitoring/alerting for injected-dispatch attempts (auth-absent or signature-invalid calls).",
        "Periodically rotate and re-validate the invariant with automated tooling (e.g. this scanner in CI).",
    ],
    3: [
        "Maintain semantic binding coverage across all tool surfaces and transports.",
        "Continue automated regression testing of the provenance invariant.",
    ],
}


def remediation_checklist(hardening_tier: int) -> list[str]:
    """Return remediation items appropriate to the current tier and everything above it."""
    items: list[str] = []
    for t in range(hardening_tier, 3):
        items.extend(_REMEDIATION.get(t, []))
    if hardening_tier >= 2:
        items.extend(_REMEDIATION[2])
    # De-dup preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def build_report(
    *,
    target: str,
    adapter: str,
    tools: list[dict],
    vector_results: dict[str, dict],
) -> dict:
    """Assemble the report JSON.

    ``vector_results`` maps vector name -> {"verdict", "observation", ...}.
    """
    tool_risks = []
    for tool in tools:
        tname = tool.get("name", "?")
        tdesc = tool.get("description", "")
        tool_risks.append(
            {"name": tname, "description": tdesc, "risk_tier": classify_tool_risk(tname, tdesc)}
        )

    verdict_by_vector = {v: r.get("verdict", "INCONCLUSIVE") for v, r in vector_results.items()}
    tier = score_hardening_tier(verdict_by_vector)

    any_vulnerable = any(v == "VULNERABLE" for v in verdict_by_vector.values())
    all_hardened = bool(verdict_by_vector) and all(
        v == "HARDENED" for v in verdict_by_vector.values()
    )
    overall = "VULNERABLE" if any_vulnerable else ("HARDENED" if all_hardened else "INCONCLUSIVE")

    return {
        "target": target,
        "adapter": adapter,
        "overall_verdict": overall,
        "hardening_tier": tier,
        "invariant": (
            "For every tool execution, exactly one unconsumed, unexpired, "
            "model-issued authorization exists whose bound fields match the call."
        ),
        "tools": tool_risks,
        "max_tool_risk": max_risk_tier([t["risk_tier"] for t in tool_risks]),
        "vectors": {
            v: {
                "verdict": r.get("verdict", "INCONCLUSIVE"),
                "response_type": r.get("response_type"),
                "side_effects_detected": r.get("side_effects_detected", []),
                "timing_ms": r.get("timing_ms"),
            }
            for v, r in vector_results.items()
        },
        "remediation": remediation_checklist(tier),
    }
