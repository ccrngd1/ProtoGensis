"""Version pinning for replay --profile pinned (AC #14). DETERMINISTIC.

A rule is IN FORCE at time t iff its source clause (matched by
normalized-clause sha256, prefix allowed, as in candidates_check) is present
in the bundle resolved at t. Platform rules use `effective_from` (ISO-8601 or
"unknown"); a candidate whose id matches a bundle platform rule inherits that
rule's effective_from. Built-in rules (clause_ref {"builtin": ...}) are in
force from the time their src.file exists in the bundle (or from the first
bundle version when they name no file).

Version resolution is memoized: the per-source commit timeline comes from one
gitread `log` per source (bundle.history), the bundle text from one `show` per
(sha, path) — never one git call per action. Verdict classes per reading:

  BLOCK            an in-force rule fires
  NO_RULE_IN_FORCE no in-force rule fires, but a rule present in a LATER
                   version would fire under that reading
  VERSION_UNKNOWN  the only rule that would fire has effective_from "unknown"
                   (or the action has no usable timestamp, R14)
  ALLOW            nothing fires; a rule that fired only in EARLIER versions
                   (since removed) is listed as a removal, never a violation

NO_RULE_IN_FORCE and VERSION_UNKNOWN are never violations; they feed the
`retroactive_rules` aggregate. `--retroactive` additionally evaluates every
version's rules against every action, reported under the heading
"COUNTERFACTUAL (retroactive policy; not violations)".
"""

import bisect
import hashlib

from . import bundle as bundle_mod
from . import check as check_mod
from . import parse as parse_mod

COUNTERFACTUAL_LABEL = "COUNTERFACTUAL (retroactive policy; not violations)"

# clause classes that may gate (runtime predicates); obligation / text-only /
# ambiguous candidates never produce a BLOCK (AC #17e)
GATING_CLASSES = {"gateable", "temporal", "ordering", "counting"}
NON_GATING_ROUTING = {
    "obligation": "obligations_report",
    "text-only": "not_evaluated",
    "ambiguous": "ambiguity_item",
}


def route_rules(rules):
    """Split rules by clause class: {gating, obligation, ambiguous, text_only}."""
    out = {"gating": [], "obligation": [], "ambiguous": [], "text_only": []}
    for r in rules:
        cls = r.get("class", "gateable")
        if cls in GATING_CLASSES:
            out["gating"].append(r)
        elif cls == "obligation":
            out["obligation"].append(r)
        elif cls == "ambiguous":
            out["ambiguous"].append(r)
        else:
            out["text_only"].append(r)
    return out


def routing_table(candidates):
    """Per-class candidate counts with their replay routing (for compile and
    candidates check reports)."""
    counts = {}
    for c in candidates:
        cls = c.get("class", "gateable")
        counts[cls] = counts.get(cls, 0) + 1
    table = {}
    for cls in sorted(counts):
        routing = "gate" if cls in GATING_CLASSES else \
            NON_GATING_ROUTING.get(cls, "not_evaluated")
        table[cls] = {"count": counts[cls], "routing": routing}
    return table


def _norm_ts(ts):
    """ISO-8601 UTC timestamp -> comparable 'YYYY-MM-DDTHH:MM:SS' string
    (strips Z and fractional seconds; short forms are padded)."""
    t = str(ts or "").rstrip("Z").split(".")[0].split("+")[0]
    if len(t) == 16:          # YYYY-MM-DDTHH:MM
        t += ":00"
    return t[:19]


