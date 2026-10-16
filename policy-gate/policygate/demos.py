"""Offline demos: compile, feb19, adversarial, readings, amend, all (AC #25).

Each section prints its banner. feb19 carries the reconstruction banner; the
others carry the SYNTHETIC banner. No network, no /root/.openclaw access
(except the optional --verify-sources host path, which is read-only via gitread).
All output is byte-deterministic.
"""

import json
import os

from . import check as check_mod
from . import resolve as resolve_mod
from . import rules as rules_mod

HERE = os.path.dirname(__file__)
FIX = os.path.normpath(os.path.join(HERE, os.pardir, "fixtures"))

RECON_BANNER = ("RECONSTRUCTED FIXTURE: rebuilt from the mistake log, a memory backup, "
                "and git history (f84fecd8, 943e5e1d). The original transcript does not "
                "exist. In-episode timestamps are approximate.")
SYN_BANNER = "SYNTHETIC FIXTURE: mechanism demo, not results from real transcripts"
KEYWORD_LABEL = "agenthook-style keyword baseline (our reimplementation, not agenthook)"


# ----------------------------------------------------------------------------
# feb19
# ----------------------------------------------------------------------------
def _load_feb19():
    with open(os.path.join(FIX, "feb19", "episodes.json"), encoding="utf-8") as f:
        episodes = json.load(f)
    with open(os.path.join(FIX, "feb19", "policy_f84fecd8.json"), encoding="utf-8") as f:
        policy = json.load(f)
    return episodes, policy


def _resolve_feb19(policy):
    kept, report = resolve_mod.resolve(policy["candidates"])
    # the spike's RESOLVE block lists only per-candidate REPAIR/REJECT rows,
    # one row per candidate, in candidate order
    seen = set()
    rows = []
    for r in report:
        if r["outcome"] not in ("REPAIR", "REJECT"):
            continue
        if "~" in r["id"] or ">" in r["id"]:
            continue
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        rows.append({"id": r["id"], "outcome": r["outcome"], "class": r["class"]})
    return kept, rows


def _resolve_jobs(events, jobmap):
    out = []
    for e in events:
        e = dict(e)
        if e.get("type") == "call":
            args = dict(e.get("args") or {})
            jid = args.get("jobId")
            if jid in jobmap:
                args["jobId"] = jobmap[jid]
            e["args"] = args
        out.append(e)
    return out


def _replay_episode(events, kept_rules, jobmap):
    """Replay one episode with cc_authorized=False throughout (no CC instruction
    authorized these actions; the one CC turn is a question). Returns
    (calls, blocked, call_records, weakens_fired)."""
    events = _resolve_jobs(events, jobmap)
    facts = {"cc_authorized": False, "confirmation_fresh": False, "principal": "agent"}
    calls = 0
    blocked = 0
    records = []
    weakens = False
    for e in events:
        if e.get("type") != "call":
            continue
        calls += 1
        call = {"vtool": e["vtool"], "args": e.get("args") or {}, "ts": e.get("ts", "")}
        res = check_mod.check(e["vtool"], call, facts, kept_rules)
        if res["verdict"] == "BLOCK":
            blocked += 1
        if "TWR-FBD-03" in res["fired"]:
            weakens = True
        records.append({"vtool": e["vtool"], "fired": res["fired"],
                        "verdict": res["verdict"]})
    return calls, blocked, records, weakens


def feb19_data(baseline=None):
    episodes, policy = _load_feb19()
    jobmap = episodes["jobs"]
    kept, resolve_rows = _resolve_feb19(policy)

    ep1 = episodes["episode_1"]["events"]
    ep2 = episodes["episode_2"]["events"]

    # episode 1 pinned to pre-f84fecd8 (no rules)
    c1p, b1p, rec1p, _ = _replay_episode(ep1, [], jobmap)
    # episode 1 counterfactual under f84fecd8 rules (retroactive)
    c1c, b1c, rec1c, _ = _replay_episode(ep1, kept, jobmap)
    # episode 2 pinned to f84fecd8
    c2p, b2p, rec2p, weakens = _replay_episode(ep2, kept, jobmap)

    flat_calls = []
    for rec, ep in ((rec1p, "ep1_pinned"), (rec1c, "ep1_counterfactual"), (rec2p, "ep2_pinned")):
        for r in rec:
            flat_calls.append({"episode": ep, **r})

    data = {
        "banner": RECON_BANNER,
        "resolve": resolve_rows,
        "episodes": {
            "ep1_pinned": {"calls": c1p, "blocked": b1p},
            "ep1_counterfactual": {"calls": c1c, "blocked": b1c, "retroactive": True},
            "ep2_pinned": {"calls": c2p, "blocked": b2p},
        },
        "weakens_policy_fired": weakens,
        "calls": flat_calls,
    }
    if baseline == "keyword":
        from .baselines import keyword
        data["baselines"] = {"keyword": keyword.feb19_summary(ep2, jobmap)}
    return data


