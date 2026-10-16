"""Replay: pinning, verdict classes, profiles, run dir (AC #14, #18). DETERMINISTIC.

Two profiles:
  spike-parity: spike 1's hand-compiled rules, spike principal heuristic, three
    readings, NO pinning, NO consumption. Reproduces spike_replay.out. Blocked
    under a reading = infra action not cc_authorized under that reading (exactly
    the spike's semantics).
  pinned: real-bundle candidates, version pinning (a rule is in force at t iff
    its clause hash is present in the bundle resolved at t; platform rules by
    effective_from), consumption, full principal classes, verdict classes
    ALLOW | BLOCK | NO_RULE_IN_FORCE | VERSION_UNKNOWN per reading. PolicyGate's
    own results. Non-gateable candidate classes never BLOCK (AC #17e):
    obligation -> obligations report section, ambiguous -> unclassified_clause
    ambiguity items, text-only -> not evaluated.

Per-action detail (with spike-style redact) goes only to local/ or tmp --out
dirs; results/ copies hold aggregates.json only. actions.jsonl additionally
carries a label_context object (local only) for hand-labelling in phase 2.
"""

import hashlib
import json
import os
import tomllib

from . import ambiguity as ambiguity_mod
from . import check as check_mod
from . import facts as facts_mod
from . import normalize as norm
from . import pinning as pinning_mod
from . import readings as readings_mod
from . import report as report_mod
from . import rules as rules_mod
from . import vtools as vtools_mod
from .adapters import legacy_jsonl, trajectory

CONFIG_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir, "config"))
PROFILE_DIR = os.path.join(CONFIG_DIR, "profiles")
EXIT_OK, EXIT_USAGE = 0, 2
VERDICT_CLASSES = ["ALLOW", "BLOCK", "NO_RULE_IN_FORCE", "VERSION_UNKNOWN"]
# predicates whose rules carry an authorization verdict per reading
AUTH_PREDICATES = {"cc_authorized", "confirmation_fresh"}


class ReplayInvariantError(AssertionError):
    """A BLOCK verdict with an empty fired list (phase 2a Bug 1 invariant)."""


def check_verdict_invariant(rec):
    """A verdict of BLOCK with an empty fired list is impossible."""
    if rec.get("verdict_class") == "BLOCK" and not rec.get("fired"):
        raise ReplayInvariantError(
            f"BLOCK with empty fired list: {rec.get('vtool')} at {rec.get('ts')}")
    by_reading = rec.get("fired_by_reading") or {}
    for r, v in (rec.get("readings") or {}).items():
        if v == "BLOCK" and not by_reading.get(r):
            raise ReplayInvariantError(
                f"reading {r} BLOCK with empty fired list: {rec.get('vtool')}")


def _sha_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _sha_candidates(path):
    """sha256 of a candidates file, or of the sorted per-file hashes of a dir."""
    if os.path.isdir(path):
        parts = []
        for f in sorted(os.listdir(path)):
            if f.endswith(".json"):
                parts.append(_sha_file(os.path.join(path, f)))
        return hashlib.sha256("".join(parts).encode()).hexdigest()
    return _sha_file(path)


def _load_profile_rules(profile):
    path = os.path.join(PROFILE_DIR, f"{profile.replace('-', '_')}.toml")
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    cands = cfg.get("rule", [])
    kept = []
    for c in cands:
        kept.append(rules_mod.candidate_to_rule(c))
    return cfg, kept, path


def _action_key(agent, ts, vtool, segment, occurrence=0):
    """AC #19: sha256(agent|ts|vtool|segment) over the FULL segment text of the
    action; a deterministic occurrence index disambiguates two actions sharing
    one segment. Profile-independent. occurrence=0 keeps the plain form."""
    base = f"{agent}|{ts}|{vtool}|{segment}"
    if occurrence:
        base += f"|{occurrence}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def input_manifest(source, path):
    """AC #18: {file_count, sha256 over the sorted (relpath, size) list}."""
    if source == "legacy-archive":
        files = legacy_jsonl.iter_files(path)
        base = path
    elif source == "trajectory":
        p = os.path.join(path, "events.jsonl") if os.path.isdir(path) else path
        files, base = [p], os.path.dirname(p)
    else:
        files, base = [path], os.path.dirname(os.path.abspath(path))
    entries = sorted((os.path.relpath(f, base), os.path.getsize(f)) for f in files)
    digest = hashlib.sha256(
        json.dumps(entries, sort_keys=True).encode("utf-8")).hexdigest()
    return {"file_count": len(entries), "sha256": digest}


