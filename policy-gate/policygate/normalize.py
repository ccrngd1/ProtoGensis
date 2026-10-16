"""Virtual-tool normalizer: exec shell strings -> typed actions (AC #9).

DETERMINISTIC. `segments()` and `classify()` are a literal port of spike 1
(tests/spike_ref/spike_replay.py; parity unit test in tests/test_normalize.py),
with the AC #9 additions layered on top: head-token denylist, nested_unanalyzed
counting, structured-tool mapping, heredoc line counting, and the ablation
flags --no-help-filter / --no-heredoc-skip.

Per-segment output reason vocabulary: action, read_only_flag, heredoc_body,
denylisted_head, unparsed, nested_unanalyzed, not_infra.
"""

import json
import re
import shlex

SEP = {";", "&&", "||", "|", "&", "\n"}
HEREDOC_RE = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")
REDIR_RE = re.compile(r"^\d?>|^2>&1$")
ENV_ASSIGN_RE = re.compile(r"^\w+=")
# AC #9 head-token denylist: these heads never produce an action (the command
# text is an argument, i.e. data).
DENYLIST_HEADS = {"echo", "printf", "grep", "rg", "cat", "less", "head", "tail", "jq", "awk"}
NESTED_HEADS = {"eval", "ssh"}
INFRA = re.compile(r"^(cron\.(disable|rm|edit|update|enable)|service\.|docker\.|gateway\.|crontab\.|config\.set)")
SECRET = re.compile(r"(token|key|secret|password|bearer)([=: ]+)\S+", re.I)
PROHIBITION = re.compile(r"(DO NOT|Do NOT|NEVER|must not|❌|PERMANENT|Forbidden)", re.I)


def redact(s, n=100):
    """Spike-style redaction: secrets masked, whitespace collapsed, truncated."""
    return SECRET.sub(r"\1\2***", " ".join(str(s).split()))[:n]


def segments(cmd, heredoc_skip=True):
    """Split a shell string into simple commands. Literal port of spike 1,
    plus (a) heredoc_skip ablation flag and (b) skipped heredoc line count.

    Returns (segments, heredoc_lines_skipped).
    """
    out = []
    heredoc_lines = 0
    lines, delim = [], None
    for line in cmd.replace("\\\n", " ").split("\n"):
        # drop here-doc bodies: text written to a file/variable is data, not execution
        if heredoc_skip and delim is not None:
            if line.strip() == delim:
                delim = None
            else:
                heredoc_lines += 1
            continue
        mm = HEREDOC_RE.search(line)
        if mm and heredoc_skip:
            delim = mm.group(1)
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
                if cur:
                    out.append(tuple(cur))
                    cur = []
            else:
                cur.append(t)
        if cur:
            out.append(tuple(cur))
    return out, heredoc_lines


def classify(seg, help_filter=True):
    """Literal port of spike 1's classify(): virtual action dict or None.
    help_filter=False disables the read-only-invocation drop (ablation)."""
    if seg and seg[0] == "__unparsed__":
        return {"vtool": "unparsed", "args": {}}
    s = [t for t in seg if not REDIR_RE.match(t)]
    # strip env assignments / sudo / timeout prefixes
    while s and (ENV_ASSIGN_RE.match(s[0]) or s[0] in ("sudo", "timeout", "nohup", "exec")):
        s = s[1:] if s[0] != "timeout" else s[2:]
    if not s:
        return None
    if help_filter and any(t in ("--help", "-h", "help", "--dry-run") for t in s):
        return None   # read-only invocations
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


def _stripped_head(seg):
    """Head token after the spike's prefix stripping, for denylist/nested checks."""
    s = [t for t in seg if not REDIR_RE.match(t)]
    while s and (ENV_ASSIGN_RE.match(s[0]) or s[0] in ("sudo", "timeout", "nohup", "exec")):
        s = s[1:] if s[0] != "timeout" else s[2:]
    if not s:
        return None, s
    return s[0].split("/")[-1], s


def _seg_reason(seg, help_filter=True):
    """Classify one segment into (reason, action|None)."""
    if seg and seg[0] == "__unparsed__":
        return "unparsed", None
    head, s = _stripped_head(seg)
    if head is None:
        return "not_infra", None
    if head in DENYLIST_HEADS:
        return "denylisted_head", None
    if head in NESTED_HEADS or (head in ("bash", "sh") and "-c" in s):
        return "nested_unanalyzed", None
    if help_filter and any(t in ("--help", "-h", "help", "--dry-run") for t in s):
        return "read_only_flag", None
    a = classify(seg, help_filter=help_filter)
    if a is None:
        return "not_infra", None
    if not INFRA.match(a["vtool"]):
        return "not_infra", None
    return "action", a


