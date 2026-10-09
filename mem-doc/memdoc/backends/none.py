"""A0: no memory. Lower bound."""

from .base import ContextParts, MemoryBackend, StoreSnapshot


class NoneBackend(MemoryBackend):
    arm_id = "a0"
    name = "none"
    write_policy = "none"
    read_policy = "none"
    inject = "none"

    def bootstrap(self, session) -> ContextParts:
        return ContextParts()

    def scripted_apply(self, event, session_idx):
        return None

    def fill_distractors(self, distractor_sessions):
        return None

    def store_snapshot(self) -> StoreSnapshot:
        return StoreSnapshot(kind="none", texts={}, token_estimate=0)
