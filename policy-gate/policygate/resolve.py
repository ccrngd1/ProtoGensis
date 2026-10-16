"""RESOLVE: structural static checks, deterministic, no LLM (AC #7).

Classes:
  (a) write-scope       REPAIR: authorization/confirmation predicate bound to
                        read-only vtools re-scoped to writes; read-gate
                        predicates (channel_shared) left alone
  (b) argument-signature REPAIR: a predicate whose `reads` keys are not params
                        of a bound vtool is unbound from it
  (c) self-blocking      REPAIR: vtools in Enable[predicate] stripped from guard set
  (d) unscoped-wildcard  REJECT
  (e) domain-satisfiability REJECT: unknown predicate/vtool/out-of-domain params
  (f) cross-rule contradiction  CONFLICT -> ambiguity queue (never auto-resolved);
                        whole-file protection narrowed to rule-bearing sections (REPAIR)
  (g) subject-scope      kept with subjects: UNDECIDED + ambiguity item
  (h) shadowing (audit)  listed

Each report row: {id, outcome ∈ {REPAIR, REJECT, CONFLICT, SUBJECT_UNDECIDED,
SHADOW, OK}, class, detail}. `rules check` exits 1 if anything is rejected or
repaired.
"""

import fnmatch

from . import rules, vocab, vtools as vtools_mod

READ_GATE_PREDICATES = {"channel_shared"}

# Call-level fields every action carries (set by the adapter, not passed as a
# vtool argument). A predicate reading only these is signature-compatible with
# every vtool, so argument-signature (b) must not unbind it (e.g.
# quiet_hours_utc reads the call timestamp, which is not in any vtool's params).
CALL_FIELDS = {"ts"}


def _expand_tools(patterns, known):
    out = set()
    for pat in patterns:
        for v in known:
            if fnmatch.fnmatch(v, pat):
                out.add(v)
    return sorted(out)


def resolve(candidates, vtool_schema=None):
    """Run RESOLVE over candidate dicts.

    Returns (kept_rules, report) where kept_rules are validated/repaired rule
    dicts and report is a list of row dicts (one or more per candidate).
    """
    schema = vtool_schema or vtools_mod.load()
    known_vtools = set(schema)
    report = []
    kept = []

    for c in candidates:
        cid = c.get("id", "<no-id>")

        # type-derivability (AC #5): explicit type field is a rejection
        try:
            rule = rules.candidate_to_rule(c)
        except rules.RuleError as e:
            report.append({"id": cid, "outcome": "REJECT", "class": "type-not-derivable",
                           "detail": str(e)})
            continue

        pred = rule["predicate"]

        # (d) unscoped wildcard
        if rule["tools"] == ["*"] or "*" in rule["tools"] and len(rule["tools"]) == 1:
            report.append({"id": cid, "outcome": "REJECT", "class": "unscoped-wildcard",
                           "detail": "unscoped wildcard '*' would gate every tool incl. reads"})
            continue

        # (e) domain satisfiability: unknown predicate
        if not vocab.is_known(pred):
            report.append({"id": cid, "outcome": "REJECT", "class": "domain-satisfiability",
                           "detail": f"unknown predicate {pred!r}"})
            continue
        if not vocab.domain_ok(pred, rule["params"]):
            report.append({"id": cid, "outcome": "REJECT", "class": "domain-satisfiability",
                           "detail": f"params {rule['params']} outside declared domain of {pred}"})
            continue

        # expand tool patterns against the schema; unknown vtool -> REJECT (e)
        unknown = [t for t in rule["tools"]
                   if not any(fnmatch.fnmatch(v, t) for v in known_vtools)]
        if unknown:
            report.append({"id": cid, "outcome": "REJECT", "class": "domain-satisfiability",
                           "detail": f"unknown vtool(s) {unknown}"})
            continue
        tools = _expand_tools(rule["tools"], known_vtools)

        spec = vocab.VOCAB.get(pred, {})
        reads = spec.get("reads", [])
        kind = spec.get("kind", "")

        # (a) write-scope: authorization/confirmation predicate on read-only vtools
        if pred in ("cc_authorized", "confirmation_fresh") and pred not in READ_GATE_PREDICATES \
                and kind != "read-gate":
            ro = [t for t in tools if not schema.get(t, {}).get("is_write", False)]
            if ro:
                tools = [t for t in tools if schema.get(t, {}).get("is_write", False)]
                rule["resolve"].append(f"write-scope: dropped read-only {ro}")
                report.append({"id": cid, "outcome": "REPAIR", "class": "write-scope",
                               "detail": f"authorization bound to read-only {ro} -> dropped"})

        # (b) argument-signature consistency (over arg reads only; call-level
        # fields like the timestamp exist on every action)
        arg_reads = [r for r in reads if r not in CALL_FIELDS]
        if arg_reads and arg_reads != ["*"]:
            bad = [t for t in tools
                   if not set(arg_reads) & set(schema.get(t, {}).get("params", []))]
            # only when the predicate truly reads arg keys the vtool lacks
            bad = [t for t in bad
                   if not any(r in schema.get(t, {}).get("params", []) for r in arg_reads)]
            if bad:
                tools = [t for t in tools if t not in bad]
                rule["resolve"].append(f"argument-signature: {reads} not params of {bad} -> unbound")
                report.append({"id": cid, "outcome": "REPAIR", "class": "argument-signature",
                               "detail": f"{reads} not params of {bad} -> unbound"})

        # (c) self-blocking / deadlock: strip Enable[predicate] vtools
        enable_pats = spec.get("enable", [])
        selfblock = [t for t in tools
                     if any(fnmatch.fnmatch(t, e) for e in enable_pats if e not in ("cc_turn",))]
        if selfblock:
            tools = [t for t in tools if t not in selfblock]
            rule["resolve"].append(f"self-blocking: stripped {selfblock}")
            report.append({"id": cid, "outcome": "REPAIR", "class": "self-blocking",
                           "detail": f"vtools in Enable[{pred}] stripped: {selfblock}"})

        # (f) whole-file protection narrowed to rule-bearing sections
        if c.get("whole_file_protection"):
            rule["resolve"].append("contradiction: whole-file protection narrowed to rule-bearing sections")
            rule["section_scoped"] = True
            report.append({"id": cid, "outcome": "REPAIR", "class": "contradiction",
                           "detail": "whole-file protection narrowed to rule-bearing sections"})

        if not tools:
            report.append({"id": cid, "outcome": "REJECT", "class": "no-operable-tool",
                           "detail": "no operable tool after repairs"})
            continue

        rule["tools"] = tools

        # (g) subject scope: subjects undecidable
        if rule["subjects"] in ("UNDECIDED", ["UNDECIDED"]) or c.get("subjects_undecided"):
            rule["subjects"] = "UNDECIDED"
            report.append({"id": cid, "outcome": "SUBJECT_UNDECIDED", "class": "subject-scope",
                           "detail": "subjects cannot be determined from the bundle; evaluated both ways"})

        kept.append(rule)

    # (f) cross-rule contradiction across different sources
    _detect_conflicts(kept, report)
    # (h) shadowing in audit mode
    _detect_shadows(kept, report)
    return kept, report