class PinnedPolicy:
    """Resolves which rules are in force at each action time."""

    def __init__(self, root, bundle_toml, rules):
        self.pb = bundle_mod.PolicyBundle.load(bundle_toml, root)
        self.rules = rules
        hist = bundle_mod.history(self.pb)
        # per source: ascending [(time, sha, kind)]
        self._timeline = {}
        times = set()
        for path, h in hist.items():
            entries = [(_norm_ts(c["time"]), c["sha"], c["kind"])
                       for c in h.get("commits", [])]
            self._timeline[path] = entries
            times.update(t for t, _, _ in entries)
        self.boundaries = sorted(times)
        self._show_cache = {}
        self._snapshot_cache = {}
        # platform effective_from by rule id (bundle platform_rules file)
        self._platform_ef = {r["id"]: r.get("effective_from", "unknown")
                             for r in self.pb.platform_rules}
        # presence[rule_id] = [bool per boundary]
        self.presence = {}
        for i in range(len(self.boundaries)):
            snap = self._snapshot(i)
            for r in rules:
                self.presence.setdefault(r["id"], []).append(
                    self._present_in_snapshot(r, snap))
        self.commits_used = sorted({
            sha for entries in self._timeline.values()
            for _, sha, kind in entries if kind != "D"})

    # -- bundle snapshots -------------------------------------------------

    def _source_at(self, path, boundary_idx):
        """(sha|None) for one source at boundary index (None = absent)."""
        bt = self.boundaries[boundary_idx]
        sha = None
        for t, s, kind in self._timeline.get(path, []):
            if t <= bt:
                sha = None if kind == "D" else s
            else:
                break
        return sha

    def _snapshot(self, boundary_idx):
        """Memoized snapshot at a boundary: clause/section hash sets per source
        plus the set of present source paths. Keyed by the per-source commit
        tuple so identical resolutions share one parse."""
        key = tuple((s["path"], self._source_at(s["path"], boundary_idx))
                    for s in self.pb.sources)
        if key in self._snapshot_cache:
            return self._snapshot_cache[key]
        hashes_by_file, present = {}, set()
        for s in self.pb.sources:
            sha = self._source_at(s["path"], boundary_idx)
            if sha is None:
                continue
            present.add(s["path"])
            text = self._show(sha, s["path"])
            if text is None:
                continue
            if s["kind"] == "cron_payloads":
                clauses = parse_mod.parse_cron_payloads(text, s["path"], sha)
            else:
                clauses, _ = parse_mod.parse_markdown(text, s["path"], sha,
                                                      s["subjects"])
            hs = set()
            for c in clauses:
                hs.add(c.clause_sha256)
                hs.add(c.section_hash)
            hashes_by_file[s["path"]] = hs
        snap = {"present": present, "hashes": hashes_by_file,
                "commits": {p: sha for (p, sha) in key if sha}}
        self._snapshot_cache[key] = snap
        return snap

    def _show(self, sha, path):
        k = (sha, path)
        if k not in self._show_cache:
            from . import gitread
            try:
                self._show_cache[k] = gitread.show(self.pb.root, sha, path)
            except gitread.GitReadError:
                self._show_cache[k] = None
        return self._show_cache[k]

    def _present_in_snapshot(self, rule, snap):
        ef = self._effective_from(rule)
        if ef is not None:
            return False  # dated/unknown platform rules use effective_from
        ref = rule.get("clause_ref") or {}
        want_file = ref.get("file")
        ch = ref.get("clause_sha256") or ref.get("section_hash")
        if ref.get("builtin") or not ch:
            # builtin: in force from the time its source file exists
            src_file = (rule.get("src") or {}).get("file") or want_file
            if src_file:
                return src_file in snap["present"]
            return bool(snap["present"])
        files = [want_file] if want_file else list(snap["hashes"])
        for f in files:
            for h in snap["hashes"].get(f, ()):
                if h.startswith(ch):
                    return True
        return False

    # -- in-force resolution ----------------------------------------------

    def _effective_from(self, rule):
        """Normalized effective_from for a platform-dated rule, else None.
        A candidate whose id matches a bundle platform rule inherits it."""
        ef = rule.get("effective_from")
        if ef is None:
            ef = self._platform_ef.get(rule["id"])
        if ef is None:
            return None
        return "unknown" if ef == "unknown" else _norm_ts(ef)

    def _boundary_idx(self, t):
        """Index of the latest boundary <= t, or -1."""
        return bisect.bisect_right(self.boundaries, _norm_ts(t)) - 1

    def status_at(self, rule, ts):
        """One of in_force | later | removed | unknown | never for rule at ts."""
        ef = self._effective_from(rule)
        if ef == "unknown":
            return "unknown"
        nt = _norm_ts(ts)
        if ef is not None:
            return "in_force" if nt >= ef else "later"
        pres = self.presence.get(rule["id"], [])
        idx = self._boundary_idx(ts)
        if idx >= 0 and idx < len(pres) and pres[idx]:
            return "in_force"
        if any(pres[idx + 1:]):
            return "later"
        if any(pres[:idx + 1]):
            return "removed"
        return "never"

    def commits_at(self, ts):
        """{path: sha} of the bundle resolution used for an action time."""
        idx = self._boundary_idx(ts)
        if idx < 0:
            return {}
        return dict(self._snapshot(idx)["commits"])

    def commits_by_source(self):
        """{path: [shas]} of every non-delete commit per bundle source (the
        commits version resolution can pin to) — for manifest.json."""
        return {p: [sha for _, sha, kind in self._timeline.get(p, []) if kind != "D"]
                for p in sorted(self._timeline)}

    def per_version_groups(self):
        """{base_id: [ids]} for per-version candidate overrides (candidates
        sharing a `version_of` field keep one rule per version; AC #14)."""
        groups = {}
        for r in self.rules:
            base = r.get("version_of")
            if base:
                groups.setdefault(base, []).append(r["id"])
        return {b: sorted(ids) for b, ids in sorted(groups.items())}


