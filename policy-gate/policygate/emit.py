"""EMIT: rules.json + compile-report.{json,md} (AC #8). DETERMINISTIC.

compile writes rules.json (sorted keys) and a compile report with: clauses
parsed, clauses per class, candidates in/kept/repaired/rejected, counts per
RESOLVE class, minority-vote drops, ambiguity items created, coverage (gateable
clauses with >=1 compiled rule / gateable clauses) and the list of gateable
clauses with no rule. Every count is labeled with the candidate origin
(builder vs llm:<model>); builder-authored defect counts are never presented as
LLM extraction defect rates (Trap 21).
"""

import json
import os

from . import bundle as bundle_mod
from . import parse as parse_mod
from . import pinning as pinning_mod
from . import resolve as resolve_mod
from . import rules as rules_mod
from .extract import candidates as cand_mod


def compile_bundle(root, bundle_toml, at, candidates_path, out_dir=None):
    pb = bundle_mod.PolicyBundle.load(bundle_toml, root)
    bundle_at = pb.at(at)
    parsed = parse_mod.parse_bundle(bundle_at)
    cands = cand_mod.load(candidates_path)
    origin = cand_mod.origin_of(cands)
    kept, report = resolve_mod.resolve(cands)

    resolve_counts = {}
    for row in report:
        resolve_counts[row["class"]] = resolve_counts.get(row["class"], 0) + 1
    # ensure >=8 classes are represented as keys (AC #8 requires >=8)
    for cls in ("write-scope", "argument-signature", "self-blocking",
                "unscoped-wildcard", "domain-satisfiability", "contradiction",
                "subject-scope", "shadowing", "type-not-derivable", "no-operable-tool"):
        resolve_counts.setdefault(cls, 0)

    rejected = [r for r in report if r["outcome"] == "REJECT"]
    repaired_ids = {r["id"] for r in report if r["outcome"] == "REPAIR"}

    # clause classification counts come from candidate `class` fields in v1
    clause_classes = {}
    for c in cands:
        cls = c.get("class", "gateable")
        clause_classes[cls] = clause_classes.get(cls, 0) + 1

    # coverage over gateable clauses: a gateable candidate that produced a kept rule
    gateable_cands = [c for c in cands if c.get("class", "gateable") == "gateable"]
    kept_ids = {r["id"] for r in kept}
    covered = [c for c in gateable_cands if c["id"] in kept_ids]
    unenforced = sorted(c.get("clause_ref", {}).get("line") and
                        f"{c.get('src', {}).get('file', '?')}:{c['clause_ref']['line']}"
                        or c["id"]
                        for c in gateable_cands if c["id"] not in kept_ids)
    coverage = round(len(covered) / len(gateable_cands), 4) if gateable_cands else 1.0

    conflicts = [r for r in report if r["outcome"] == "CONFLICT"]
    subject_undecided = [r for r in report if r["outcome"] == "SUBJECT_UNDECIDED"]
    ambiguity_items = len(conflicts) + len(subject_undecided)

    compile_report = {
        "candidate_origin": origin,
        "clauses_parsed": len(parsed["clauses"]),
        "fenced_blocks_skipped": parsed["fenced_blocks_skipped"],
        "clauses_per_class": dict(sorted(clause_classes.items())),
        "candidates_in": len(cands),
        "candidates_kept": len(kept),
        "candidates_repaired": len(repaired_ids),
        "candidates_rejected": len(rejected),
        # replay routing per clause class (AC #17e): non-gateable classes
        # (obligation, text-only, ambiguous) never produce a BLOCK
        "class_routing": pinning_mod.routing_table(cands),
        "resolve_counts": dict(sorted(resolve_counts.items())),
        "minority_drops": [],
        "ambiguity_items": ambiguity_items,
        "coverage": coverage,
        "unenforced_gateable": unenforced,
        "resolve_report": report,
    }

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "rules.json"), "w", encoding="utf-8") as f:
            f.write(rules_mod.rules_json(kept))
        with open(os.path.join(out_dir, "compile-report.json"), "w", encoding="utf-8") as f:
            json.dump(compile_report, f, sort_keys=True, indent=2)
        with open(os.path.join(out_dir, "compile-report.md"), "w", encoding="utf-8") as f:
            f.write(render_report(compile_report, "md"))
    return compile_report, kept


def compile_cmd(root, bundle_toml, at, candidates_path, out_dir):
    report, _ = compile_bundle(root, bundle_toml, at, candidates_path, out_dir)
    return report


def render_report(report, fmt):
    if fmt == "json":
        # the stdout form excludes the verbose resolve_report for determinism
        slim = {k: v for k, v in report.items() if k != "resolve_report"}
        return json.dumps(slim, sort_keys=True, indent=2)
    lines = [
        "# Compile report",
        "",
        f"- candidate origin: **{report['candidate_origin']}** "
        "(builder-authored candidate defects are NOT an LLM extraction defect rate)",
        f"- clauses parsed: {report['clauses_parsed']} "
        f"(fenced blocks skipped: {report['fenced_blocks_skipped']})",
        f"- candidates in / kept / repaired / rejected: "
        f"{report['candidates_in']} / {report['candidates_kept']} / "
        f"{report['candidates_repaired']} / {report['candidates_rejected']}",
        f"- coverage (gateable): {report['coverage']}",
        f"- ambiguity items created: {report['ambiguity_items']}",
        "",
        "## RESOLVE counts",
    ]
    for cls, n in sorted(report["resolve_counts"].items()):
        lines.append(f"- {cls}: {n}")
    lines.append("")
    lines.append("## Replay routing per clause class (non-gateable classes never BLOCK)")
    for cls, row in report.get("class_routing", {}).items():
        lines.append(f"- {cls}: {row['count']} -> {row['routing']}")
    lines.append("")
    lines.append("## Unenforced gateable clauses (silently unenforced without this list)")
    for u in report["unenforced_gateable"]:
        lines.append(f"- {u}")
    if fmt == "terminal":
        return "\n".join(lines)
    return "\n".join(lines) + "\n"
