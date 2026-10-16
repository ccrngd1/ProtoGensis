#!/usr/bin/env python3
"""PolicyGate feasibility spike (PreCog, 2026-10-16). Throwaway, stdlib only.

Questions it answers:
  Q1. In real OpenClaw transcripts, what share of infra-mutating actions go
      through structured tools vs. free-form `exec` shell strings?
  Q2. Can a stdlib shlex normalizer turn those shell strings into
      "virtual tool calls" (openclaw.cron.disable{id}, gateway.restart, ...)?
  Q3. How do verdicts change with how strict the authorization predicate is?
      (explicit CC instruction vs "yes" to a plan vs any human turn)
  Q4. Who are the principals behind the "user" turns that precede infra actions?
      (CC vs heartbeat vs system notice vs another agent)

Reads the archived legacy JSONL transcripts under ~/.openclaw/agents/*/
session-sqlite-import-archive/ (read-only). Prints aggregates plus a few
redacted examples. Never prints secrets: commands are truncated and
token/key/password patterns are masked.

Hand-compiled rules (from ~/.openclaw/global/BASE-AGENTS.md, "Infrastructure Rules"):
  INF-PRE-01  PRECONDITION cc_authorized   guards cron.{disable,rm,edit,update,enable}
  INF-PRE-02  PRECONDITION cc_authorized   guards service.{restart,stop,disable}, docker.*, gateway.*
  INF-FBD-03  FORBIDDEN    quiet_hours_utc (00:00-08:00) AND NOT cc_authorized   guards all of the above
  PLAT-FBD-04 FORBIDDEN    always          guards gateway.{restart,stop} via exec
              (from the current OpenClaw system prompt; NOT in force historically ->
               shows why replay must pin the policy version)
"""
import glob, json, os, re, shlex, sys, collections

ROOT = os.path.expanduser("~/.openclaw/agents")
SECRET = re.compile(r"(token|key|secret|password|bearer)([=: ]+)\S+", re.I)

def redact(s, n=100):
    return SECRET.sub(r"\1\2***", " ".join(str(s).split()))[:n]

# ---------- Q2: shell -> virtual actions ----------
SEP = {";", "&&", "||", "|", "&", "\n"}

def segments(cmd):
    """Split a shell string into simple commands. shlex with punctuation_chars
    keeps quoted strings intact and emits ; && || | as separate tokens."""
    out = []
    lines, body, delim = [], False, None
    for line in cmd.replace("\\\n", " ").split("\n"):
        # drop here-doc bodies: text written to a file/variable is data, not execution
        if delim is not None:
            if line.strip() == delim: delim = None
            continue
        mm = re.search(r"<<-?\s*['\"]?(\w+)['\"]?", line)
        if mm: delim = mm.group(1)
        lines.append(line)
    for line in lines:
        try:
            lex = shlex.shlex(line, posix=True, punctuation_chars=";&|")
            lex.whitespace_split = True
            lex.commenters = "#"
            toks = list(lex)
        except ValueError:          # unbalanced quotes etc.
            out.append(("__unparsed__", line))
            continue
        cur = []
        for t in toks:
            if t in SEP or set(t) <= set(";&|"):
                if cur: out.append(tuple(cur)); cur = []
            else:
                cur.append(t)
        if cur: out.append(tuple(cur))
    return out

