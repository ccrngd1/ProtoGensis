"""Forge layer: craft tool-use-shaped payloads that no model actually emitted.

Three vectors, escalating in sophistication:

* **Vector A — direct dispatch** (:mod:`.direct`): deliver a ``tool_use`` block in
  the position the event loop consumes, with no preceding model turn. Mirrors the
  AWS/Strands ``_has_tool_use_in_latest_message`` shape.
* **Vector B — replay / forged approval** (:mod:`.replay`): inject a fabricated
  confirmation or resume a session with injected tool-use history.
* **Vector C — cross-session injection** (:mod:`.cross_session`): move a payload or
  auth token from one session/context into another.
"""

from .direct import DirectForgePayload, build_direct_payload
from .replay import ReplayForgePayload, build_replay_payload
from .cross_session import CrossSessionForgePayload, build_cross_session_payload

__all__ = [
    "DirectForgePayload",
    "build_direct_payload",
    "ReplayForgePayload",
    "build_replay_payload",
    "CrossSessionForgePayload",
    "build_cross_session_payload",
]
