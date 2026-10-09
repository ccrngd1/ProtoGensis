"""AC #2 storyline tests: determinism, validator catches planted violations,
committed tasks/ validates clean."""

import hashlib
from pathlib import Path

import pytest

from memdoc.tasks.generate import generate, remap_canaries, write_tree
from memdoc.tasks.schema import load_all, load_storyline, storyline_to_toml
from memdoc.tasks.validate import min_uu_overlap, validate

TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"


def _tree_hash(d):
    h = hashlib.sha256()
    for p in sorted(Path(d).rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(d)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def test_generator_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    write_tree(a, 41)
    write_tree(b, 41)
    assert _tree_hash(a) == _tree_hash(b)


def test_committed_tasks_match_generator(tmp_path):
    write_tree(tmp_path / "regen", 41)
    assert _tree_hash(TASKS_DIR) == _tree_hash(tmp_path / "regen")


def test_committed_tasks_validate_clean():
    assert validate(TASKS_DIR) == []


def test_suite_shape():
    storylines = load_all(TASKS_DIR)
    assert len(storylines) == 40
    cats = {}
    for s in storylines:
        cats[s.category] = cats.get(s.category, 0) + 1
    assert cats == {c: 5 for c in range(1, 9)}


def test_unknown_unknown_overlap_is_zero():
    assert min_uu_overlap(load_all(TASKS_DIR)) == 0


def test_validator_catches_planted_canary_in_world(tmp_path):
    write_tree(tmp_path, 41)
    s = load_storyline(tmp_path / "c2s0" / "storyline.toml")
    canary = s.facts[0].canary
    world_file = tmp_path / "c2s0" / "world" / "notes.md"
    world_file.write_text(world_file.read_text() + f"\nleak: {canary}\n")
    assert any("recoverable from world" in v for v in validate(tmp_path))


def test_validator_catches_same_session_probe(tmp_path):
    write_tree(tmp_path, 41)
    p = tmp_path / "c3s0" / "storyline.toml"
    text = p.read_text()
    # move the first probe into the fact's session
    text = text.replace("session = 4", "session = 1", 1)
    p.write_text(text)
    assert any("not after fact session" in v for v in validate(tmp_path))


def test_validator_catches_missing_abstention_distractor(tmp_path):
    write_tree(tmp_path, 41)
    p = tmp_path / "c7s0" / "storyline.toml"
    text = p.read_text().replace("near_miss = true", "near_miss = false")
    p.write_text(text)
    assert any("no near-miss distractor" in v for v in validate(tmp_path))


def test_validator_catches_missing_unknown_unknown(tmp_path):
    write_tree(tmp_path, 41)
    p = tmp_path / "c6s0" / "storyline.toml"
    text = p.read_text().replace("unknown_unknown = true", "unknown_unknown = false")
    p.write_text(text)
    assert any("no unknown-unknown probe" in v for v in validate(tmp_path))


def test_validator_catches_uu_keyword_overlap(tmp_path):
    write_tree(tmp_path, 41)
    p = tmp_path / "c6s0" / "storyline.toml"
    s = load_storyline(p)
    uu = next(x for x in s.probes if x.unknown_unknown)
    fact = next(f for f in s.facts if f.key in uu.fact_keys)
    kw = sorted(set(fact.text.lower().split()) - {"the", "a"})[0].strip(".,;:")
    text = p.read_text().replace(uu.prompt, uu.prompt + " " + kw)
    p.write_text(text)
    assert any("keyword overlap" in v for v in validate(tmp_path))


def test_validator_catches_too_few_enumeration_facts(tmp_path):
    write_tree(tmp_path, 41)
    for i in range(5):
        p = tmp_path / f"c5s{i}" / "storyline.toml"
        p.write_text(p.read_text().replace('kind = "enumerate"', 'kind = "introduce"'))
    assert any("enumeration facts" in v for v in validate(tmp_path))


def test_canaries_redrawn_per_seed():
    storylines = [s for s, _ in generate(41)[0]]
    remapped = remap_canaries(storylines, run_seed=1)
    orig = {f.canary for s in storylines for f in s.facts}
    new = {f.canary for s in remapped for f in s.facts}
    assert orig.isdisjoint(new)
    # structure unchanged
    assert [s.id for s in remapped] == [s.id for s in storylines]
    for a, b in zip(storylines, remapped):
        assert [p.prompt for p in a.probes] == [p.prompt for p in b.probes]
        # supersedes links are remapped consistently
        for fa, fb in zip(a.facts, b.facts):
            assert (fa.supersedes == "") == (fb.supersedes == "")


def test_toml_roundtrip(tmp_path):
    storylines = [s for s, _ in generate(41)[0]]
    s = storylines[0]
    f = tmp_path / "x.toml"
    f.write_text(storyline_to_toml(s))
    s2 = load_storyline(f)
    assert s2.id == s.id and len(s2.facts) == len(s.facts) and len(s2.probes) == len(s.probes)
    assert s2.facts[0].canary == s.facts[0].canary