def _iter_events(source, path):
    if source == "legacy-archive":
        yield from legacy_jsonl.read_archive(path)
    elif source == "trajectory":
        yield from trajectory.read_bundle(path)
    elif source == "fixture":
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("//"):
                    rec = json.loads(line)
                    if "synthetic" in rec and "type" not in rec:
                        continue
                    yield rec
    else:
        raise ValueError(source)


def _count_files(source, path):
    if source == "legacy-archive":
        return len(legacy_jsonl.iter_files(path))
    return 1


def _infra_verdicts(vtool, auth, hour, rules):
    """Per-reading verdicts for an infra-mutating action (spike semantics:
    blocked under r = not cc_authorized under r). Returns (verdicts, fired)
    keyed by reading; a BLOCK always names the binding rule(s) that fired."""
    binding = [r for r in rules if vtool in r["tools"]]
    auth_ids = [r["id"] for r in binding
                if r["type"] == "PRECONDITION" and r["predicate"] in AUTH_PREDICATES]
    quiet_ids = []
    if hour is not None:
        for r in binding:
            if r["type"] == "FORBIDDEN" and r["predicate"] == "quiet_hours_utc":
                p = r.get("params") or {}
                start, end = int(p.get("start", 0)), int(p.get("end", 8))
                in_window = (start <= hour < end) if start <= end \
                    else (hour >= start or hour < end)
                if in_window:
                    quiet_ids.append(r["id"])
    verdicts, fired = {}, {}
    for rd in readings_mod.READINGS:
        if not binding:
            # no rule in force binds this vtool: never a bare BLOCK
            verdicts[rd], fired[rd] = "NO_RULE_IN_FORCE", []
            continue
        f = [] if auth[rd] else auth_ids + quiet_ids
        verdicts[rd], fired[rd] = ("BLOCK", f) if f else ("ALLOW", [])
    return verdicts, fired


def _non_infra_verdicts(vtool, call, store, rules):
    """Per-reading verdicts for a non-infra action (e.g. file.edit): evaluated
    ONLY by rules that bind the vtool; with none in force the verdict is
    NO_RULE_IN_FORCE, never a bare BLOCK (phase 2a Bug 1)."""
    binding = [r for r in rules if vtool in r["tools"]]
    if not binding:
        return ({rd: "NO_RULE_IN_FORCE" for rd in readings_mod.READINGS},
                {rd: [] for rd in readings_mod.READINGS})
    verdicts, fired = {}, {}
    for rd in readings_mod.READINGS:
        facts = store.facts_snapshot(rd, vtool, call)
        res = check_mod.check(vtool, call, facts, binding)
        verdicts[rd], fired[rd] = res["verdict"], res["fired"]
    return verdicts, fired


