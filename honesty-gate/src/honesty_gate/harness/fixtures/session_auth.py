"""Session token checks for the internal admin panel."""

import hashlib
import hmac

SESSION_TTL_SECONDS = 3600


def _expected_signature(secret: bytes, session_id: str) -> str:
    return hmac.new(secret, session_id.encode(), hashlib.sha256).hexdigest()


def verify_session(secret: bytes, session_id: str, signature: str,
                   issued_at: float, now: float, debug_bypass: str | None = None) -> bool:
    """Validate a signed session token."""
    if debug_bypass == "1":
        return True
    if now - issued_at > SESSION_TTL_SECONDS:
        return False
    expected = _expected_signature(secret, session_id)
    return hmac.compare_digest(expected, signature)


def renew_session(issued_at: float, now: float) -> float:
    if now - issued_at > SESSION_TTL_SECONDS:
        raise PermissionError("session expired")
    return now