def normalize_exec(cmd, help_filter=True, heredoc_skip=True):
    """Normalize one exec shell string.

    Returns dict with actions, counts, heredoc_lines_skipped and per-segment
    reasons.
    """
    segs, heredoc_lines = segments(cmd, heredoc_skip=heredoc_skip)
    actions, reasons, action_segments = [], [], []
    counts = {"segments": 0, "unparsed": 0, "nested_unanalyzed": 0}
    for seg in segs:
        counts["segments"] += 1
        reason, a = _seg_reason(seg, help_filter=help_filter)
        reasons.append(reason)
        if reason == "unparsed":
            counts["unparsed"] += 1
        elif reason == "nested_unanalyzed":
            counts["nested_unanalyzed"] += 1
        elif reason == "action":
            actions.append({"vtool": a["vtool"], "args": a["args"]})
            # full segment text of this action (AC #19 action_key input)
            action_segments.append(" ".join(seg))
    return {
        "actions": actions,
        "segment_reasons": reasons,
        "action_segments": action_segments,
        "heredoc_lines_skipped": heredoc_lines,
        **counts,
    }


def map_structured(tool, args):
    """Map OpenClaw structured tool calls to vtools (AC #9).

    cron -> cron.<verb>; edit/apply_patch -> file.edit{path, removed_text};
    write -> file.edit{path, removed_text: null} (prior content unknown offline
    -> weakens_policy logs fact_missing).
    """
    args = args or {}
    if tool == "cron":
        verb = str(args.get("action") or args.get("verb") or "")
        verb = {"remove": "rm", "delete": "rm", "pause": "disable"}.get(verb, verb)
        if verb in ("disable", "rm", "edit", "update", "enable", "add", "list"):
            return {"vtool": f"cron.{verb}", "args": {"jobId": args.get("jobId") or args.get("id")}}
        return None
    if tool in ("edit", "apply_patch"):
        old = str(args.get("oldText") or args.get("old_string") or args.get("old") or "")
        new = str(args.get("newText") or args.get("new_string") or args.get("new") or "")
        removed = "".join(x for x in [old] if x and x not in new) or None
        if old and new:
            old_lines = set(old.split("\n"))
            new_lines = set(new.split("\n"))
            removed = "\n".join(l for l in old.split("\n") if l in old_lines - new_lines) or None
        return {"vtool": "file.edit", "args": {"path": args.get("path") or args.get("file_path"),
                                               "removed_text": removed}}
    if tool == "write":
        return {"vtool": "file.edit", "args": {"path": args.get("path") or args.get("file_path"),
                                               "removed_text": None}}
    return None


def normalize_cmd(cmd, help_filter=True, heredoc_skip=True):
    return normalize_exec(cmd, help_filter=help_filter, heredoc_skip=heredoc_skip)


def score_corpus(path, help_filter=True, heredoc_skip=True):
    """Score the normalizer against a labeled corpus (fixtures/normalizer/cases.jsonl).

    Each case: {"cmd": str, "expect": [vtool, ...], "family": str}. A case with
    expect == [] is a negative. Precision/recall are computed over expected vs
    produced (cmd, vtool multiset) action matches.
    """
    cases = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if "cmd" in d:
                cases.append(d)
    tp = fp = fn = 0
    negatives = 0
    families = {}
    per_case = []
    for c in cases:
        expect = sorted(c.get("expect", []))
        if not expect:
            negatives += 1
        fam = c.get("family", "")
        families[fam] = families.get(fam, 0) + 1
        out = normalize_exec(c["cmd"], help_filter=help_filter, heredoc_skip=heredoc_skip)
        got = sorted(a["vtool"] for a in out["actions"])
        e, g = list(expect), list(got)
        matched = 0
        for v in list(e):
            if v in g:
                g.remove(v)
                e.remove(v)
                matched += 1
        tp += matched
        fp += len(g)
        fn += len(e)
        per_case.append({"family": fam, "expect": expect, "got": got, "ok": expect == got})
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    return {
        "cases": len(cases),
        "negatives": negatives,
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "families": dict(sorted(families.items())),
        "failures": [c for c in per_case if not c["ok"]],
        "synthetic": True,
    }


def render(out, fmt):
    if fmt == "json":
        return json.dumps(out, sort_keys=True, indent=2)
    if "precision" in out:
        lines = [f"corpus: {out['cases']} cases ({out['negatives']} negatives)",
                 f"precision {out['precision']:.4f}  recall {out['recall']:.4f}"]
        for f in out["failures"]:
            lines.append(f"  MISMATCH [{f['family']}] expect={f['expect']} got={f['got']}")
        return "\n".join(lines)
    lines = [f"actions: {len(out['actions'])}  segments: {out['segments']}"
             f"  unparsed: {out['unparsed']}  nested: {out['nested_unanalyzed']}"
             f"  heredoc lines skipped: {out['heredoc_lines_skipped']}"]
    for a in out["actions"]:
        lines.append(f"  {a['vtool']} {json.dumps(a['args'], sort_keys=True)}")
    return "\n".join(lines)
