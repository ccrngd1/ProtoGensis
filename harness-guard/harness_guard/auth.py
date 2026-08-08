"""Model-issued authorization primitive (the fix for CoreBreak).

An ``Authorization`` binds a tool dispatch to a specific *model turn*. It is minted
only when the model genuinely emits a tool_use block, signed with a server-held
key, and consumed exactly once at dispatch. A harness that requires a matching,
unexpired, unconsumed authorization for every tool execution satisfies the
architectural invariant.

The signing key is **ephemeral**: generated fresh per process, never written to
disk, never logged. This mirrors the hardened harness contract.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass, field


def args_hash(tool_input: dict) -> str:
    """Stable hash of tool arguments, for binding auth to specific args."""
    canonical = json.dumps(tool_input, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class Authorization:
    session_id: str
    turn_id: str
    tool_name: str
    args_hash: str
    nonce: str
    issued_at: float
    expires_at: float
    signature: str = ""

    def _signing_bytes(self) -> bytes:
        payload = {
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "tool_name": self.tool_name,
            "args_hash": self.args_hash,
            "nonce": self.nonce,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "tool_name": self.tool_name,
            "args_hash": self.args_hash,
            "nonce": self.nonce,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Authorization":
        return cls(
            session_id=data["session_id"],
            turn_id=data["turn_id"],
            tool_name=data["tool_name"],
            args_hash=data["args_hash"],
            nonce=data["nonce"],
            issued_at=float(data["issued_at"]),
            expires_at=float(data["expires_at"]),
            signature=data.get("signature", ""),
        )


class AuthMinter:
    """Mints and verifies one-time authorizations with an ephemeral HMAC key.

    The key never leaves the process and is never logged. Only code that holds the
    minter (i.e. the harness's own model-turn handler) can produce a valid
    signature — which is exactly why forged/replayed authorizations fail.
    """

    def __init__(self, ttl_seconds: float = 30.0) -> None:
        # Ephemeral: fresh per process, never persisted, never logged.
        self._key = os.urandom(32)
        self.ttl_seconds = ttl_seconds
        self._consumed: set[str] = set()

    def mint(self, session_id: str, turn_id: str, tool_name: str, tool_input: dict) -> Authorization:
        now = time.time()
        auth = Authorization(
            session_id=session_id,
            turn_id=turn_id,
            tool_name=tool_name,
            args_hash=args_hash(tool_input),
            nonce=uuid.uuid4().hex,
            issued_at=now,
            expires_at=now + self.ttl_seconds,
        )
        auth.signature = hmac.new(self._key, auth._signing_bytes(), hashlib.sha256).hexdigest()
        return auth

    def verify_and_consume(
        self, auth: Authorization | None, tool_name: str, tool_input: dict
    ) -> tuple[bool, str]:
        """Return ``(ok, reason)``. Consumes the nonce on success (one-time use)."""
        if auth is None:
            return False, "no model-issued authorization found"

        expected = hmac.new(self._key, auth._signing_bytes(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, auth.signature or ""):
            return False, "authorization signature invalid (not model-issued)"

        if time.time() > auth.expires_at:
            return False, "authorization expired"

        if auth.nonce in self._consumed:
            return False, "authorization already consumed (replay)"

        if auth.tool_name != tool_name:
            return False, "authorization tool_name does not match call"

        if auth.args_hash != args_hash(tool_input):
            return False, "authorization args_hash does not match call arguments"

        self._consumed.add(auth.nonce)
        return True, "ok"
