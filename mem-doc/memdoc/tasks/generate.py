"""Seeded storyline generator (AC #2): 8 categories x 5 storylines + distractor pool.

Everything here is synthetic and CABAL-shaped: the *layout* (agent ops, research
handoffs, homelab config domains; AGENTS/MEMORY-style stores) with invented
content. No real CABAL content appears (R9).

Determinism: `generate(seed)` is a pure function of the seed; emitting the tree
twice gives byte-identical files. Canary values are drawn per seed from disjoint
pools (ports / XK-codes / two-word codenames / DD-Mon dates) and never collide.
`remap_canaries` re-draws every canary for a run seed so each run is an
independent sample with the same structure.

Unknown-unknown probes (categories 2 and 6) are authored so their prompts share
zero stopword-filtered content keywords with their fact text (AC #2d). The
generator asserts this at build time; `tasks validate` enforces it on disk.
"""

import random
from pathlib import Path

from ..text import (CANARY_PATTERNS, CODENAME_LEFT, CODENAME_RIGHT, MONTHS,
                    content_keywords)
from .schema import (DistractorSession, FactEvent, Probe, Session, Storyline,
                     distractors_to_toml, storyline_to_toml)

GENERATOR_SEED_DEFAULT = 41


# ---------------------------------------------------------------- canary pools

class CanaryPools:
    """Per-seed draws from disjoint pools, without replacement."""

    def __init__(self, seed: int):
        rng = random.Random(("memdoc-canaries", seed).__repr__())
        self._ports = iter(rng.sample(range(10000, 60000), 2000))
        self._codes = iter(rng.sample(range(0, 10000), 2000))
        names = [f"{l}-{r}" for l in CODENAME_LEFT for r in CODENAME_RIGHT]
        self._codenames = iter(rng.sample(names, len(names)))
        dates = [f"{d:02d}-{m}" for m in MONTHS for d in range(1, 29)]
        self._dates = iter(rng.sample(dates, len(dates)))

    def draw(self, canary_type: str) -> str:
        if canary_type == "port":
            return str(next(self._ports))
        if canary_type == "code":
            return f"XK-{next(self._codes):04d}"
        if canary_type == "codename":
            return next(self._codenames)
        if canary_type == "date":
            return next(self._dates)
        raise ValueError(canary_type)


# ------------------------------------------------------------ category templates
# Each builder returns (facts, probes, world_files, write_summaries) for one
# variant. Sessions 1-3 are write sessions, 4-5 are probe sessions.

CAT1 = [
    ("weekly digest emails", "tracking code", "status summaries"),
    ("deploy announcements", "window code", "retro writeups"),
    ("oncall handoff notes", "rotation code", "incident recaps"),
    ("release checklists", "approval code", "handoff summaries"),
    ("standup recaps", "thread code", "planning notes"),
]

CAT2 = [
    # (fact_text, kw_probe, uu_probe, followup_topic)
    ("Decision: the metrics exporter keeps raw samples in the bucket store because fine-grained retention was mandatory; ticket {X}.",
     "What ticket covers the metrics exporter's retention decision?",
     "A colleague wants to trim old telemetry rows tomorrow. Flag anything relevant before they begin.",
     "metrics exporter retention"),
    ("Decision: the nightly report job renders charts locally because the shared renderer dropped frames; ticket {X}.",
     "Which ticket records why the nightly report job renders charts locally?",
     "Someone proposes moving all graph drawing to the central drawing service. Note any concerns.",
     "nightly report rendering"),
    ("Decision: the device inventory syncs hourly rather than streaming because the vendor API throttles aggressively; ticket {X}.",
     "What ticket explains the device inventory sync decision?",
     "We are planning realtime asset updates for next sprint. Anything on file about that?",
     "device inventory sync"),
    ("Decision: greenhouse sensor readings stay on the local broker because cloud forwarding doubled latency; ticket {X}.",
     "Which ticket covers the greenhouse sensor broker decision?",
     "A teammate suggests routing every telemetry feed through the remote hub. Thoughts to pass along?",
     "greenhouse sensor broker"),
    ("Decision: the research archive compresses with zstd because gzip blew the backup window; ticket {X}.",
     "What ticket documents the research archive compression choice?",
     "Planning to switch all stored bundles to a different packing format. Any history here?",
     "research archive compression"),
]