def replay_stream(source, path, profile, help_filter=True, heredoc_skip=True,
                  readings=None, pinned_rules=None, bundle=None, pin=None,
                  retroactive=False):
    """Core replay loop. Returns (aggregates, actions).

    `pin` (a pinning.PinnedPolicy) switches the pinned profile to real
    version-pinned evaluation; without it the pinned profile evaluates the
    given rules unpinned (synthetic in-memory tests)."""
    rd = readings or readings_mod.default()
    store = facts_mod.FactStore(profile, readings=rd)
    schema = vtools_mod.load()
    # vtools whose aggregates feed the INF-rule parity values: exactly the
    # infra_mutating set from config/vtools.toml, in BOTH profiles (Bug 1)
    infra_vtools = {n for n, s in schema.items() if s["infra_mutating"]}
    rules = pinned_rules
    if rules is None:
        _, rules, _ = _load_profile_rules("spike-parity")
    # non-gateable candidate classes never gate (AC #17e)
    routed = pinning_mod.route_rules(rules)
    gating_rules = routed["gating"]
    obligation_rules = routed["obligation"]

    tool_counts = {}
    seg_total = seg_unparsed = seg_nested = 0
    actions = []
    exec_calls = 0
    structured_cron = 0
    ablation_infra = 0

    last_turn_text = ""

    def handle_turn(ev):
        nonlocal last_turn_text
        last_turn_text = ev.get("text") or ""
        store.observe_turn(ev.get("principal", "unknown"), ev.get("provenance_source", "heuristic"),
                           ev.get("cc_text"), ev.get("prev_assistant", ""), agent=ev.get("agent"))

    def record_action(agent, ts, vtool, args, segment, cmd, triggering):
        hour = None
        if len(ts) >= 13 and ts[11:13].isdigit():
            hour = int(ts[11:13])
        call = {"vtool": vtool, "args": args, "ts": ts}
        infra = vtool in infra_vtools
        reading_auth = store.authorization_for(vtool) if infra or pin else None
        rule_rows, counterfactual, obligations_fired = [], None, []
        if pin is not None:
            # real version-pinned evaluation (AC #14), every action
            facts_by = {r: store.facts_snapshot(r, vtool, call)
                        for r in readings_mod.READINGS}
            verdicts, fired, retro, rule_rows = pinning_mod.classify_action(
                pin, vtool, call, facts_by, gating_rules, readings_mod.READINGS)
            if retroactive:
                counterfactual = pinning_mod.counterfactual_fired(
                    vtool, call, facts_by, gating_rules, readings_mod.READINGS)
            # obligations: end-of-trace report section, never a gate
            for ob in obligation_rules:
                if vtool in ob["tools"]:
                    res = check_mod.check(vtool, call, facts_by["strict"], [ob])
                    if res["fired"]:
                        obligations_fired.append(ob["id"])
            # consumption: a write that used a cc_authorized fact consumes it
            if schema.get(vtool, {}).get("is_write"):
                store.consume_authorization(
                    vtool, {r: bool(reading_auth and reading_auth.get(r))
                            for r in readings_mod.READINGS})
            retro_by_reading = retro
        elif infra:
            verdicts, fired = _infra_verdicts(vtool, reading_auth, hour, gating_rules)
            retro_by_reading = None
        else:
            # non-infra writes (e.g. file.edit) never get INF-rule reading
            # verdicts; they are evaluated only by rules that bind them
            reading_auth = None
            verdicts, fired = _non_infra_verdicts(vtool, call, store, gating_rules)
            retro_by_reading = None
        actions.append({
            "agent": agent, "ts": ts[:16], "vtool": vtool, "args": args,
            "principal": store.principal, "provenance_source": "heuristic"
            if source == "legacy-archive" else "typed",
            "cc_text": store.cc_text, "turn_text": last_turn_text,
            "prev_assistant": store.prev_assistant,
            "hour": hour, "cmd": cmd, "segment": segment,
            "infra": infra, "readings_auth": reading_auth,
            "verdicts": verdicts, "fired_by_reading": fired,
            "retro": retro_by_reading, "rule_rows": rule_rows,
            "counterfactual": counterfactual,
            "obligations_fired": obligations_fired,
            "call": call,
        })

    for ev in _iter_events(source, path):
        t = ev.get("type")
        if t == "turn":
            handle_turn(ev)
            continue
        if t == "result":
            store.observe_result(ev.get("tool"), ev.get("ok", True), ev.get("text", ""))
            continue
        if t != "call":
            continue
        tool = ev.get("tool")
        tool_counts[tool] = tool_counts.get(tool, 0) + 1
        args = ev.get("args") or {}
        ts = ev.get("ts", "")
        agent = ev.get("agent", "?")
        if tool == "cron":
            structured_cron += 1
            mapped = norm.map_structured("cron", args)
            if mapped and norm.INFRA.match(mapped["vtool"]):
                record_action(agent, ts, mapped["vtool"], mapped["args"],
                              json.dumps(args, sort_keys=True), str(args), ev)
            continue
        if tool in ("edit", "apply_patch", "write"):
            mapped = norm.map_structured(tool, args)
            if mapped:
                record_action(agent, ts, mapped["vtool"], mapped["args"],
                              json.dumps(args, sort_keys=True), str(args.get("path", "")), ev)
            continue
        if tool != "exec":
            continue
        exec_calls += 1
        cmd = str(args.get("command", ""))
        out = norm.normalize_exec(cmd, help_filter=help_filter, heredoc_skip=heredoc_skip)
        seg_total += out["segments"]
        seg_unparsed += out["unparsed"]
        seg_nested += out["nested_unanalyzed"]
        for i, a in enumerate(out["actions"]):
            # AC #19: the key hashes the FULL segment text of this action
            seg_text = out["action_segments"][i] if i < len(out.get("action_segments", [])) else cmd
            record_action(agent, ts, a["vtool"], a["args"], seg_text, cmd, ev)
        # ablation count (first-pass): same corpus without help/heredoc handling
        abl = norm.normalize_exec(cmd, help_filter=False, heredoc_skip=False)
        ablation_infra += len(abl["actions"])

    total_calls = sum(tool_counts.values())
    exec_share = round(exec_calls / total_calls, 3) if total_calls else 0.0

    aggregates = _aggregate(source, path, profile, actions, tool_counts,
                            total_calls, exec_share, structured_cron,
                            seg_total, seg_unparsed, seg_nested, ablation_infra,
                            rd, pinned_rules, pin, retroactive, gating_rules,
                            obligation_rules)
    return aggregates, actions


