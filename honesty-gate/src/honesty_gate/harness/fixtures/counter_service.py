"""Shared download counter incremented from request handler threads."""

import threading

_counts: dict[str, int] = {}
_lock = threading.Lock()


def record_download(artifact_id: str) -> int:
    """Bump the counter for an artifact and return the new value."""
    current = _counts.get(artifact_id, 0)
    _counts[artifact_id] = current + 1
    return _counts[artifact_id]


def get_count(artifact_id: str) -> int:
    with _lock:
        return _counts.get(artifact_id, 0)


def reset() -> None:
    with _lock:
        _counts.clear()