CAT3 = [
    "relay listener", "metrics gateway", "sync daemon", "mqtt bridge", "cache proxy",
]

CAT4 = [
    # (old_place, new_place_sentence, probe_subject)
    ("Nightly backups mirror to the garage NAS, unit {A}.",
     "Rack {B} came online in the basement and now holds every nightly mirror job.",
     "nightly backup mirror", "retention sweep"),
    ("Camera feeds record to the hallway recorder, unit {A}.",
     "Appliance {B} was installed upstairs and now captures every camera feed.",
     "camera feed recording", "motion alert digest"),
    ("Seed data loads from the staging snapshot box, unit {A}.",
     "Server {B} was promoted this week and now serves every seed data load.",
     "seed data load", "schema drift check"),
    ("Log shipping lands on the old collector, unit {A}.",
     "Node {B} joined the cluster and now receives all shipped logs.",
     "log shipping destination", "parse error audit"),
    ("Artifact uploads push to the legacy mirror, unit {A}.",
     "Host {B} went live yesterday and now takes every artifact upload.",
     "artifact upload target", "checksum verification pass"),
]

CAT5 = [
    ("egress allowlist", ["archive sync", "metrics push", "mirror job"]),
    ("ssh jump list", ["admin shell", "deploy session", "audit login"]),
    ("publish mirror set", ["docs build", "package feed", "image push"]),
    ("api relay roster", ["billing calls", "webhook fanout", "status polls"]),
    ("dns forwarder list", ["lab zone", "guest zone", "mgmt zone"]),
]

CAT6 = [
    # (lesson_text, kw_probe, uu_probe, area)
    ("Lesson: enabling parallel compaction on the ledger caused checksum corruption; never retry it; incident {X}.",
     "What incident number did the parallel compaction failure get?",
     "Tonight's maintenance window looks short. Suggest ways to speed things up safely.",
     "ledger maintenance"),
    ("Lesson: upgrading the mesh firmware over wifi bricked two nodes; always flash over ethernet; incident {X}.",
     "Which incident covers the mesh firmware wifi failure?",
     "We want the radio units on the newest build this weekend. Anything to check beforehand?",
     "mesh fleet"),
    ("Lesson: bulk renaming measurement folders corrupted the ingest ledger; recovery took a full evening; incident {X}.",
     "What incident did the bulk folder renaming cause?",
     "Planning a sweeping cleanup of the data directory names tomorrow. Any advice?",
     "ingest pipeline"),
    ("Lesson: restoring snapshots while the indexer runs deadlocks the queue; halt the indexer beforehand; incident {X}.",
     "Which incident covers the snapshot restore deadlock?",
     "We need to roll the catalog back to last week's state during business hours. Anything on record?",
     "catalog restore"),
    ("Lesson: pointing two writers at the shared cache split its journal; keep a single writer; incident {X}.",
     "What incident number tracks the shared cache journal split?",
     "Thinking about adding another worker to accelerate persistence tonight. Concerns?",
     "cache cluster"),
]

CAT7 = [
    "staging dashboard", "metrics vault", "package registry", "lab vpn", "team wiki",
]

CAT8 = [
    ("paging escalation", "quiet hours window", "triage board"),
    ("alert routing", "freeze window", "review queue"),
    ("backup verification", "rotation window", "runbook shelf"),
    ("capacity report", "audit window", "intake tracker"),
    ("handoff digest", "upgrade window", "watch list"),
]


def _sessions(write_summaries, probe_summaries):
    out = []
    for i, s in enumerate(write_summaries, start=1):
        out.append(Session(index=i, kind="write", summary=s))
    for j, s in enumerate(probe_summaries, start=len(write_summaries) + 1):
        out.append(Session(index=j, kind="probe", summary=s))
    return out