def _rule_hit_counts(actions):
    """rules{<id>: {strict, plan, lenient}} from per-reading fired lists."""
    hits = {}
    for a in actions:
        for r in readings_mod.READINGS:
            for rid in (a["fired_by_reading"] or {}).get(r, []):
                hits.setdefault(rid, {x: 0 for x in readings_mod.READINGS})[r] += 1
    return {rid: hits[rid] for rid in sorted(hits)}


def _firing_rate_rows(actions, gating_rules, pin):
    """(rule, vtool) firing rates: n = evaluations (in-force when pinned),
    fired = strict-reading fires (AC #17b)."""
    by = {}
    for a in actions:
        vtool = a["vtool"]
        if pin is not None:
            rows = a.get("rule_rows") or []
            for row in rows:
                if row["status"] != "in_force":
                    continue
                c = by.setdefault((row["id"], vtool), {"n": 0, "fired": 0})
                c["n"] += 1
                if row["fired"].get("strict"):
                    c["fired"] += 1
        else:
            fired_strict = set((a["fired_by_reading"] or {}).get("strict", []))
            for r in gating_rules:
                if vtool in r["tools"]:
                    c = by.setdefault((r["id"], vtool), {"n": 0, "fired": 0})
                    c["n"] += 1
                    if r["id"] in fired_strict:
                        c["fired"] += 1
    return report_mod.firing_rates(by)


def _retroactive_rule_counts(actions):
    """retroactive_rules{<id>: {flagged, cc_requested_strict, class}}: rules
    that would fire but were not in force (strict reading)."""
    out = {}
    for a in actions:
        retro = (a.get("retro") or {}).get("strict")
        if not retro:
            continue
        # removed rules fired only in earlier versions: the action stays
        # ALLOW; the removal is listed here, never counted as a violation
        for reason, cls in (("later", "NO_RULE_IN_FORCE"),
                            ("unknown", "VERSION_UNKNOWN"),
                            ("removed", "ALLOW")):
            for rid in retro.get(reason, []):
                row = out.setdefault(rid, {"flagged": 0, "cc_requested_strict": 0,
                                           "class": cls})
                row["flagged"] += 1
                auth = a.get("readings_auth") or {}
                if auth.get("strict"):
                    row["cc_requested_strict"] += 1
    return {rid: out[rid] for rid in sorted(out)}


