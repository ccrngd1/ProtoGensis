"""Rule-4 check for aggregators/selectors.

An aggregator/selector must:
  (a) be from a family NOT on the panel  -> violation is a HARD ERROR.
  (b) have pilot single-model accuracy >= every panel member on that task set
      (point estimates; CI overlap is reported, not enforced).

The A4b weak aggregator is exempt from (b) BY DESIGN (that is the arm's
purpose) and must be labeled that way in all outputs.
"""

from dataclasses import dataclass, field


class Rule4FamilyViolation(Exception):
    """Aggregator family is on the panel: hard error."""


@dataclass
class Rule4Result:
    ok: bool
    aggregator: str
    panel: list
    exempt_from_b: bool
    label: str
    accuracy_check: dict = field(default_factory=dict)
    ci_overlap_notes: list = field(default_factory=list)


def check_rule4(
    aggregator_id: str,
    aggregator_family: str,
    panel: list,                      # [(profile_id, family)]
    accuracies: dict | None = None,   # profile_id -> (acc, ci_lo, ci_hi); None pre-pilot
    task_set: str = "",
    exempt_from_b: bool = False,
) -> Rule4Result:
    """Validate rule 4. Raises Rule4FamilyViolation on (a); (b) failures make
    ok=False unless exempt_from_b."""
    panel_families = {fam for _, fam in panel}
    if aggregator_family in panel_families:
        raise Rule4FamilyViolation(
            f"aggregator {aggregator_id} (family {aggregator_family}) is from a "
            f"family on the panel {sorted(panel_families)}; rule 4(a) is a hard error"
        )
    label = (
        "WEAK-BY-DESIGN (exempt from rule-4(b): aggregator capability "
        "deliberately below panel)" if exempt_from_b else "rule-4 checked"
    )
    result = Rule4Result(
        ok=True,
        aggregator=aggregator_id,
        panel=[pid for pid, _ in panel],
        exempt_from_b=exempt_from_b,
        label=label,
    )
    if accuracies is None or exempt_from_b:
        if accuracies and exempt_from_b:
            result.accuracy_check = _acc_check(aggregator_id, panel, accuracies, task_set)
        return result
    result.accuracy_check = _acc_check(aggregator_id, panel, accuracies, task_set)
    result.ok = result.accuracy_check["passes_b"]
    result.ci_overlap_notes = result.accuracy_check["ci_overlap"]
    return result


def _acc_check(aggregator_id, panel, accuracies, task_set):
    if aggregator_id not in accuracies:
        return {"passes_b": False, "reason": f"no pilot accuracy for {aggregator_id}",
                "ci_overlap": []}
    agg_acc, agg_lo, agg_hi = accuracies[aggregator_id]
    passes = True
    overlap = []
    for pid, _ in panel:
        if pid not in accuracies:
            passes = False
            overlap.append(f"no pilot accuracy for panel member {pid}")
            continue
        acc, lo, hi = accuracies[pid]
        if agg_acc < acc:
            passes = False
        if not (agg_hi < lo or hi < agg_lo):
            overlap.append(
                f"{task_set}: CI of {aggregator_id} [{agg_lo:.3f},{agg_hi:.3f}] "
                f"overlaps {pid} [{lo:.3f},{hi:.3f}]"
            )
    return {"passes_b": passes, "aggregator_acc": agg_acc, "ci_overlap": overlap}