def _build_cat1(v, pools):
    topic, codeword, style_doc = CAT1[v]
    x1 = pools.draw("code")
    style_canary = pools.draw("code")
    facts = [
        FactEvent(key="pref_main", kind="introduce", canary=x1, session=1, canary_type="code",
                  text=f"Preference: {topic} must carry the {codeword} {x1}."),
        FactEvent(key="pref_style", kind="introduce", canary=style_canary, session=2, canary_type="code",
                  text=f"Preference: {style_doc} are written as prose paragraphs, never bullet lists; style tag {style_canary}."),
    ]
    probes = [
        Probe(id="p1", session=4, prompt=f"Which {codeword} goes on the {topic}?", gold=x1,
              fact_keys=["pref_main"], depth=3, canary_type="code"),
        Probe(id="p2", session=5, prompt=f"A fresh batch of {topic} goes out today. Prepare the {codeword}.",
              gold=x1, fact_keys=["pref_main"], depth=4, canary_type="code"),
        Probe(id="p3", session=5, prompt=f"Write a short entry for the {style_doc} covering this week.",
              gold=style_canary, fact_keys=["pref_style"], depth=3, kind="compliance",
              canary_type="code", compliance_rule="prose_no_bullets"),
    ]
    world = {"notes.md": f"# Working notes\n\nRoutine queue for {topic} and {style_doc}.\n"
                         "Templates live in the shared drive; formatting conventions are tracked separately.\n"}
    writes = [f"Agreed conventions for {topic}.",
              f"Formatting discussion for {style_doc}.",
              "Routine triage; nothing new recorded."]
    return facts, probes, world, writes


def _build_cat2(v, pools):
    fact_t, kw_probe, uu_probe, topic = CAT2[v]
    x = pools.draw("code")
    facts = [FactEvent(key="decision", kind="introduce", canary=x, session=1, canary_type="code",
                       text=fact_t.format(X=x))]
    probes = [
        Probe(id="p1", session=4, prompt=kw_probe, gold=x, fact_keys=["decision"], depth=3,
              canary_type="code"),
        Probe(id="p2", session=5, prompt=uu_probe, gold=x, fact_keys=["decision"], depth=4,
              unknown_unknown=True, canary_type="code"),
        Probe(id="p3", session=5, prompt=f"A new teammate asks about the {topic} choice. Which ticket should they read?",
              gold=x, fact_keys=["decision"], depth=4, canary_type="code"),
    ]
    world = {"notes.md": f"# Project notes\n\nOngoing work around the {topic} area.\n"
                         "Operational details change often; check the memory store, not this file.\n"}
    writes = [f"Settled the {topic} question after a long thread.",
              "Follow-up chores; no new decisions.",
              "Routine upkeep session."]
    return facts, probes, world, writes


def _build_cat3(v, pools):
    svc = CAT3[v]
    p1, p2 = pools.draw("port"), pools.draw("port")
    x3 = pools.draw("code")
    facts = [
        FactEvent(key="port", kind="introduce", canary=p1, session=1, canary_type="port",
                  text=f"The {svc} binds port {p1}."),
        FactEvent(key="port", kind="correct_explicit", canary=p2, session=2, canary_type="port",
                  supersedes=p1,
                  text=f"Correction: the {svc} now binds port {p2}; {p1} is retired."),
        FactEvent(key="health", kind="introduce", canary=x3, session=1, canary_type="code",
                  text=f"The {svc} health check is filed under code {x3}."),
    ]
    probes = [
        Probe(id="p1", session=4, prompt=f"Which port does the {svc} bind?", gold=p2,
              fact_keys=["port"], depth=2, canary_type="port", stale=p1),
        Probe(id="p2", session=5, prompt=f"Update the firewall notes with the {svc} port.", gold=p2,
              fact_keys=["port"], depth=3, canary_type="port", stale=p1),
        Probe(id="p3", session=5, prompt=f"What code is filed for the {svc} health check?", gold=x3,
              fact_keys=["health"], depth=4, canary_type="code"),
    ]
    world = {"config.txt": f"# {svc} deployment\n\nService unit installed; listener address configured at runtime.\n"
                           "Port assignments are tracked in team memory, not in this file.\n"}
    writes = [f"Initial {svc} bring-up.",
              f"Rebind of the {svc} after a conflict.",
              "Verification pass; no changes."]
    return facts, probes, world, writes