def classify(seg):
    """Return a virtual action dict or None."""
    if seg and seg[0] == "__unparsed__":
        return {"vtool": "unparsed", "args": {}}
    s = [t for t in seg if not re.match(r"^\d?>|^2>&1$", t)]
    # strip env assignments / sudo / timeout prefixes
    while s and (re.match(r"^\w+=", s[0]) or s[0] in ("sudo", "timeout", "nohup", "exec")):
        s = s[1:] if s[0] != "timeout" else s[2:]
    if not s: return None
    if any(t in ("--help", "-h", "help", "--dry-run") for t in s): return None   # read-only invocations
    h = s[0].split("/")[-1]
    if h == "openclaw" and len(s) >= 3 and s[1] == "cron" and s[2] in ("disable", "rm", "remove", "delete", "edit", "update", "enable", "add", "pause"):
        verb = {"remove": "rm", "delete": "rm", "pause": "disable"}.get(s[2], s[2])
        return {"vtool": f"cron.{verb}", "args": {"jobId": s[3] if len(s) > 3 and not s[3].startswith("-") else None}}
    if h == "openclaw" and len(s) >= 3 and s[1] == "gateway" and s[2] in ("restart", "stop"):
        return {"vtool": f"gateway.{s[2]}", "args": {}}
    if h == "openclaw" and len(s) >= 3 and s[1] == "config" and s[2] == "set":
        return {"vtool": "config.set", "args": {"key": s[3] if len(s) > 3 else None}}
    if h == "systemctl" and len(s) >= 2 and s[1] in ("restart", "stop", "disable"):
        return {"vtool": f"service.{s[1]}", "args": {"unit": s[2] if len(s) > 2 else None}}
    if h == "docker" and len(s) >= 2:
        if s[1] in ("restart", "stop", "rm"):
            return {"vtool": f"docker.{s[1]}", "args": {"target": s[2] if len(s) > 2 else None}}
        if s[1] == "compose" and any(v in s for v in ("up", "down", "restart")):
            return {"vtool": "docker.compose", "args": {}}
    if h == "crontab" and any(f in s for f in ("-e", "-r", "-")):
        return {"vtool": "crontab.write", "args": {}}
    return None

INFRA = re.compile(r"^(cron\.(disable|rm|edit|update|enable)|service\.|docker\.|gateway\.|crontab\.|config\.set)")

# ---------- Q4: principal of a "user" turn ----------
def principal(text):
    t = text.lstrip()
    if "HEARTBEAT" in t[:300]: return "heartbeat"
    if t.startswith("System:") or t.startswith("[System]") or "Exec finished" in t[:200]: return "system"
    if t.startswith("[cron:") or "cron job" in t[:80].lower() and "scheduled" in t[:200].lower(): return "cron"
    if re.search(r'"from"\s*:\s*"(main|precog|netops|enhancer|[a-z-]+)"', t[:400]) or t.startswith("[Inter-agent") or "task-request" in t[:300]:
        return "agent"
    if "subagent" in t[:200].lower() or t.startswith("[Subagent"): return "agent"
    return "human"   # best effort: channel message text, usually CC

AFFIRM = re.compile(r"^\W*(yes|yep|yeah|ok(ay)?|do it|go( ahead)?|sure|proceed|continue|approved?|lgtm|run (steps?|it|them)|execute|sounds good)\b", re.I)
VERB_FOR = {
    "cron": re.compile(r"\b(cron|job|jobs|schedul)\w*", re.I),
    "gateway": re.compile(r"\b(gateway|restart)\w*", re.I),
    "service": re.compile(r"\b(restart|service|systemd|container|docker|stop)\w*", re.I),
    "docker": re.compile(r"\b(docker|container|compose|restart)\w*", re.I),
    "config": re.compile(r"\b(config|setting|set)\w*", re.I),
    "crontab": re.compile(r"\b(cron|crontab)\w*", re.I),
}

def text_of(m):
    c = m.get("content")
    if isinstance(c, str): return c
    return " ".join(p.get("text", "") for p in (c or []) if isinstance(p, dict) and p.get("type") == "text")

def authorized(reading, vt, cc_text, prev_assistant):
    """cc_authorized predicate under three readings (cf. NOMOS strict vs batch reading)."""
    if cc_text is None: return False
    fam = vt.split(".")[0]
    pat = VERB_FOR.get(fam)
    names_it = bool(pat and pat.search(cc_text))
    if reading == "strict":            # CC's own turn names the action/object
        return names_it
    if reading == "plan":              # ...or CC affirmed a plan that named it
        return names_it or (bool(AFFIRM.match(cc_text)) and bool(pat and pat.search(prev_assistant or "")))
    if reading == "lenient":           # any human turn opened this run
        return True
    raise ValueError(reading)