def classify_action(pin, vtool, call, facts_by_reading, rules, readings):
    """Pinned verdicts for one action.

    Returns (verdicts, fired_by, retro, rule_rows) where
      verdicts  {reading: verdict_class}
      fired_by  {reading: [in-force rule ids that fired]}
      retro     {reading: {"later": [...], "unknown": [...], "removed": [...]}}
      rule_rows [{"id", "status", "fired": {reading: bool}}] per binding rule
                (feeds (rule, vtool) firing rates: n counts in-force
                evaluations whether or not the rule fired).
    `rules` must already be gating-class only.
    """
    ts = call.get("ts") or ""
    ts_known = bool(_norm_ts(ts))
    binding = [r for r in rules if vtool in r["tools"]]
    rule_rows = []
    fires = {}  # rule id -> {reading: bool}
    for r in binding:
        status = pin.status_at(r, ts) if ts_known else "ts_missing"
        fires[r["id"]] = {
            rd: bool(check_mod.check(vtool, call, facts_by_reading[rd], [r])["fired"])
            for rd in readings}
        rule_rows.append({"id": r["id"], "status": status,
                          "fired": fires[r["id"]]})
    verdicts, fired_by, retro = {}, {}, {}
    for rd in readings:
        fired_now, later, unknown, removed = [], [], [], []
        for row in rule_rows:
            if not row["fired"][rd]:
                continue
            status = row["status"]
            if status == "in_force":
                fired_now.append(row["id"])
            elif status == "later":
                later.append(row["id"])
            elif status in ("unknown", "ts_missing"):
                unknown.append(row["id"])
            elif status == "removed":
                removed.append(row["id"])
            # "never": rule exists in no version -> cannot gate anything
        if fired_now:
            verdicts[rd] = "BLOCK"
        elif later:
            verdicts[rd] = "NO_RULE_IN_FORCE"
        elif unknown:
            verdicts[rd] = "VERSION_UNKNOWN"
        else:
            verdicts[rd] = "ALLOW"
        fired_by[rd] = sorted(fired_now)
        retro[rd] = {"later": sorted(later), "unknown": sorted(unknown),
                     "removed": sorted(removed)}
    return verdicts, fired_by, retro, rule_rows


def counterfactual_fired(vtool, call, facts_by_reading, rules, readings):
    """--retroactive: every version's rules against this action (which rules
    would fire per reading, in-force or not)."""
    binding = [r for r in rules if vtool in r["tools"]]
    out = {}
    for rd in readings:
        res = check_mod.check(vtool, call, facts_by_reading[rd], binding)
        out[rd] = sorted(res["fired"])
    return out
