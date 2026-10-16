"""Version-pinned replay tests (AC #14) on the synthetic policy repo.

An action before the rule's commit -> NO_RULE_IN_FORCE; after -> BLOCK; after
the rule's removal -> ALLOW with the removal listed; a platform rule with
effective_from "unknown" -> VERSION_UNKNOWN; a per-version clause change keeps
one rule per version; --retroactive adds the labeled COUNTERFACTUAL section.
Plus an end-to-end CLI run on a synthetic legacy archive straddling the
synthetic commits. SYNTHETIC: no real data anywhere.
"""

import hashlib
import json
import os
import subprocess
import sys

import pytest

from policygate import ambiguity as ambiguity_mod
from policygate import cli, pinning, replay, resolve
from policygate.parse import normalize_text

REPO = os.path.dirname(os.path.dirname(__file__))
FIX = os.path.join(REPO, "tests", "fixtures")
BUNDLE_TOML = os.path.join(REPO, "fixtures", "bundle.synthetic.toml")

QH_CLAUSE = "No autonomous infra work between midnight and 08:00 UTC."
LEG_CLAUSE = "Never invoke the legacy deploy script directly."


def _sha(text):
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def _candidates():
    """Synthetic candidates against the make_policy_repo bundle."""
    return [
        # quiet-hours clause enters at commit 2 (2026-02-20)
        {"id": "QH-FBD-01", "polarity": "block_when_true",
         "predicate": "quiet_hours_utc", "params": {"start": 0, "end": 8},
         "tools": ["cron.edit"], "subjects": ["*"], "class": "temporal",
         "origin": "builder", "src": {"file": "global/BASE-AGENTS.md"},
         "clause_ref": {"file": "global/BASE-AGENTS.md",
                        "clause_sha256": _sha(QH_CLAUSE)[:16]}},
        # legacy-tooling clause exists commits 1-2, removed at commit 3 (2026-03-15)
        {"id": "LEG-FBD-02", "polarity": "block_when_true",
         "predicate": "principal_is", "params": {"principal": "cron"},
         "tools": ["service.restart"], "subjects": ["*"], "class": "gateable",
         "origin": "builder", "src": {"file": "global/BASE-AGENTS.md"},
         "clause_ref": {"file": "global/BASE-AGENTS.md",
                        "clause_sha256": _sha(LEG_CLAUSE)[:16]}},
        # platform rule: effective_from "unknown" inherited by id from
        # config/platform_rules.toml via the bundle
        {"id": "PLAT-FBD-04", "polarity": "block_until_true",
         "predicate": "cc_authorized", "params": {"action_class": "gateway"},
         "tools": ["gateway.restart"], "subjects": ["*"], "class": "gateable",
         "origin": "builder", "clause_ref": {"builtin": "platform system prompt"}},
        # obligation class: NEVER a gate (AC #17e); end-of-trace report section
        {"id": "OBL-PRE-05", "polarity": "block_until_true",
         "predicate": "cc_authorized", "params": {"action_class": "memory.update"},
         "tools": ["file.edit"], "subjects": ["*"], "class": "obligation",
         "origin": "builder", "clause_ref": {"builtin": "memory update obligation"}},
        # ambiguous class: never a gate; becomes an unclassified_clause item
        {"id": "AMB-FBD-06", "polarity": "block_when_true",
         "predicate": "path_in", "params": {"globs": ["*.md"]},
         "tools": ["file.edit"], "subjects": ["*"], "class": "ambiguous",
         "origin": "builder", "src": {"file": "workspace/AGENTS.md"},
         "clause_ref": {"file": "workspace/AGENTS.md", "clause_sha256": "0" * 16}},
    ]


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    target = tmp_path_factory.mktemp("pinrepo") / "repo"
    subprocess.run([sys.executable, os.path.join(FIX, "make_policy_repo.py"),
                    str(target)], check=True, capture_output=True)
    return str(target)


@pytest.fixture(scope="module")
def pin(repo):
    kept, _ = resolve.resolve(_candidates())
    return pinning.PinnedPolicy(repo, BUNDLE_TOML, kept), kept