def _counterfactual_totals(actions):
    """--retroactive: per-reading totals of every version's rules applied to
    every action (NOT violations)."""
    if not any(a.get("counterfactual") for a in actions):
        return None
    totals = {r: {"blocked": 0, "total": 0} for r in readings_mod.READINGS}
    for a in actions:
        cf = a.get("counterfactual") or {}
        for r in readings_mod.READINGS:
            totals[r]["total"] += 1
            if cf.get(r):
                totals[r]["blocked"] += 1
    return {"label": pinning_mod.COUNTERFACTUAL_LABEL, "readings": totals}


def _obligation_section(actions, obligation_rules):
    """Obligations are not gates (AC #17e): end-of-trace report counts."""
    if not obligation_rules:
        return None
    counts = {r["id"]: 0 for r in obligation_rules}
    for a in actions:
        for rid in a.get("obligations_fired") or []:
            counts[rid] += 1
    return {rid: counts[rid] for rid in sorted(counts)}


def _aggregate(source, path, profile, actions, tool_counts, total_calls, exec_share,
               structured_cron, seg_total, seg_unparsed, seg_nested, ablation_infra,
               rd, pinned_rules, pin, retroactive, gating_rules, obligation_rules):
    by_vtool, by_agent, by_principal = {}, {}, {}
    non_infra_by_vtool = {}
    readings_blocked = {r: 0 for r in readings_mod.READINGS}
    verdict_classes = {r: {c: 0 for c in VERDICT_CLASSES} for r in readings_mod.READINGS}
    # infra-only verdict classes: verdict_classes sums infra and non-infra
    # (file.edit) actions, so a claim like "N of the 59 infra actions were
    # NO_RULE_IN_FORCE" needs its own exact aggregate (phase 5)
    verdict_classes_infra = {r: {c: 0 for c in VERDICT_CLASSES}
                             for r in readings_mod.READINGS}
    quiet_in_window = 0
    quiet_blocked_plan = 0
    gw_flagged = 0
    gw_cc_requested = 0
    ts_missing = 0

    # infra_actions, by_agent, by_principal, readings, quiet_hours (and the
    # parity values derived from them) count ONLY infra-mutating vtools; a
    # non-infra write (e.g. file.edit) stays in by_vtool / its own counts and
    # never receives INF-rule reading verdicts (phase 2a Bug 1)
    infra = [a for a in actions if a["infra"]]
    non_infra = [a for a in actions if not a["infra"]]

    for a in non_infra:
        by_vtool[a["vtool"]] = by_vtool.get(a["vtool"], 0) + 1
        non_infra_by_vtool[a["vtool"]] = non_infra_by_vtool.get(a["vtool"], 0) + 1
        for r in readings_mod.READINGS:
            verdict_classes[r][a["verdicts"][r]] += 1

    for a in infra:
        by_vtool[a["vtool"]] = by_vtool.get(a["vtool"], 0) + 1
        by_agent[a["agent"]] = by_agent.get(a["agent"], 0) + 1
        by_principal[a["principal"]] = by_principal.get(a["principal"], 0) + 1
        auth = a["readings_auth"]
        if a["hour"] is None:
            ts_missing += 1
        for r in readings_mod.READINGS:
            if pin is not None:
                # pinned: blocked = an in-force rule fired under this reading
                if a["verdicts"][r] == "BLOCK":
                    readings_blocked[r] += 1
            elif not auth[r]:
                # spike semantics: blocked under r = not cc_authorized under r
                readings_blocked[r] += 1
            verdict_classes[r][a["verdicts"][r]] += 1
            verdict_classes_infra[r][a["verdicts"][r]] += 1
        if a["hour"] is not None and a["hour"] < 8:
            quiet_in_window += 1
            if (pin is not None and a["verdicts"]["plan"] == "BLOCK") or \
                    (pin is None and not auth["plan"]):
                quiet_blocked_plan += 1
        if a["vtool"].startswith("gateway."):
            gw_flagged += 1
            if auth["strict"]:
                gw_cc_requested += 1

    aggregates = {
        "schema": "policygate-aggregates-v1",
        "profile": profile,
        "source": {
            "kind": source,
            "transcripts": _count_files(source, path),
            "tool_calls": total_calls,
            "exec_share": exec_share,
            "structured_cron_calls": structured_cron,
        },
        "input_manifest": input_manifest(source, path),
        "normalizer": {
            "segments": seg_total,
            "unparsed": seg_unparsed,
            "unparsed_rate": round(seg_unparsed / seg_total, 4) if seg_total else 0.0,
            "nested_unanalyzed": seg_nested,
            "infra_actions": len(infra),
            "non_infra_actions": len(non_infra),
            "ablation": {"no_help_no_heredoc": ablation_infra},
        },
        "by_vtool": dict(sorted(by_vtool.items())),
        "non_infra_by_vtool": dict(sorted(non_infra_by_vtool.items())),
        "by_agent": dict(sorted(by_agent.items())),
        "by_principal": dict(sorted(by_principal.items())),
        "provenance_source": "heuristic" if source == "legacy-archive" else "typed",
        "readings": {r: {"blocked": readings_blocked[r], "total": len(infra)}
                     for r in readings_mod.READINGS},
        "rules": _rule_hit_counts(actions),
        "quiet_hours": {"in_window": quiet_in_window, "blocked_plan": quiet_blocked_plan},
        "verdict_classes": verdict_classes,
        "verdict_classes_infra": verdict_classes_infra,
        "retroactive_rules": _retroactive_rule_counts(actions) if pin is not None else {},
        "firing_rates": _firing_rate_rows(actions, gating_rules, pin),
        "ambiguity_items": {},
        "ts_missing": ts_missing,
        "readings_sha256": rd.sha256,
        "plat_fbd_04": {"flagged": gw_flagged, "cc_requested_strict": gw_cc_requested},
    }
    obligations = _obligation_section(actions, obligation_rules)
    if obligations is not None:
        aggregates["obligations"] = obligations
    counterfactual = _counterfactual_totals(actions)
    if counterfactual is not None:
        aggregates["counterfactual"] = counterfactual
    aggregates["parity_check"] = _parity_check(aggregates)
    return aggregates