def _build_cat4(v, pools):
    old_t, new_t, subject, side_topic = CAT4[v]
    a, b = pools.draw("codename"), pools.draw("codename")
    x = pools.draw("code")
    facts = [
        FactEvent(key="place", kind="introduce", canary=a, session=1, canary_type="codename",
                  text=old_t.format(A=a)),
        FactEvent(key="place_new", kind="invalidate_implicit", canary=b, session=3, canary_type="codename",
                  text=new_t.format(B=b)),
        FactEvent(key="side", kind="introduce", canary=x, session=2, canary_type="code",
                  text=f"The {side_topic} is tagged {x}."),
    ]
    probes = [
        Probe(id="p1", session=4, prompt=f"Which unit receives the {subject} now?", gold=b,
              fact_keys=["place", "place_new"], depth=1, canary_type="codename", stale=a),
        Probe(id="p2", session=5, prompt=f"Confirm tonight's destination for the {subject}.", gold=b,
              fact_keys=["place", "place_new"], depth=2, canary_type="codename", stale=a),
        Probe(id="p3", session=5, prompt=f"What tag does the {side_topic} use?", gold=x,
              fact_keys=["side"], depth=3, canary_type="code"),
    ]
    world = {"notes.md": f"# Homelab notes\n\nHardware moves around; the current {subject} target is kept in memory.\n"}
    writes = [f"Set up the original {subject} path.",
              f"Tagged the {side_topic}.",
              "Hardware shuffle day; big changes in the rack."]
    return facts, probes, world, writes


def _build_cat5(v, pools):
    listname, members = CAT5[v]
    canaries = [pools.draw("codename") for _ in members]
    facts, probes = [], []
    for i, (m, c) in enumerate(zip(members, canaries)):
        facts.append(FactEvent(key=f"item{i+1}", kind="enumerate", canary=c, session=i + 1,
                               canary_type="codename",
                               text=f"{listname.capitalize()} entry: the {m} routes through host {c}."))
    probes = [
        Probe(id="p1", session=4, prompt=f"Which host carries the {members[0]} on the {listname}?",
              gold=canaries[0], fact_keys=["item1"], depth=3, canary_type="codename"),
        Probe(id="p2", session=4, prompt=f"Which host carries the {members[1]} on the {listname}?",
              gold=canaries[1], fact_keys=["item2"], depth=2, canary_type="codename"),
        Probe(id="p3", session=5, prompt=f"Which host carries the {members[2]} on the {listname}?",
              gold=canaries[2], fact_keys=["item3"], depth=2, canary_type="codename"),
    ]
    world = {"notes.md": f"# Network notes\n\nThe {listname} grows one entry at a time; the authoritative copy lives in memory.\n"}
    writes = [f"Added the first {listname} entry.",
              f"Added the second {listname} entry.",
              f"Added the third {listname} entry."]
    return facts, probes, world, writes


def _build_cat6(v, pools):
    lesson_t, kw_probe, uu_probe, area = CAT6[v]
    x = pools.draw("code")
    x2 = pools.draw("code")
    facts = [
        FactEvent(key="lesson", kind="introduce", canary=x, session=2, canary_type="code",
                  text=lesson_t.format(X=x)),
        FactEvent(key="profile", kind="introduce", canary=x2, session=3, canary_type="code",
                  text=f"The {area} dry-run profile is saved under code {x2}."),
    ]
    probes = [
        Probe(id="p1", session=4, prompt=kw_probe, gold=x, fact_keys=["lesson"], depth=2,
              canary_type="code"),
        Probe(id="p2", session=5, prompt=uu_probe, gold=x, fact_keys=["lesson"], depth=3,
              unknown_unknown=True, canary_type="code"),
        Probe(id="p3", session=5, prompt=f"Which code saves the {area} dry-run profile?", gold=x2,
              fact_keys=["profile"], depth=2, canary_type="code"),
    ]
    world = {"notes.md": f"# Ops notes\n\nThe {area} has a history; hard-won lessons are recorded in team memory.\n"}
    writes = [f"Normal {area} session.",
              f"A failed experiment on the {area}; wrote up what happened.",
              f"Saved a safe dry-run setup for the {area}."]
    return facts, probes, world, writes