def _rule(kept, rid):
    return next(r for r in kept if r["id"] == rid)


def test_status_before_after_removed_unknown(pin):
    p, kept = pin
    qh, leg, plat = (_rule(kept, r) for r in ("QH-FBD-01", "LEG-FBD-02", "PLAT-FBD-04"))
    # before the quiet-hours commit -> later; after -> in force
    assert p.status_at(qh, "2026-02-10T01:00:00Z") == "later"
    assert p.status_at(qh, "2026-03-01T01:00:00Z") == "in_force"
    # before any commit at all -> later
    assert p.status_at(leg, "2026-01-15T12:00:00Z") == "later"
    # in force commits 1-2; removed from commit 3
    assert p.status_at(leg, "2026-03-01T12:00:00Z") == "in_force"
    assert p.status_at(leg, "2026-04-01T12:00:00Z") == "removed"
    # platform rule with effective_from "unknown"
    assert p.status_at(plat, "2026-03-01T12:00:00Z") == "unknown"


def _fixture_events(tmp_path, events):
    f = tmp_path / "events.jsonl"
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"synthetic": True}) + "\n")
        for e in events:
            fh.write(json.dumps(e) + "\n")
    return str(f)


def _cron_turn(ts):
    return {"type": "turn", "principal": "cron", "provenance_source": "heuristic",
            "cc_text": None, "prev_assistant": "", "agent": "synthetic-agent",
            "text": "[cron: nightly] scheduled maintenance", "ts": ts}


def _exec(ts, command):
    return {"type": "call", "tool": "exec", "args": {"command": command},
            "ts": ts, "agent": "synthetic-agent"}


EVENTS = [
    # quiet-hours cron.edit BEFORE the rule's commit -> NO_RULE_IN_FORCE
    _cron_turn("2026-02-10T01:00:00Z"),
    _exec("2026-02-10T01:00:00Z", "openclaw cron edit job-synth-a"),
    # same action AFTER the commit -> BLOCK
    _cron_turn("2026-03-01T01:00:00Z"),
    _exec("2026-03-01T01:00:00Z", "openclaw cron edit job-synth-b"),
    # legacy rule in force -> BLOCK
    _cron_turn("2026-03-01T12:00:00Z"),
    _exec("2026-03-01T12:00:00Z", "systemctl restart synthetic-unit"),
    # after its removal -> ALLOW, removal listed
    _cron_turn("2026-04-01T12:00:00Z"),
    _exec("2026-04-01T12:00:00Z", "systemctl restart synthetic-unit"),
    # platform rule "unknown" is the only firing rule -> VERSION_UNKNOWN
    _cron_turn("2026-03-01T12:30:00Z"),
    _exec("2026-03-01T12:30:00Z", "openclaw gateway restart"),
    # obligation-class candidate on file.edit: fires the obligations section,
    # NEVER a BLOCK (AC #17e; the phase-3 host finding)
    {"type": "call", "tool": "edit", "ts": "2026-03-01T13:00:00Z",
     "agent": "synthetic-agent",
     "args": {"path": "workspace/MEMORY.md", "oldText": "Do NOT disable x.\nkeep",
              "newText": "keep"}},
]