def _parity_check(agg):
    """Compare the run to config/research_values.toml (27 values)."""
    with open(os.path.join(CONFIG_DIR, "research_values.toml"), "rb") as f:
        rv = tomllib.load(f)
    actual = {
        "transcripts": agg["source"]["transcripts"],
        "tool_calls": agg["source"]["tool_calls"],
        "exec_share": agg["source"]["exec_share"],
        "structured_cron_calls": agg["source"]["structured_cron_calls"],
        "segments": agg["normalizer"]["segments"],
        "unparsed": agg["normalizer"]["unparsed"],
        "infra_actions": agg["normalizer"]["infra_actions"],
        "ablation_no_help_no_heredoc": agg["normalizer"]["ablation"]["no_help_no_heredoc"],
        "strict_blocked": agg["readings"]["strict"]["blocked"],
        "plan_blocked": agg["readings"]["plan"]["blocked"],
        "lenient_blocked": agg["readings"]["lenient"]["blocked"],
        "quiet_in_window": agg["quiet_hours"]["in_window"],
        "quiet_blocked_plan": agg["quiet_hours"]["blocked_plan"],
        "plat_fbd_04_flagged": agg["plat_fbd_04"]["flagged"],
        "plat_fbd_04_cc_requested": agg["plat_fbd_04"]["cc_requested_strict"],
        "principal_human": agg["by_principal"].get("cc_direct", 0),
        "principal_cron": agg["by_principal"].get("cron", 0),
        "principal_system": agg["by_principal"].get("system", 0),
        "agent_main": agg["by_agent"].get("main", 0),
        "agent_enhancer": agg["by_agent"].get("enhancer", 0),
        "vtool_cron_edit": agg["by_vtool"].get("cron.edit", 0),
        "vtool_gateway_restart": agg["by_vtool"].get("gateway.restart", 0),
        "vtool_service_restart": agg["by_vtool"].get("service.restart", 0),
        "vtool_cron_disable": agg["by_vtool"].get("cron.disable", 0),
        "vtool_cron_rm": agg["by_vtool"].get("cron.rm", 0),
        "vtool_cron_enable": agg["by_vtool"].get("cron.enable", 0),
        "vtool_config_set": agg["by_vtool"].get("config.set", 0),
    }
    matches, deltas = [], []
    for key in sorted(rv):
        want = rv[key]
        got = actual.get(key)
        if key == "exec_share":
            same = got is not None and round(float(got), 3) == round(float(want), 3)
        else:
            same = got == want
        row = {"id": key, "research": want, "actual": got}
        (matches if same else deltas).append(row)
    return {"matches": matches, "deltas": deltas}