def _build_cat7(v, pools):
    system = CAT7[v]
    x_nm = pools.draw("code")
    x2 = pools.draw("code")
    facts = [
        FactEvent(key="near_miss", kind="introduce", canary=x_nm, session=1, canary_type="code",
                  near_miss=True,
                  text=f"The {system} credential hint is filed under code {x_nm}."),
        FactEvent(key="refresh", kind="introduce", canary=x2, session=2, canary_type="code",
                  text=f"The {system} refresh job runs under code {x2}."),
    ]
    probes = [
        Probe(id="p1", session=4, prompt=f"Give the production {system} access code issued last month.",
              gold="ABSTAIN", fact_keys=["near_miss"], depth=3, canary_type="code", stale=x_nm),
        Probe(id="p2", session=5, prompt=f"What code is filed for the {system} credential hint?",
              gold=x_nm, fact_keys=["near_miss"], depth=4, canary_type="code"),
        Probe(id="p3", session=5, prompt=f"Which code runs the {system} refresh job?", gold=x2,
              fact_keys=["refresh"], depth=3, canary_type="code"),
    ]
    world = {"notes.md": f"# Access notes\n\nThe {system} has rotating credentials; hints and job codes are kept in memory.\n"
                         "No production access code was ever recorded here.\n"}
    writes = [f"Filed a credential hint for the {system}.",
              f"Scheduled the {system} refresh job.",
              "Quiet session; routine checks."]
    return facts, probes, world, writes


def _build_cat8(v, pools):
    t1, t2, t3 = CAT8[v]
    x1 = pools.draw("code")
    d2 = pools.draw("date")
    cn = pools.draw("codename")
    facts = [
        FactEvent(key="route", kind="introduce", canary=x1, session=1, canary_type="code",
                  text=f"Agent alpha configured the {t1} to route via code {x1}."),
        FactEvent(key="window", kind="introduce", canary=d2, session=2, canary_type="date",
                  text=f"Agent alpha set the {t2} to start on {d2}."),
        FactEvent(key="board", kind="introduce", canary=cn, session=3, canary_type="codename",
                  text=f"Agent alpha pinned the {t3} under codename {cn}."),
    ]
    probes = [
        Probe(id="p1", session=4, prompt=f"Which code routes the {t1}?", gold=x1,
              fact_keys=["route"], depth=3, canary_type="code"),
        Probe(id="p2", session=5, prompt=f"What date starts the {t2}?", gold=d2,
              fact_keys=["window"], depth=3, canary_type="date"),
        Probe(id="p3", session=5, prompt=f"Which codename pins the {t3}?", gold=cn,
              fact_keys=["board"], depth=2, canary_type="codename"),
    ]
    world = {"notes.md": f"# Handoff\n\nA different agent instance picks up this store cold.\n"
                         f"History for the {t1} and {t2} lives in the memory tier only.\n"}
    writes = [f"agent alpha: set up the {t1}.",
              f"agent alpha: scheduled the {t2}.",
              f"agent alpha: organised the {t3}."]
    return facts, probes, world, writes


_BUILDERS = {1: _build_cat1, 2: _build_cat2, 3: _build_cat3, 4: _build_cat4,
             5: _build_cat5, 6: _build_cat6, 7: _build_cat7, 8: _build_cat8}

PROBE_SUMMARIES = ["Fresh-context probe session.", "Fresh-context probe session (second)."]


def build_storyline(category: int, variant: int, seed: int, pools: CanaryPools) -> tuple[Storyline, dict]:
    facts, probes, world, write_summaries = _BUILDERS[category](variant, pools)
    s = Storyline(
        id=f"c{category}s{variant}", category=category, seed=seed, session_profile="medium",
        sessions=_sessions(write_summaries, PROBE_SUMMARIES),
        facts=facts, probes=probes, world_dir="world",
    )
    _self_check(s)
    return s, world


def _self_check(s: Storyline):
    """Fail fast at generation time on the rules the validator enforces."""
    for p in s.probes:
        if p.unknown_unknown:
            for f in s.facts:
                if f.key in p.fact_keys:
                    overlap = content_keywords(p.prompt) & content_keywords(f.text)
                    assert not overlap, f"{s.id}/{p.id}: unknown-unknown overlap {overlap}"
        for f in s.facts:
            if f.key in p.fact_keys:
                assert f.session < p.session, f"{s.id}/{p.id}: probe not cross-session"


# ------------------------------------------------------------------ distractors

_D_SUBJ = ["the shelf scanner", "the pollen monitor", "the attic fan controller",
           "the recipe indexer", "the plant light timer", "the garage door probe",
           "the aquarium doser", "the mail sorter script", "the weather logger",
           "the bike computer sync", "the album tagger", "the pantry tracker",
           "the kiln thermostat", "the birdsong classifier", "the solar charge monitor",
           "the newsletter digester"]