def main():
    files = [f for f in glob.glob(f"{ROOT}/*/session-sqlite-import-archive/*.jsonl.imported-*") if "trajectory" not in f]
    tool_counts = collections.Counter()
    exec_infra = 0; segs_total = 0; segs_unparsed = 0
    actions = []   # (agent, ts, vtool, principal_of_turn, verdicts{reading:bool}, quiet, cmd)
    for f in files:
        agent = os.path.relpath(f, ROOT).split("/")[0]
        turn_principal = None; cc_text = None; prev_assistant = ""; last_assistant_text = ""
        for line in open(f, errors="ignore"):
            try: d = json.loads(line)
            except Exception: continue
            m = d.get("message") or {}
            role = m.get("role")
            if role == "user":
                txt = text_of(m)
                turn_principal = principal(txt)
                cc_text = re.sub(r"^\[[^\]]{8,40}\]\s*", "", txt) if turn_principal == "human" else None
                prev_assistant = last_assistant_text
                continue
            if role != "assistant": continue
            at = text_of(m)
            if at.strip(): last_assistant_text = at
            for p in m.get("content") or []:
                if not isinstance(p, dict) or p.get("type") != "toolCall": continue
                name = p.get("name"); tool_counts[name] += 1
                if name != "exec": continue
                cmd = str((p.get("arguments") or {}).get("command", ""))
                for seg in segments(cmd):
                    a = classify(seg)
                    segs_total += 1
                    if a and a["vtool"] == "unparsed": segs_unparsed += 1; continue
                    if not a or not INFRA.match(a["vtool"]): continue
                    ts = d.get("timestamp", "")
                    hour = int(ts[11:13]) if len(ts) >= 13 and ts[11:13].isdigit() else 12
                    v = {r: authorized(r, a["vtool"], cc_text, prev_assistant) for r in ("strict", "plan", "lenient")}
                    actions.append((agent, ts[:16], a["vtool"], turn_principal or "none", v, hour < 8, cmd))
    exec_infra = len(actions)

    print(f"transcripts scanned: {len(files)}")
    tot = sum(tool_counts.values())
    print(f"tool calls: {tot}; exec share: {tool_counts['exec']/tot:.1%}; structured 'cron' tool calls: {tool_counts['cron']}")
    print(f"exec segments parsed: {segs_total}; unparsed (shlex error): {segs_unparsed} ({segs_unparsed/max(segs_total,1):.2%})")
    print(f"infra-mutating virtual actions found: {exec_infra}")
    print("by vtool:", dict(collections.Counter(a[2] for a in actions).most_common()))
    print("by agent:", dict(collections.Counter(a[0] for a in actions).most_common()))
    print("principal of the turn that triggered the action:", dict(collections.Counter(a[3] for a in actions).most_common()))
    print("principal x agent:", dict(collections.Counter((a[0], a[3]) for a in actions).most_common()))
    print("\nverdicts for rules INF-PRE-01/02 (BLOCK = no CC authorization under that reading):")
    for r in ("strict", "plan", "lenient"):
        blocked = sum(1 for a in actions if not a[4][r])
        print(f"  {r:8s}: BLOCK {blocked:3d} / {exec_infra}  ({blocked/max(exec_infra,1):.0%})")
    q = [a for a in actions if a[5]]
    print(f"\nINF-FBD-03 quiet hours (00-08 UTC): {len(q)} actions in window; "
          f"blocked under 'plan' reading: {sum(1 for a in q if not a[4]['plan'])}")
    gw = [a for a in actions if a[2].startswith("gateway.")]
    print(f"PLAT-FBD-04 (current platform rule, retroactive): would flag {len(gw)} gateway restarts via exec "
          f"-- of which {sum(1 for a in gw if a[4]['strict'])} were explicitly requested by CC. "
          "=> a retroactive rule produces 'violations' that were authorized at the time; pin policy versions.")
    print("\nexamples where strict and plan readings disagree (CC said 'yes' to a plan):")
    for a in [a for a in actions if a[4]["plan"] and not a[4]["strict"]][:4]:
        print("  ", a[0], a[1], a[2], "|", redact(a[6], 70))
    print("examples blocked under every reading except lenient-none (no human turn at all):")
    for a in [a for a in actions if not a[4]["lenient"]][:6]:
        print("  ", a[0], a[1], a[2], "principal:", a[3], "|", redact(a[6], 70))

if __name__ == "__main__":
    main()