def _assign_action_keys(actions):
    """Deterministic keys in stream order; a repeated (agent, ts, vtool,
    segment) tuple gets an occurrence index (AC #19)."""
    seen = {}
    keys = []
    for a in actions:
        tup = (a["agent"], a["ts"], a["vtool"], a["segment"])
        occ = seen.get(tup, 0)
        seen[tup] = occ + 1
        keys.append(_action_key(a["agent"], a["ts"], a["vtool"], a["segment"],
                                occurrence=occ))
    return keys


def write_run_dir(out_dir, aggregates, actions, profile, bundle_commits=None,
                  readings=None, candidates_sha=None, label_context=True,
                  ambiguity_items=None):
    """Write run dir (local/ or tmp): manifest.json, actions.jsonl,
    aggregates.json, ambiguity.{json,md}."""
    os.makedirs(out_dir, exist_ok=True)
    rd = readings or readings_mod.default()
    head = _policygate_head()
    manifest = {
        "profile": profile,
        "bundle_commits": bundle_commits or {},
        "readings_sha256": rd.sha256,
        "vtools_sha256": _sha_file(os.path.join(CONFIG_DIR, "vtools.toml")),
        "candidates_sha256": candidates_sha or "",
        "policygate_head": head,
        "input_manifest": aggregates.get("input_manifest", {}),
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, sort_keys=True, indent=2)
    with open(os.path.join(out_dir, "aggregates.json"), "w", encoding="utf-8") as f:
        json.dump(aggregates, f, sort_keys=True, indent=2)
    keys = _assign_action_keys(actions)
    with open(os.path.join(out_dir, "actions.jsonl"), "w", encoding="utf-8") as f:
        for key, a in zip(keys, actions):
            rec = {
                "action_key": key,
                "agent": a["agent"], "ts": a["ts"], "vtool": a["vtool"],
                "args": _mask_args(a["args"]),
                "principal": a["principal"], "provenance_source": a["provenance_source"],
                "infra": a["infra"],
                "readings": a["verdicts"],
                "verdict_class": a["verdicts"]["strict"],
                "fired": a["fired_by_reading"]["strict"],
                "fired_by_reading": a["fired_by_reading"],
            }
            if a.get("retro"):
                rec["retroactive"] = a["retro"]
            if a.get("counterfactual") is not None:
                rec["counterfactual_fired"] = a["counterfactual"]
            if a.get("obligations_fired"):
                rec["obligations_fired"] = a["obligations_fired"]
            check_verdict_invariant(rec)
            if label_context:
                rec["label_context"] = {
                    "principal": a["principal"],
                    "turn_text": norm.redact(a.get("cc_text") or a.get("turn_text") or "", 240),
                    "prev_assistant": norm.redact(a.get("prev_assistant") or "", 240),
                }
            f.write(json.dumps(rec, sort_keys=True) + "\n")
    ambiguity_mod.write(out_dir, ambiguity_items or [])


def _mask_args(args):
    out = {}
    for k, v in (args or {}).items():
        if isinstance(v, str):
            out[k] = norm.redact(v, 70)
        else:
            out[k] = v
    return out


def _policygate_head():
    from . import gitread
    try:
        return gitread.run(os.path.dirname(os.path.dirname(__file__)),
                           ["rev-parse", "HEAD"]).strip()
    except Exception:
        return "unknown"


