"""results lint: enumerated-vocabulary check for results/ (AC #21). + results get helper.

Fails any results JSON containing a string value outside the enumerated
vocabulary (vtool names, rule IDs, agent IDs, principal classes, reading names,
verdict classes, YYYY-MM buckets, sha256 hex, profile names, plus a small set
of schema/structural strings). This keeps per-action transcript detail
(label_context, redacted commands) out of committed results.
"""

import json
import os
import re

from . import vocab, readings as readings_mod
from .baselines.keyword import LABEL as KEYWORD_BASELINE_LABEL
from .pinning import COUNTERFACTUAL_LABEL
from .replay import VERDICT_CLASSES

PRINCIPALS = {"cc_direct", "cc_relayed", "agent", "cron", "heartbeat", "system",
              "tool_content", "unknown"}
PROFILES = {"pinned", "spike-parity"}
PROVENANCE = {"heuristic", "typed"}
LABEL_STATUS = {"provisional", "confirmed"}
# the labeled counterfactual heading and the keyword baseline's exact label
# string are part of the results schema (AC #14, #20)
SCHEMA_STRINGS = {"policygate-aggregates-v1", COUNTERFACTUAL_LABEL,
                  KEYWORD_BASELINE_LABEL}

VTOOLS = {"cron.list", "cron.add", "cron.disable", "cron.enable", "cron.rm",
          "cron.edit", "cron.update", "gateway.restart", "gateway.stop",
          "service.restart", "service.stop", "service.disable", "docker.restart",
          "docker.stop", "docker.rm", "docker.compose", "config.set",
          "crontab.write", "file.read", "file.edit", "message.send", "backup.create"}
# rule ID grammar: PREFIX-TYPE-NN with an optional per-version lowercase
# suffix (CAB-PRE-15a / CAB-PRE-15b keep one rule per clause version, AC #14)
RULE_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*-[A-Z0-9]+-\d+[a-z]?$|^(INF|PLAT|TWR|SYN|AMB)[-A-Z0-9]*$")
AGENT_RE = re.compile(r"^[a-z][a-z0-9-]*$")
YYYYMM_RE = re.compile(r"^\d{4}-\d{2}$")
YYYYMMDD_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$|^[0-9a-f]{7,40}$")
KIND_RE = re.compile(r"^(legacy-archive|trajectory|fixture)$")


def _enumerated(s):
    if s in VTOOLS or s in PRINCIPALS or s in PROFILES or s in PROVENANCE \
            or s in SCHEMA_STRINGS or s in VERDICT_CLASSES \
            or s in LABEL_STATUS or s in readings_mod.READINGS:
        return True
    if vocab.is_known(s):
        return True
    if RULE_ID_RE.match(s) or AGENT_RE.match(s) or YYYYMM_RE.match(s) \
            or YYYYMMDD_RE.match(s) or SHA_RE.match(s) or KIND_RE.match(s):
        return True
    # research_values ids / parity_check ids are snake_case identifiers
    if re.match(r"^[a-z][a-z0-9_]*$", s):
        return True
    if s == "":
        return True
    return False


def _walk_strings(obj, path="$"):
    bad = []
    if isinstance(obj, str):
        if not _enumerated(obj):
            bad.append((path, obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            # keys are structural (vtool names, rule ids, etc.) — also checked
            if isinstance(k, str) and not _enumerated(k):
                bad.append((f"{path}.<key>", k))
            bad.extend(_walk_strings(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad.extend(_walk_strings(v, f"{path}[{i}]"))
    return bad


def lint_file(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return _walk_strings(data)


def lint_dir(path):
    if os.path.isfile(path):
        files = [path]
    else:
        files = [os.path.join(path, f) for f in sorted(os.listdir(path))
                 if f.endswith(".json")]
    all_bad = []
    for fp in files:
        for p, s in lint_file(fp):
            all_bad.append(f"{os.path.basename(fp)} {p}: non-enumerated string {s!r}")
    if all_bad:
        return False, ["RESULTS LINT FAIL:"] + all_bad
    return True, [f"RESULTS LINT OK ({len(files)} file(s))"]


def get_key(path, keypath):
    """results get <file> <key.path>: fetch a nested value (dot/bracket path)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cur = data
    for part in re.split(r"\.|\[|\]", keypath or ""):
        if part == "":
            continue
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            cur = cur[part]
    return cur if not isinstance(cur, (dict, list)) else json.dumps(cur, sort_keys=True)
