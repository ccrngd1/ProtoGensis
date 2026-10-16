"""Ambiguity queue tests (AC #17): one item per undecidable
(clause, action-class) pair, affected summed, deterministic ids, clause_ref
pointing at a policy clause, deferred_authorization restricted to research
§3.2. SYNTHETIC data only."""

from policygate import amend, ambiguity

RULES = [
    {"id": "SYN-PRE-01", "type": "PRECONDITION", "predicate": "cc_authorized",
     "params": {}, "tools": ["cron.disable", "cron.edit", "file.edit"],
     "subjects": ["*"],
     "clause_ref": {"file": "global/BASE-AGENTS.md", "commit": "aaaaaaaa0000",
                    "line": 7}},
    {"id": "SYN-FBD-03", "type": "FORBIDDEN", "predicate": "quiet_hours_utc",
     "params": {"start": 0, "end": 8}, "tools": ["cron.edit", "cron.disable"],
     "subjects": ["*"],
     "clause_ref": {"file": "global/BASE-AGENTS.md", "commit": "aaaaaaaa0000",
                    "line": 13}},
]


def _action(vtool="cron.edit", ts="2026-05-02T01:00", principal="cron",
            text="execute the validated queue item", hour=1, infra=True,
            auth=None, key="k1"):
    return {"agent": "synthetic-agent", "ts": ts, "vtool": vtool,
            "principal": principal, "cc_text": text, "hour": hour,
            "infra": infra, "action_key": key,
            "readings_auth": auth or {"strict": False, "plan": False,
                                      "lenient": False}}


def test_one_item_per_kind_from_fixtures():
    resolve_report = [
        {"id": "SYN-PRE-01", "outcome": "SUBJECT_UNDECIDED",
         "class": "subject-scope", "detail": "x"},
        {"id": "SYN-PRE-01~SYN-FBD-03", "outcome": "CONFLICT",
         "class": "contradiction", "detail": "x vs y"},
    ]
    actions = [
        _action(vtool="cron.disable", ts="2026-05-03T14:00",
                principal="cc_direct", text="yes", hour=14,
                auth={"strict": False, "plan": True, "lenient": True}, key="kA"),
        _action(key="kB"),
    ]
    items = ambiguity.generate(actions, resolve_report, rules=RULES)
    kinds = {it["kind"] for it in items}
    assert kinds == {"subject_scope", "conflict", "plan_reading",
                     "deferred_authorization", "temporal_scope"}


def test_collapse_to_clause_action_class_pair():
    # three cron-family actions with strict != plan -> ONE plan_reading item,
    # affected.strict summed, every action_key kept as evidence
    actions = [
        _action(vtool="cron.edit", principal="cc_direct", text="yes", hour=14,
                ts=f"2026-05-0{i}T14:00",
                auth={"strict": False, "plan": True, "lenient": True},
                key=f"k{i}")
        for i in (1, 2, 3)
    ]
    items = ambiguity.generate(actions, [], rules=RULES)
    plan = [it for it in items if it["kind"] == "plan_reading"]
    assert len(plan) == 1
    it = plan[0]
    assert it["action_class"] == "cron.*"
    assert it["affected"] == {"strict": 3, "plan": 0, "lenient": 0}
    assert sorted(it["action_keys"]) == ["k1", "k2", "k3"]
    # clause_ref names the POLICY CLAUSE file@commit:line, not an action
    assert it["clause_ref"] == "global/BASE-AGENTS.md@aaaaaaaa:7"


def test_distinct_action_classes_stay_distinct():
    actions = [
        _action(vtool="cron.edit", principal="cc_direct", text="yes", hour=14,
                auth={"strict": False, "plan": True, "lenient": True}, key="k1"),
        _action(vtool="file.edit", principal="cc_direct", text="yes", hour=14,
                infra=False,
                auth={"strict": False, "plan": True, "lenient": True}, key="k2"),
    ]
    items = ambiguity.generate(actions, [], rules=RULES)
    plan = [it for it in items if it["kind"] == "plan_reading"]
    assert {it["action_class"] for it in plan} == {"cron.*", "file.edit"}


def test_deterministic_ids():
    actions = [_action(key="k1")]
    a = ambiguity.generate(actions, [], rules=RULES)
    b = ambiguity.generate(actions, [], rules=RULES)
    assert [it["id"] for it in a] == [it["id"] for it in b]
    assert all(it["id"].startswith("AMB-") for it in a)


def test_deferred_authorization_research_3_2_only():
    # cron trigger WITHOUT a queue reference -> NOT deferred_authorization
    plain_cron = _action(text="[cron: nightly] scheduled maintenance", key="k1")
    # cron queue reference WITH provenance -> NOT deferred_authorization
    with_prov = _action(text="run the queue item approved-by CC temple-item 12",
                        key="k2")
    # non-cron principal mentioning a queue -> NOT deferred_authorization
    human = _action(principal="cc_direct", text="clear the queue please",
                    key="k3")
    # the research §3.2 shape: cron + queue/validated + no provenance
    deferred = _action(text="Execute it. It was already validated when queued",
                       key="k4")
    items = ambiguity.generate([plain_cron, with_prov, human, deferred], [],
                               rules=RULES)
    defs = [it for it in items if it["kind"] == "deferred_authorization"]
    assert len(defs) == 1
    assert defs[0]["action_keys"] == ["k4"]
    assert defs[0]["affected"] == {"strict": 1, "plan": 1, "lenient": 0}


def test_no_item_without_binding_clause():
    # no gating rule binds the vtool -> no clause to point at -> no item
    orphan = _action(vtool="gateway.restart",
                     text="already validated when queued", key="k1")
    items = ambiguity.generate([orphan], [], rules=RULES)
    assert items == []


def test_clause_refs_are_policy_clauses():
    resolve_report = [
        {"id": "SYN-PRE-01", "outcome": "SUBJECT_UNDECIDED",
         "class": "subject-scope", "detail": "x"},
    ]
    actions = [_action(key="k1"),
               _action(vtool="cron.disable", principal="cc_direct", text="yes",
                       hour=14,
                       auth={"strict": False, "plan": True, "lenient": True},
                       key="k2")]
    items = ambiguity.generate(actions, resolve_report, rules=RULES)
    for it in items:
        # file@commit:line form everywhere a source clause exists
        assert "@" in it["clause_ref"], it
        assert ":" in it["clause_ref"], it
        # never an action-shaped ref (agent@ts:vtool)
        assert not it["clause_ref"].startswith("synthetic-agent@"), it


def test_by_kind_only_counts():
    counts = ambiguity.generate(
        [], [{"id": "SYN-PRE-01", "outcome": "SUBJECT_UNDECIDED",
              "class": "subject-scope", "detail": "x"}],
        by_kind_only=True, rules=RULES)
    assert counts == {"subject_scope": 1}


def test_amend_overlay_not_written_to_repo(tmp_path):
    import shutil
    from pathlib import Path
    src = Path(__file__).parent.parent / "fixtures" / "amend"
    run = tmp_path / "run"
    shutil.copytree(src / "run", run)
    out = tmp_path / "out"
    delta = amend.amend_cmd(str(run), str(src / "answers.toml"), str(out))
    assert delta["overlay_written_to_policy_repo"] is False
    assert delta["items_closed"] == 2
    assert sorted(delta["before"].keys()) == ["lenient", "plan", "strict"]
    # strict blocked 8 - (2 + 1) = 5
    assert delta["after"]["strict"] == 5
    assert (out / "delta.json").exists()