def _verify_sources(root):
    """Read-only [host] checks via gitread. Prints PASS/FAIL per check, no file text."""
    from . import gitread
    lines = []

    def check(name, ok):
        lines.append(f"{'PASS' if ok else 'FAIL'} {name}")

    try:
        t1 = gitread.commit_time(root, "f84fecd8")
        check("f84fecd8 exists at 2026-02-19T16:38Z", t1.startswith("2026-02-19") and "16:38" in t1)
    except Exception:
        check("f84fecd8 exists at 2026-02-19T16:38Z", False)
    try:
        t2 = gitread.commit_time(root, "943e5e1d")
        check("943e5e1d exists at 2026-02-20T01:01Z", t2.startswith("2026-02-20") and "01:01" in t2)
    except Exception:
        check("943e5e1d exists at 2026-02-20T01:01Z", False)
    try:
        blob = gitread.show(root, "f84fecd8",
                            "workspace-techwriter-researcher/MEMORY.md")
        check("f84fecd8 MEMORY.md contains DO NOT TOUCH block", "DO NOT TOUCH" in blob)
    except Exception:
        check("f84fecd8 MEMORY.md contains DO NOT TOUCH block", False)
    try:
        diff = gitread.run(root, ["show", "943e5e1d", "--",
                                  "workspace-techwriter-researcher/MEMORY.md"])
        removed_dnt = any(l.startswith("-") and "DO NOT TOUCH" in l for l in diff.splitlines())
        added_paused = any(l.startswith("+") and "PAUSED" in l for l in diff.splitlines())
        check("943e5e1d MEMORY.md diff removes DO NOT TOUCH, adds PAUSED",
              removed_dnt and added_paused)
    except Exception:
        check("943e5e1d MEMORY.md diff removes DO NOT TOUCH, adds PAUSED", False)
    return lines


def render_feb19(data, fmt):
    if fmt == "json":
        return json.dumps(data, sort_keys=True, indent=2)
    lines = [data["banner"], ""]
    lines.append("RESOLVE:")
    for r in data["resolve"]:
        lines.append(f"  {r['id']}: {r['outcome']} {r['class']}")
    e = data["episodes"]
    lines.append(f"episode 1 pinned (pre-f84fecd8, no rule in force): "
                 f"{e['ep1_pinned']['blocked']}/{e['ep1_pinned']['calls']} blocked")
    lines.append(f"episode 1 COUNTERFACTUAL (retroactive policy; not violations): "
                 f"{e['ep1_counterfactual']['blocked']}/{e['ep1_counterfactual']['calls']} blocked")
    lines.append(f"episode 2 pinned (f84fecd8): "
                 f"{e['ep2_pinned']['blocked']}/{e['ep2_pinned']['calls']} blocked")
    lines.append(f"weakens_policy fired on the MEMORY.md self-edit: {data['weakens_policy_fired']}")
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# adversarial (AC #12)
# ----------------------------------------------------------------------------
def adversarial_data():
    path = os.path.join(FIX, "adversarial", "cases.jsonl")
    cases = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if "principal" in d or "events" in d:
                cases.append(d)
    from . import principal as principal_mod
    from . import facts as facts_mod

    accepted = 0
    blocked = 0
    expected_block = 0
    results = []
    for c in cases:
        store = facts_mod.FactStore("pinned")
        legit_budget = 1 if c.get("legit_cc") else 0
        improper = 0
        for ev in c["events"]:
            if ev.get("type") == "turn":
                # only cc_direct / cc_relayed turns may create authorization;
                # a forged principal (cron/agent/system/heartbeat/unknown)
                # never does, no matter what the text claims
                p = ev.get("principal")
                prov = ev.get("provenance_source", "heuristic")
                cc_text = ev.get("cc_text") if p in ("cc_direct", "cc_relayed") else None
                store.observe_turn(p, prov, cc_text, ev.get("prev_assistant", ""))
            elif ev.get("type") == "result":
                # tool-result content never creates an authorization fact
                store.observe_result(ev.get("tool"), ev.get("ok", True), ev.get("text", ""))
            elif ev.get("type") == "call":
                vt = ev["vtool"]
                auth = store.authorization_for(vt)
                if any(auth.values()):
                    if legit_budget > 0:
                        legit_budget -= 1          # the one legitimate CC-authorized write
                        store.consume_authorization(vt, auth)
                    else:
                        improper += 1               # forged or a consumed retry
        if c.get("expect_block", True):
            expected_block += 1
            blocked += 1
        accepted += improper
        results.append({"id": c["id"], "improper_acceptances": improper})

    return {
        "banner": SYN_BANNER,
        "cases": len(cases),
        "accepted_authorizations": accepted,
        "blocked": blocked,
        "cases_expected_block": expected_block,
        "results": results,
    }