@pytest.fixture(scope="module")
def pinned_run(repo, pin, tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("pinrun")
    p, kept = pin
    path = _fixture_events(tmp_path, EVENTS)
    agg, actions = replay.replay_stream("fixture", path, "pinned",
                                        pinned_rules=kept, pin=p)
    return agg, actions


def test_verdict_classes_strict(pinned_run):
    agg, actions = pinned_run
    assert agg["verdict_classes"]["strict"] == {
        "ALLOW": 2, "BLOCK": 2, "NO_RULE_IN_FORCE": 1, "VERSION_UNKNOWN": 1}
    # infra-only verdict classes exclude the file.edit (ALLOW, no gating rule
    # binds it): 5 infra actions, not 6 (phase 5; feeds the
    # no-rule-in-force-infra claim)
    assert agg["verdict_classes_infra"]["strict"] == {
        "ALLOW": 1, "BLOCK": 2, "NO_RULE_IN_FORCE": 1, "VERSION_UNKNOWN": 1}
    for r, vc in agg["verdict_classes"].items():
        infra = agg["verdict_classes_infra"][r]
        assert sum(infra.values()) == agg["normalizer"]["infra_actions"]
        assert all(infra[c] <= vc[c] for c in vc)
    by = {(a["ts"], a["vtool"]): a for a in actions}
    assert by[("2026-02-10T01:00", "cron.edit")]["verdicts"]["strict"] == "NO_RULE_IN_FORCE"
    blocked = by[("2026-03-01T01:00", "cron.edit")]
    assert blocked["verdicts"]["strict"] == "BLOCK"
    assert blocked["fired_by_reading"]["strict"] == ["QH-FBD-01"]
    assert by[("2026-03-01T12:00", "service.restart")]["verdicts"]["strict"] == "BLOCK"
    removed = by[("2026-04-01T12:00", "service.restart")]
    assert removed["verdicts"]["strict"] == "ALLOW"
    assert removed["retro"]["strict"]["removed"] == ["LEG-FBD-02"]
    assert by[("2026-03-01T12:30", "gateway.restart")]["verdicts"]["strict"] == "VERSION_UNKNOWN"


def test_retroactive_rules_never_violations(pinned_run):
    agg, _ = pinned_run
    rr = agg["retroactive_rules"]
    # the pre-commit quiet-hours fire and the platform-unknown fire are listed,
    # the removal is listed as ALLOW; none of them raise the blocked counts
    assert rr["QH-FBD-01"]["class"] == "NO_RULE_IN_FORCE"
    assert rr["PLAT-FBD-04"]["class"] == "VERSION_UNKNOWN"
    assert rr["LEG-FBD-02"]["class"] == "ALLOW"
    assert agg["readings"]["strict"]["blocked"] == 2
    # aggregate schema completeness (Component Specifications)
    assert agg["rules"]["QH-FBD-01"]["strict"] == 1
    assert isinstance(agg["firing_rates"], list) and agg["firing_rates"]
    for row in agg["firing_rates"]:
        assert set(row) == {"rule", "vtool", "n", "fired", "rate", "flag"}
    assert agg["input_manifest"]["file_count"] == 1
    assert len(agg["input_manifest"]["sha256"]) == 64


def test_obligations_report_not_gate(pinned_run):
    agg, actions = pinned_run
    edit = next(a for a in actions if a["vtool"] == "file.edit")
    # never a BLOCK from a non-gateable class
    assert all(v != "BLOCK" for v in edit["verdicts"].values())
    assert edit["obligations_fired"] == ["OBL-PRE-05"]
    assert agg["obligations"] == {"OBL-PRE-05": 1}
    # the ambiguous-class candidate never fired a BLOCK either
    assert not any("AMB-FBD-06" in a["fired_by_reading"]["strict"] for a in actions)


def test_retroactive_flag_adds_counterfactual(repo, pin, tmp_path):
    p, kept = pin
    path = _fixture_events(tmp_path, EVENTS)
    agg, actions = replay.replay_stream("fixture", path, "pinned",
                                        pinned_rules=kept, pin=p, retroactive=True)
    cf = agg["counterfactual"]
    assert cf["label"] == "COUNTERFACTUAL (retroactive policy; not violations)"
    # every version's rules against every action: both service restarts and the
    # pre-commit cron.edit now fire; the file.edit (no gating rule) does not
    assert cf["readings"]["strict"] == {"blocked": 5, "total": 6}
    # pinned verdicts are unchanged by --retroactive
    assert agg["verdict_classes"]["strict"]["BLOCK"] == 2


def test_ts_missing_never_temporal_never_block(repo, pin, tmp_path):
    """R14: an action with no timestamp is counted in ts_missing and gets
    VERSION_UNKNOWN (not BLOCK) when a rule would otherwise fire."""
    p, kept = pin
    events = [_cron_turn("2026-03-01T12:00:00Z"),
              _exec("", "systemctl restart synthetic-unit")]
    path = _fixture_events(tmp_path, events)
    agg, actions = replay.replay_stream("fixture", path, "pinned",
                                        pinned_rules=kept, pin=p)
    assert agg["ts_missing"] == 1
    assert actions[0]["verdicts"]["strict"] == "VERSION_UNKNOWN"


def test_per_version_clause_change_one_rule_per_version(tmp_path):
    """A clause whose text changes across versions keeps one rule per version
    (per-version candidate overrides); the report lists such rules."""
    repo = tmp_path / "pvrepo"
    repo.mkdir()

    def git(*args, date=None):
        env = dict(os.environ)
        if date:
            env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
        subprocess.run(["git", "-c", "user.name=policygate",
                        "-c", "user.email=policygate@localhost",
                        "-C", str(repo), *args],
                       check=True, capture_output=True, env=env)

    v1 = "# Synthetic policy\n\n## Jobs\n- Never disable the alpha job.\n"
    v2 = "# Synthetic policy\n\n## Jobs\n- Never disable the alpha or beta jobs.\n"
    git("init", "-q", "-b", "main")
    (repo / "policy.md").write_text(v1)
    git("add", "-A")
    git("commit", "-q", "-m", "v1", date="2026-01-01T00:00:00Z")
    (repo / "policy.md").write_text(v2)
    git("add", "-A")
    git("commit", "-q", "-m", "v2", date="2026-02-01T00:00:00Z")

    bundle_toml = tmp_path / "bundle.toml"
    bundle_toml.write_text(
        '[[source]]\npath = "policy.md"\nkind = "base"\nsubjects = ["*"]\nprecedence = 1\n')

    def cand(rid, clause, protected):
        return {"id": rid, "polarity": "block_when_true",
                "predicate": "target_protected", "params": {},
                "data": {"protected": protected},
                "tools": ["cron.disable"], "subjects": ["*"], "class": "gateable",
                "origin": "builder", "version_of": "PV-FBD-10",
                "src": {"file": "policy.md"},
                "clause_ref": {"file": "policy.md", "clause_sha256": _sha(clause)[:16]}}

    kept, _ = resolve.resolve([
        cand("PV-FBD-11", "Never disable the alpha job.", ["job-alpha"]),
        cand("PV-FBD-12", "Never disable the alpha or beta jobs.",
             ["job-alpha", "job-beta"]),
    ])
    p = pinning.PinnedPolicy(str(repo), str(bundle_toml), kept)
    assert p.per_version_groups() == {"PV-FBD-10": ["PV-FBD-11", "PV-FBD-12"]}
    r11, r12 = _rule(kept, "PV-FBD-11"), _rule(kept, "PV-FBD-12")
    # each version's rule is in force only while its text is in the bundle
    assert p.status_at(r11, "2026-01-15T12:00:00Z") == "in_force"
    assert p.status_at(r12, "2026-01-15T12:00:00Z") == "later"
    assert p.status_at(r11, "2026-02-15T12:00:00Z") == "removed"
    assert p.status_at(r12, "2026-02-15T12:00:00Z") == "in_force"
    # the per-version override is honoured: job-beta blocks only under v2
    events = [_cron_turn("2026-01-15T12:00:00Z"),
              _exec("2026-01-15T12:00:00Z", "openclaw cron disable job-beta"),
              _cron_turn("2026-02-15T12:00:00Z"),
              _exec("2026-02-15T12:00:00Z", "openclaw cron disable job-beta")]
    path = _fixture_events(tmp_path, events)
    agg, actions = replay.replay_stream("fixture", path, "pinned",
                                        pinned_rules=kept, pin=p)
    assert actions[0]["verdicts"]["strict"] == "NO_RULE_IN_FORCE"
    assert actions[1]["verdicts"]["strict"] == "BLOCK"
    assert actions[1]["fired_by_reading"]["strict"] == ["PV-FBD-12"]


def test_ambiguity_items_counts_by_kind(pinned_run, repo, pin, tmp_path):
    p, kept = pin
    ambiguous = [c for c in _candidates() if c.get("class") == "ambiguous"]
    _, actions = pinned_run
    items = ambiguity_mod.generate(actions, [], ambiguous_rules=ambiguous,
                                   rules=kept)
    counts = ambiguity_mod.counts_by_kind(items)
    assert counts["unclassified_clause"] == 1
    # the two 01:00Z cron edits COLLAPSE into one (clause, cron.*) item
    # with affected.plan == 2 (AC #17: one item per pair, counts summed)
    assert counts["temporal_scope"] == 1
    temp = next(it for it in items if it["kind"] == "temporal_scope")
    assert temp["action_class"] == "cron.*"
    assert temp["affected"]["plan"] == 2
    # the clause_ref points at the quiet-hours POLICY CLAUSE, not an action
    assert temp["clause_ref"].startswith("global/BASE-AGENTS.md@")


# ---- end-to-end CLI test on a synthetic legacy archive (AC #14 Verify) ----

ARCHIVE_LINES = [
    {"timestamp": "2026-02-10T01:00:00Z",
     "message": {"role": "user", "content": "[cron: nightly] cron job scheduled maintenance"}},
    {"timestamp": "2026-02-10T01:00:05Z",
     "message": {"role": "assistant", "content": [
         {"type": "toolCall", "name": "exec",
          "arguments": {"command": "openclaw cron edit job-synth-a"}}]}},
    {"timestamp": "2026-03-01T01:00:00Z",
     "message": {"role": "user", "content": "[cron: nightly] cron job scheduled maintenance"}},
    {"timestamp": "2026-03-01T01:00:05Z",
     "message": {"role": "assistant", "content": [
         {"type": "toolCall", "name": "exec",
          "arguments": {"command": "openclaw cron edit job-synth-b"}},
         # two actions from ONE segment-identical pair at the same ts:
         # the occurrence index keeps their action_keys distinct (AC #19)
         {"type": "toolCall", "name": "exec",
          "arguments": {"command": "openclaw cron edit job-synth-b"}}]}},
    {"timestamp": "2026-03-01T12:00:00Z",
     "message": {"role": "user", "content": "[cron: nightly] cron job scheduled maintenance"}},
    {"timestamp": "2026-03-01T12:00:05Z",
     "message": {"role": "assistant", "content": [
         {"type": "toolCall", "name": "exec",
          "arguments": {"command": "systemctl restart synthetic-unit"}},
         {"type": "toolCall", "name": "exec",
          "arguments": {"command": "openclaw gateway restart"}}]}},
    {"timestamp": "2026-04-01T12:00:00Z",
     "message": {"role": "user", "content": "[cron: nightly] cron job scheduled maintenance"}},
    {"timestamp": "2026-04-01T12:00:05Z",
     "message": {"role": "assistant", "content": [
         {"type": "toolCall", "name": "exec",
          "arguments": {"command": "systemctl restart synthetic-unit"}}]}},
]


@pytest.fixture(scope="module")
def archive(tmp_path_factory):
    d = tmp_path_factory.mktemp("pinarchive") / "agents"
    arch = d / "synthetic-agent" / "session-sqlite-import-archive"
    arch.mkdir(parents=True)
    with open(arch / "s1.jsonl.imported-1", "w", encoding="utf-8") as f:
        for line in ARCHIVE_LINES:
            f.write(json.dumps(line) + "\n")
    return str(d)


@pytest.fixture(scope="module")
def cli_runs(repo, archive, tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("pinout")
    cands = tmp_path / "cands.json"
    cands.write_text(json.dumps({"synthetic": True, "candidates": _candidates()}))
    outs = {}
    for name, extra in (("pinned", []), ("retro", ["--retroactive"])):
        out = tmp_path / f"run-{name}"
        rc = cli.main(["replay", "--source", "legacy-archive", "--path", archive,
                       "--root", repo, "--bundle", BUNDLE_TOML,
                       "--candidates", str(cands), "--profile", "pinned",
                       "--format", "json", "--out", str(out), *extra])
        assert rc == 0
        outs[name] = out
    return outs


def test_e2e_verdict_classes_and_manifest(cli_runs):
    out = cli_runs["pinned"]
    agg = json.load(open(out / "aggregates.json"))
    assert agg["verdict_classes"]["strict"] == {
        "ALLOW": 1, "BLOCK": 3, "NO_RULE_IN_FORCE": 1, "VERSION_UNKNOWN": 1}
    # all 6 archive actions are infra, so the infra-only split is identical
    assert agg["verdict_classes_infra"] == agg["verdict_classes"]
    manifest = json.load(open(out / "manifest.json"))
    assert len(manifest["bundle_commits"]["global/BASE-AGENTS.md"]) == 3
    assert len(manifest["candidates_sha256"]) == 64
    assert manifest["input_manifest"]["file_count"] == 1
    assert len(manifest["input_manifest"]["sha256"]) == 64
    assert len(manifest["readings_sha256"]) == 64
    assert len(manifest["vtools_sha256"]) == 64
    # aggregates carry the same input manifest (AC #18, results/ copy)
    assert agg["input_manifest"] == manifest["input_manifest"]
    # ambiguity: count by kind in aggregates, full items in the run dir only
    amb = json.load(open(out / "ambiguity.json"))
    assert agg["ambiguity_items"] == ambiguity_mod.counts_by_kind(amb["items"])
    assert agg["ambiguity_items"]["unclassified_clause"] == 1


def test_e2e_action_keys_distinct_and_segment_based(cli_runs):
    out = cli_runs["pinned"]
    recs = [json.loads(l) for l in open(out / "actions.jsonl", encoding="utf-8")]
    keys = [r["action_key"] for r in recs]
    assert len(keys) == len(set(keys)) == 6
    # the key is sha256(agent|ts|vtool|segment) over the full segment text
    first = next(r for r in recs if r["ts"] == "2026-02-10T01:00")
    want = replay._action_key("synthetic-agent", "2026-02-10T01:00", "cron.edit",
                              "openclaw cron edit job-synth-a")
    assert first["action_key"] == want


def test_e2e_retroactive_differs(cli_runs):
    pinned = json.load(open(cli_runs["pinned"] / "aggregates.json"))
    retro = json.load(open(cli_runs["retro"] / "aggregates.json"))
    assert "counterfactual" not in pinned
    assert retro["counterfactual"]["label"] == \
        "COUNTERFACTUAL (retroactive policy; not violations)"
    assert retro["counterfactual"]["readings"]["strict"]["blocked"] > \
        retro["verdict_classes"]["strict"]["BLOCK"] - 1
    # the pinned verdicts themselves are identical across the two runs
    assert retro["verdict_classes"] == pinned["verdict_classes"]


def test_e2e_results_lint_accepts_aggregates(cli_runs, tmp_path):
    """results lint accepts the full pinned aggregates: input_manifest (AC #18),
    ambiguity_items by kind, retroactive_rules, and the labeled COUNTERFACTUAL
    heading in the --retroactive aggregates."""
    from policygate import results_lint
    import shutil
    shutil.copy(cli_runs["pinned"] / "aggregates.json",
                tmp_path / "replay-pinned-2026-01-01.json")
    shutil.copy(cli_runs["retro"] / "aggregates.json",
                tmp_path / "replay-pinned-2026-01-02.json")
    ok, lines = results_lint.lint_dir(str(tmp_path))
    assert ok, lines
    agg = json.load(open(tmp_path / "replay-pinned-2026-01-01.json"))
    assert set(agg["input_manifest"]) == {"file_count", "sha256"}


def test_pinned_requires_root_and_bundle(archive, tmp_path):
    rc = cli.main(["replay", "--source", "legacy-archive", "--path", archive,
                   "--candidates", "nope.json", "--profile", "pinned",
                   "--format", "json", "--out", str(tmp_path / "x")])
    assert rc == 2
