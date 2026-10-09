"""Storyline schema (AC #2): dataclasses + deterministic TOML round-trip.

All storyline content is synthetic and CABAL-shaped (layout, not content): the
domains are generic agent ops, research handoffs, and homelab configuration.
No real CABAL file content, memory line, or personal fact appears here (R9).
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CATEGORIES = {
    1: "preference_retention",
    2: "decision_continuity",
    3: "explicit_correction",
    4: "implicit_conflict",
    5: "multi_session_aggregation",
    6: "procedural_lesson",
    7: "abstention_premise_resistance",
    8: "cold_start",
}

FACT_KINDS = ("introduce", "correct_explicit", "invalidate_implicit", "enumerate")
PROBE_KINDS = ("recall", "compliance")
SESSION_PROFILES = {"short": (5, 2), "medium": (30, 5), "long": (150, 15)}
ABSTAIN = "ABSTAIN"


@dataclass
class FactEvent:
    key: str
    kind: str                 # introduce | correct_explicit | invalidate_implicit | enumerate
    text: str                 # the memory line the writer stores (contains the canary)
    canary: str
    session: int              # 1-based session index where this event happens
    canary_type: str = "code"  # port | code | codename | date
    near_miss: bool = False   # category-7 near-miss distractor fact
    supersedes: str = ""      # canary value this event supersedes ("" if none)


@dataclass
class Probe:
    id: str
    session: int
    prompt: str
    gold: str                 # canary value or "ABSTAIN"
    fact_keys: list[str]
    depth: int                # dependency depth for SR@depth-k
    unknown_unknown: bool = False
    kind: str = "recall"      # recall | compliance
    canary_type: str = "code"
    stale: str = ""           # superseded canary that counts as a stale answer
    compliance_rule: str = ""  # rule id for compliance probes


@dataclass
class Session:
    index: int
    kind: str                 # write | probe
    summary: str              # synthetic session narrative (no canaries for probe sessions)


@dataclass
class Storyline:
    id: str
    category: int
    seed: int
    session_profile: str
    sessions: list[Session] = field(default_factory=list)
    facts: list[FactEvent] = field(default_factory=list)
    probes: list[Probe] = field(default_factory=list)
    world_dir: str = "world"

    @property
    def category_name(self) -> str:
        return CATEGORIES[self.category]


def _toml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _kv(key: str, value) -> str:
    if isinstance(value, bool):
        return f"{key} = {'true' if value else 'false'}"
    if isinstance(value, int):
        return f"{key} = {value}"
    if isinstance(value, list):
        inner = ", ".join(f'"{_toml_escape(v)}"' for v in value)
        return f"{key} = [{inner}]"
    return f'{key} = "{_toml_escape(value)}"'


def storyline_to_toml(s: Storyline) -> str:
    """Deterministic TOML emitter (stdlib has no writer). Fixed key order."""
    lines = [
        _kv("id", s.id),
        _kv("category", s.category),
        _kv("category_name", s.category_name),
        _kv("seed", s.seed),
        _kv("session_profile", s.session_profile),
        _kv("world_dir", s.world_dir),
        "",
    ]
    for sess in s.sessions:
        lines += ["[[sessions]]", _kv("index", sess.index), _kv("kind", sess.kind),
                  _kv("summary", sess.summary), ""]
    for f in s.facts:
        lines += ["[[facts]]", _kv("key", f.key), _kv("kind", f.kind), _kv("text", f.text),
                  _kv("canary", f.canary), _kv("canary_type", f.canary_type),
                  _kv("session", f.session), _kv("near_miss", f.near_miss),
                  _kv("supersedes", f.supersedes), ""]
    for p in s.probes:
        lines += ["[[probes]]", _kv("id", p.id), _kv("session", p.session),
                  _kv("prompt", p.prompt), _kv("gold", p.gold),
                  _kv("fact_keys", p.fact_keys), _kv("depth", p.depth),
                  _kv("unknown_unknown", p.unknown_unknown), _kv("kind", p.kind),
                  _kv("canary_type", p.canary_type), _kv("stale", p.stale),
                  _kv("compliance_rule", p.compliance_rule), ""]
    return "\n".join(lines)


def storyline_from_dict(d: dict) -> Storyline:
    return Storyline(
        id=d["id"], category=int(d["category"]), seed=int(d["seed"]),
        session_profile=d["session_profile"], world_dir=d.get("world_dir", "world"),
        sessions=[Session(index=x["index"], kind=x["kind"], summary=x["summary"])
                  for x in d.get("sessions", [])],
        facts=[FactEvent(key=x["key"], kind=x["kind"], text=x["text"], canary=x["canary"],
                         session=x["session"], canary_type=x.get("canary_type", "code"),
                         near_miss=x.get("near_miss", False), supersedes=x.get("supersedes", ""))
               for x in d.get("facts", [])],
        probes=[Probe(id=x["id"], session=x["session"], prompt=x["prompt"], gold=x["gold"],
                      fact_keys=list(x.get("fact_keys", [])), depth=x["depth"],
                      unknown_unknown=x.get("unknown_unknown", False), kind=x.get("kind", "recall"),
                      canary_type=x.get("canary_type", "code"), stale=x.get("stale", ""),
                      compliance_rule=x.get("compliance_rule", ""))
                for x in d.get("probes", [])],
    )


def load_storyline(path) -> Storyline:
    with open(path, "rb") as f:
        return storyline_from_dict(tomllib.load(f))


def load_all(tasks_dir) -> list[Storyline]:
    tasks_dir = Path(tasks_dir)
    out = []
    for p in sorted(tasks_dir.glob("*/storyline.toml")):
        out.append(load_storyline(p))
    return out


@dataclass
class DistractorSession:
    id: str
    summary: str
    lines: list[str]          # memory lines the writer stores (non-probed facts)


def load_distractors(tasks_dir) -> list[DistractorSession]:
    path = Path(tasks_dir) / "distractors.toml"
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return [DistractorSession(id=d["id"], summary=d["summary"], lines=list(d["lines"]))
            for d in data.get("distractors", [])]


def distractors_to_toml(items: list[DistractorSession]) -> str:
    lines = []
    for d in items:
        lines += ["[[distractors]]", _kv("id", d.id), _kv("summary", d.summary),
                  _kv("lines", d.lines), ""]
    return "\n".join(lines)
