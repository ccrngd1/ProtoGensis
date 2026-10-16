"""Fact store: only principals and tool results create facts (AC #12).

Authorization facts come ONLY from cc_direct / cc_relayed turns; state facts
only from tool.result events. Assistant text, tool-result content asserting
approval, and cron/heartbeat/system/agent turns never create cc_authorized.
Confirmations are consumed on use in the `pinned` profile (a second matching
write needs a fresh CC turn); `spike-parity` does not consume.
"""

from . import readings as readings_mod


class FactStore:
    def __init__(self, profile, readings=None):
        self.profile = profile
        self.consume = (profile == "pinned")
        self.readings = readings or readings_mod.default()
        # current CC authorization context (reset by each turn)
        self.cc_text = None
        self.prev_assistant = ""
        self.principal = "unknown"
        self.agent = None
        self.checkpoints = set()
        self.attempts = {}
        # per-reading consumed flags: {reading: bool}
        self._consumed = {r: False for r in readings_mod.READINGS}

    def observe_turn(self, principal, provenance_source, cc_text, prev_assistant, agent=None):
        self.principal = principal
        self.agent = agent if agent is not None else self.agent
        self.prev_assistant = prev_assistant if prev_assistant is not None else self.prev_assistant
        # only cc_direct / cc_relayed turns provide authorization text
        if principal in ("cc_direct", "cc_relayed"):
            self.cc_text = cc_text
            self._consumed = {r: False for r in readings_mod.READINGS}
        else:
            # a non-CC turn (cron/system/agent/question) clears pending auth
            self.cc_text = None

    def observe_result(self, tool, ok, text):
        # state facts only; e.g. a successful backup clears checkpoint_seen
        if ok and tool and tool.startswith("backup."):
            self.checkpoints.add((text or "").strip() or tool)

    def authorization_for(self, vtool):
        """Return {reading: bool} for cc_authorized on this vtool, applying
        consumption under the pinned profile."""
        res = self.readings.all_readings(vtool, self.cc_text, self.prev_assistant)
        if self.consume:
            out = {}
            for r, val in res.items():
                out[r] = val and not self._consumed[r]
            return out
        return res

    def consume_authorization(self, vtool, used):
        """After a write ALLOWed under a reading, consume the confirmation for
        that reading (pinned only)."""
        if not self.consume:
            return
        for r, was_used in used.items():
            if was_used:
                self._consumed[r] = True

    def facts_snapshot(self, reading, vtool, call):
        """Build the facts dict check.py reads for a single reading."""
        auth = self.authorization_for(vtool)
        return {
            "cc_authorized": auth.get(reading, False),
            "confirmation_fresh": auth.get(reading, False),
            "principal": self.principal,
            "agent": self.agent,
            "checkpoints": set(self.checkpoints),
            "attempts": dict(self.attempts),
        }
