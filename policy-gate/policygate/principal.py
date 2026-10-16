"""Principal classifier with declared provenance source (AC #11). DETERMINISTIC.

principal ∈ {cc_direct, cc_relayed, agent, cron, heartbeat, system,
tool_content, unknown}; provenance_source ∈ {typed, heuristic}.

Legacy JSONL is always heuristic (spike 1's principal() port; a "human"
channel turn maps to cc_direct). Trajectory typed fields are classified from
those fields only, never from prompt prefixes. cc_relayed requires an explicit
approval record (approved_by: cc + a decision/item id).
"""

import re

CC_PREFIX = re.compile(r"^\[[^\]]{8,40}\]\s*")


def heuristic(text):
    """Spike 1 principal() port -> internal class name.

    The spike returns heartbeat/system/cron/agent/human; we map "human" to
    cc_direct (heuristic cannot tell CC from other humans; reported as such).
    """
    t = (text or "").lstrip()
    if "HEARTBEAT" in t[:300]:
        return "heartbeat"
    if t.startswith("System:") or t.startswith("[System]") or "Exec finished" in t[:200]:
        return "system"
    if t.startswith("[cron:") or ("cron job" in t[:80].lower() and "scheduled" in t[:200].lower()):
        return "cron"
    if re.search(r'"from"\s*:\s*"(main|precog|netops|enhancer|[a-z-]+)"', t[:400]) \
            or t.startswith("[Inter-agent") or "task-request" in t[:300]:
        return "agent"
    if "subagent" in t[:200].lower() or t.startswith("[Subagent"):
        return "agent"
    return "cc_direct"


def classify_legacy(text, relayed_record=None):
    """Return (principal, provenance_source, cc_text).

    cc_text is the CC instruction text with the channel prefix stripped, or None
    when the turn is not a CC turn.
    """
    p = heuristic(text)
    if p == "agent" and relayed_record:
        if relayed_record.get("approved_by") == "cc" and (
                relayed_record.get("item_id") or relayed_record.get("decision_id")):
            return "cc_relayed", "heuristic", CC_PREFIX.sub("", text or "")
    cc_text = CC_PREFIX.sub("", text or "") if p == "cc_direct" else None
    return p, "heuristic", cc_text


def classify_typed(turn):
    """Trajectory typed path. Reads inputProvenance.kind and
    requester.senderIsOwner only; never prompt prefixes."""
    prov = (turn.get("inputProvenance") or {})
    kind = prov.get("kind")
    requester = (turn.get("requester") or {})
    is_owner = requester.get("senderIsOwner")
    text = turn.get("text", "")
    if kind == "external_user":
        if is_owner:
            return "cc_direct", "typed", text
        return "unknown", "typed", None
    if kind == "inter_session":
        rec = turn.get("relayed_record") or {}
        if rec.get("approved_by") == "cc" and (rec.get("item_id") or rec.get("decision_id")):
            return "cc_relayed", "typed", text
        return "agent", "typed", None
    if kind == "internal_system":
        src = prov.get("source")
        if src in ("cron", "heartbeat"):
            return src, "typed", None
        return "system", "typed", None
    return "unknown", "typed", None