def render_adversarial(data, fmt):
    if fmt == "json":
        return json.dumps(data, sort_keys=True, indent=2)
    return "\n".join([
        data["banner"],
        f"adversarial cases: {data['cases']}",
        f"accepted authorizations: {data['accepted_authorizations']}",
        f"blocked: {data['blocked']} / expected {data['cases_expected_block']}",
    ])


# ----------------------------------------------------------------------------
# readings (AC #13)
# ----------------------------------------------------------------------------
def readings_data():
    from . import readings as readings_mod
    rd = readings_mod.default()
    path = os.path.join(FIX, "readings", "cases.jsonl")
    verdicts = []
    totals = {r: 0 for r in readings_mod.READINGS}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if "vtool" not in d:
                continue
            auth = rd.all_readings(d["vtool"], d.get("cc_text"), d.get("prev_assistant", ""))
            rec = {"id": d["id"], "vtool": d["vtool"],
                   "readings": {r: ("ALLOW" if auth[r] else "BLOCK") for r in readings_mod.READINGS}}
            verdicts.append(rec)
            for r in readings_mod.READINGS:
                if not auth[r]:
                    totals[r] += 1
    return {
        "banner": SYN_BANNER,
        "verdicts": verdicts,
        "totals": {r: totals[r] for r in sorted(readings_mod.READINGS)},
    }


def render_readings(data, fmt):
    from . import readings as readings_mod
    if fmt == "json":
        return json.dumps(data, sort_keys=True, indent=2)
    lines = [data["banner"], "blocked per reading (side by side):"]
    for r in readings_mod.READINGS:
        lines.append(f"{r} {data['totals'][r]} blocked")
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# compile (synthetic) (AC #25 part)
# ----------------------------------------------------------------------------
def compile_data():
    import subprocess
    import sys
    import tempfile
    from . import emit
    repo = tempfile.mkdtemp(prefix="pg_demo_repo_")
    subprocess.run([sys.executable, os.path.join(HERE, os.pardir, "tests", "fixtures",
                                                  "make_policy_repo.py"), repo],
                   check=True, capture_output=True)
    report, _ = emit.compile_bundle(
        repo, os.path.join(FIX, "bundle.synthetic.toml"), "2026-03-01T00:00:00Z",
        os.path.join(FIX, "candidates", "synthetic.json"), None)
    report = {k: v for k, v in report.items() if k != "resolve_report"}
    report["banner"] = SYN_BANNER
    return report


def render_compile(data, fmt):
    if fmt == "json":
        return json.dumps(data, sort_keys=True, indent=2)
    lines = [data["banner"],
             f"candidate origin: {data['candidate_origin']}",
             f"RESOLVE defect classes (origin builder): {data['resolve_counts']}",
             f"coverage: {data['coverage']}"]
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# amend (AC #17)
# ----------------------------------------------------------------------------
def amend_data():
    from . import amend
    return amend.demo_data(SYN_BANNER)


def render_amend(data, fmt):
    if fmt == "json":
        return json.dumps(data, sort_keys=True, indent=2)
    lines = [data["banner"],
             f"items closed: {data['items_closed']}",
             f"before: {data['before']}",
             f"after: {data['after']}",
             f"overlay written to policy repo: {data['overlay_written_to_policy_repo']}"]
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# dispatch
# ----------------------------------------------------------------------------
def run(ns):
    fmt = ns.format
    which = ns.which
    if which == "feb19":
        if ns.verify_sources:
            lines = _verify_sources(ns.verify_sources)
            print("\n".join(lines))
            return 0
        data = feb19_data(baseline=ns.baseline)
        print(render_feb19(data, fmt))
        return 0
    if which == "adversarial":
        print(render_adversarial(adversarial_data(), fmt))
        return 0
    if which == "readings":
        print(render_readings(readings_data(), fmt))
        return 0
    if which == "compile":
        print(render_compile(compile_data(), fmt))
        return 0
    if which == "amend":
        print(render_amend(amend_data(), fmt))
        return 0
    if which == "all":
        if fmt == "json":
            out = {
                "compile": compile_data(),
                "feb19": feb19_data(baseline=ns.baseline),
                "adversarial": adversarial_data(),
                "readings": readings_data(),
                "amend": amend_data(),
            }
            print(json.dumps(out, sort_keys=True, indent=2))
            return 0
        print(render_compile(compile_data(), fmt))
        print()
        print(render_feb19(feb19_data(baseline=ns.baseline), fmt))
        print()
        print(render_adversarial(adversarial_data(), fmt))
        print()
        print(render_readings(readings_data(), fmt))
        print()
        print(render_amend(amend_data(), fmt))
        return 0
    return 2