def _src_of(rule):
    src = rule.get("src") or {}
    if isinstance(src, dict):
        return src.get("file") or src.get("source") or ""
    return str(src)


def _detect_conflicts(kept, report):
    """A whole-file/forbidden protection on a vtool that another rule from a
    different source *requires* writes to (research §3.3: "never edit MEMORY.md"
    vs "update memory files") -> CONFLICT, sent to the ambiguity queue and never
    auto-resolved. Normal PRECONDITION+FORBIDDEN layering on the same tool is
    not a contradiction; the signal is an explicit `requires_write` obligation."""
    forbids = [r for r in kept if r["type"] == "FORBIDDEN"]
    requires = [r for r in kept if r.get("requires_write")]
    for a in forbids:
        for b in requires:
            if a["id"] == b["id"] or _src_of(a) == _src_of(b):
                continue
            shared = set(a["tools"]) & set(b["tools"])
            if not shared:
                continue
            report.append({"id": f"{a['id']}~{b['id']}", "outcome": "CONFLICT",
                           "class": "contradiction",
                           "detail": f"{a['id']} forbids writes that {b['id']} requires "
                                     f"on {sorted(shared)} -> ambiguity queue"})


def _detect_shadows(kept, report):
    """A broad rule whose guard set covers every tool a more specific rule
    guards is listed (audit mode must still evaluate the specific rule, or the
    more serious clause disappears; research §3.3). Reported across types,
    since a broad PRECONDITION typically hides a specific FORBIDDEN."""
    for broad in kept:
        for specific in kept:
            if broad is specific or broad["id"] == specific["id"]:
                continue
            if broad["predicate"] == specific["predicate"]:
                continue
            bt, st = set(broad["tools"]), set(specific["tools"])
            if st and st <= bt and len(bt) > len(st):
                report.append({"id": f"{broad['id']}>{specific['id']}", "outcome": "SHADOW",
                               "class": "shadowing",
                               "detail": f"{broad['id']} ({broad['predicate']}) shadows "
                                         f"{specific['id']} ({specific['predicate']}) on {sorted(st)}"})
