"""JSONL run log with an injectable clock.

Each event is {seq, t, run_id, arm, seed, agent, kind, payload} where kind is
one of read | propose | accept | repair | reject | draw | notice | env_change.
Demos use a fixed step clock so output is byte-deterministic (no wall time).
"""
from __future__ import annotations

import json
from typing import Any, Callable, TextIO


class StepClock:
    """Deterministic clock: starts at 0, advances by `step` per call."""

    def __init__(self, step: int = 1):
        self._t = 0
        self._step = step

    def __call__(self) -> int:
        t = self._t
        self._t += self._step
        return t


class RunLog:
    def __init__(self, clock: Callable[[], int] | None = None,
                 run_id: str = "run", arm: str = "", seed: int | None = None,
                 sink: TextIO | None = None):
        self.clock = clock or StepClock()
        self.run_id = run_id
        self.arm = arm
        self.seed = seed
        self.events: list[dict] = []
        self._sink = sink
        self._seq = 0

    def emit(self, kind: str, agent: str = "", **payload: Any) -> dict:
        event = {
            "seq": self._seq,
            "t": self.clock(),
            "run_id": self.run_id,
            "arm": self.arm,
            "seed": self.seed,
            "agent": agent,
            "kind": kind,
            "payload": payload,
        }
        self._seq += 1
        self.events.append(event)
        if self._sink is not None:
            self._sink.write(json.dumps(event, sort_keys=True) + "\n")
        return event

    def dump(self, path: str) -> None:
        with open(path, "w") as f:
            for ev in self.events:
                f.write(json.dumps(ev, sort_keys=True) + "\n")

    @staticmethod
    def load(path: str) -> list[dict]:
        events = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events