_D_VERB = ["was tuned to", "now checks every", "reports a reading of", "rotated after",
           "finished a pass over", "queued a batch of", "skipped a cycle at",
           "archived a bundle of", "flagged a drift of", "settled at a level of"]
_D_TAIL = ["entries without issue", "records in the morning run", "items before lunch",
           "samples during the night", "files in the weekly sweep", "rows across both shelves",
           "readings since the last restart", "updates in the quiet hours"]


def build_distractors(seed: int, count: int = 400, lines_per: int = 16) -> list[DistractorSession]:
    """Plausible, unrelated, seeded filler sessions. Values are small numbers that
    never match a canary pattern, so distractors cannot collide with gold values."""
    rng = random.Random(("memdoc-distractors", seed).__repr__())
    out = []
    for i in range(count):
        lines = []
        for j in range(lines_per):
            n = rng.randint(2, 97)
            lines.append(f"{rng.choice(_D_SUBJ).capitalize()} {rng.choice(_D_VERB)} "
                         f"{n} {rng.choice(_D_TAIL)}.")
        out.append(DistractorSession(
            id=f"d{i:03d}",
            summary=f"Unrelated homelab upkeep session {i:03d}.",
            lines=lines))
    return out


# ------------------------------------------------------------------- generation

def generate(seed: int = GENERATOR_SEED_DEFAULT):
    """All 40 storylines + world files + distractor pool for one seed."""
    pools = CanaryPools(seed)
    storylines = []
    for category in range(1, 9):
        for variant in range(5):
            storylines.append(build_storyline(category, variant, seed, pools))
    distractors = build_distractors(seed)
    return storylines, distractors


def write_tree(out_dir, seed: int = GENERATOR_SEED_DEFAULT):
    """Emit tasks/<id>/storyline.toml + world files + tasks/distractors.toml."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    storylines, distractors = generate(seed)
    for s, world in storylines:
        d = out / s.id
        (d / "world").mkdir(parents=True, exist_ok=True)
        (d / "storyline.toml").write_text(storyline_to_toml(s), encoding="utf-8")
        for name, content in sorted(world.items()):
            (d / "world" / name).write_text(content, encoding="utf-8")
    (out / "distractors.toml").write_text(distractors_to_toml(distractors), encoding="utf-8")
    return [s for s, _ in storylines]


# -------------------------------------------------------------- run-seed remap

def remap_canaries(storylines: list[Storyline], run_seed: int) -> list[Storyline]:
    """Re-draw every canary value for a run seed (AC #2: re-drawn per seed).

    The mapping is deterministic in (committed canary order, run_seed); structure,
    prompts, and non-canary text are unchanged. Returns new Storyline objects.
    """
    pools = CanaryPools(10_000 + run_seed)
    originals = {f.canary for s in storylines for f in s.facts}
    mapping: dict[str, str] = {}
    for s in storylines:
        for f in s.facts:
            if f.canary not in mapping:
                new = pools.draw(f.canary_type)
                # keep run-seed canaries disjoint from the committed set and
                # from each other (pools are without-replacement already)
                while new in originals:
                    new = pools.draw(f.canary_type)
                mapping[f.canary] = new

    def sub(text: str) -> str:
        for old, new in mapping.items():
            if old in text:
                text = text.replace(old, new)
        return text

    out = []
    for s in storylines:
        ns = Storyline(id=s.id, category=s.category, seed=run_seed,
                       session_profile=s.session_profile, world_dir=s.world_dir,
                       sessions=[Session(x.index, x.kind, x.summary) for x in s.sessions])
        ns.facts = [FactEvent(key=f.key, kind=f.kind, text=sub(f.text),
                              canary=mapping[f.canary], session=f.session,
                              canary_type=f.canary_type, near_miss=f.near_miss,
                              supersedes=mapping.get(f.supersedes, ""))
                    for f in s.facts]
        ns.probes = [Probe(id=p.id, session=p.session, prompt=p.prompt,
                           gold=mapping.get(p.gold, p.gold), fact_keys=list(p.fact_keys),
                           depth=p.depth, unknown_unknown=p.unknown_unknown, kind=p.kind,
                           canary_type=p.canary_type, stale=mapping.get(p.stale, p.stale),
                           compliance_rule=p.compliance_rule)
                     for p in s.probes]
        out.append(ns)
    return out