def replay_cmd(ns):
    import sys
    # real-data sources must not write actions.jsonl into the repo outside local/
    out = os.path.abspath(ns.out)
    repo = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    if ns.source in ("legacy-archive", "trajectory"):
        local = os.path.join(repo, "local")
        if out.startswith(repo + os.sep) and not out.startswith(local + os.sep):
            print(f"error: real-data --out must be under local/ (got {ns.out})", file=sys.stderr)
            return EXIT_USAGE
    pin = None
    resolve_report = []
    candidates_sha = None
    if ns.profile == "pinned":
        if not ns.candidates:
            print("error: --profile pinned requires --candidates", file=sys.stderr)
            return EXIT_USAGE
        if not ns.root or not ns.bundle:
            print("error: --profile pinned requires --root and --bundle "
                  "(version pinning resolves the bundle at each action time)",
                  file=sys.stderr)
            return EXIT_USAGE
        from . import resolve as resolve_mod
        cands = rules_mod.load_candidates(ns.candidates)
        candidates_sha = _sha_candidates(ns.candidates)
        run_rules, resolve_report = resolve_mod.resolve(cands)
        pin = pinning_mod.PinnedPolicy(ns.root, ns.bundle, run_rules)
    else:
        _, run_rules, _ = _load_profile_rules("spike-parity")
    aggregates, actions = replay_stream(
        ns.source, ns.path, ns.profile,
        help_filter=not ns.no_help_filter, heredoc_skip=not ns.no_heredoc_skip,
        pinned_rules=run_rules, pin=pin, retroactive=ns.retroactive,
    )
    # ambiguity queue: full items only in the run dir (local/tmp); the
    # aggregate carries only the count by kind (AC #17). unclassified_clause
    # comes from the raw candidate list: an `ambiguous` candidate must reach
    # the queue even when RESOLVE rejects it (it never gates either way).
    # Items are keyed (clause, action-class); per-action evidence travels as
    # action_keys, so keys are assigned before generation (deterministic;
    # write_run_dir recomputes the same keys).
    ambiguous = [c for c in (cands if ns.profile == "pinned" else [])
                 if c.get("class") == "ambiguous"]
    for key, a in zip(_assign_action_keys(actions), actions):
        a["action_key"] = key
    items = ambiguity_mod.generate(actions, resolve_report,
                                   ambiguous_rules=ambiguous,
                                   rules=pinning_mod.route_rules(run_rules)["gating"])
    aggregates["ambiguity_items"] = ambiguity_mod.counts_by_kind(items)
    if pin is not None:
        # a clause whose text changed across versions keeps one rule per
        # version; the report lists such rules (AC #14)
        aggregates["per_version_rules"] = pin.per_version_groups()
    bundle_commits = pin.commits_by_source() if pin is not None else {}
    write_run_dir(ns.out, aggregates, actions, ns.profile,
                  bundle_commits=bundle_commits, candidates_sha=candidates_sha,
                  ambiguity_items=items)
    if ns.format == "json":
        print(json.dumps(aggregates, sort_keys=True, indent=2))
    else:
        _print_header(ns.profile, aggregates)
    return EXIT_OK


def _print_header(profile, agg):
    print(f"profile: {profile}")
    print(f"principal provenance: {agg['provenance_source']} (legacy JSONL has no typed provenance)")
    print(f"readings sha256: {agg['readings_sha256'][:16]}")
    if profile == "spike-parity":
        print("SPIKE PARITY: research spike semantics (no version pinning, no consumption)")
    print(f"infra actions: {agg['normalizer']['infra_actions']}")
    for r in readings_mod.READINGS:
        print(f"  {r}: BLOCK {agg['readings'][r]['blocked']}/{agg['readings'][r]['total']}")
    if profile == "pinned":
        print("verdict classes per reading:")
        for r in readings_mod.READINGS:
            vc = agg["verdict_classes"][r]
            print(f"  {r}: " + " ".join(f"{c}={vc[c]}" for c in VERDICT_CLASSES))
        print(f"retroactive rules: {len(agg.get('retroactive_rules', {}))} "
              f"(never counted as violations)")
    cf = agg.get("counterfactual")
    if cf:
        print(cf["label"])
        for r in readings_mod.READINGS:
            t = cf["readings"][r]
            print(f"  {r}: {t['blocked']}/{t['total']}")
