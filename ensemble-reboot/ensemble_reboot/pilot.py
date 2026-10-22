"""Pilot planning and execution.

Stage order puts the most important data first in case the budget cap stops
the run:
  stage0  calibration: all 10 models at DEFAULT effort, the same fixed seeded
          10 items per task set, 1 seed. Picks the best single model B per
          task set, gives preliminary co-failure data and the headroom check.
  stage1  arms at default effort on the same items: A2 (N=5), A3 (7 personas),
          A4a, A4b on B. Stage-0 records are REUSED as A4 proposals and as
          A2's first sample.
  stage2  effort sweep: frontier models at every accepted level (cheap models
          after, if budget remains), skipping levels already covered.

Resume: calls whose (stage, arm, task_set, item_id, model_id, effort, seed)
key already exists in records.jsonl are skipped (their records are reused).
Seed index conventions: A2 samples use seeds 0..N-1 (seed 0 = the stage-0
record); A3 uses seed = persona index (prompt diversity, not sampling).
"""

import json
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from .arms import (
    Proposal,
    build_aggregator_prompt,
    load_personas,
    majority_vote,
    select_code_response,
)
from .budget import BudgetExceeded, BudgetGuard
from .client import BedrockClient, BedrockError, BedrockRetriesExhausted
from .grading_api import grade_code_response, grade_gpqa, grade_math
from .pricing import PricingTable
from .records import Record, RecordStore
from .roster import Roster
from .rules import check_rule4

TASK_SETS = ("gpqa", "math", "code")
SAMPLE_SALT = "pilot-sample-v1"
PILOT_ITEMS_PER_SET = 10
VOTE_MODEL_ID = "programmatic-vote"


def sample_pilot_items(items_by_set: dict, n: int = PILOT_ITEMS_PER_SET) -> dict:
    """Fixed, seeded item sample - the same items for every model."""
    out = {}
    for ts, items in items_by_set.items():
        rng = random.Random(f"{SAMPLE_SALT}:{ts}")
        pool = sorted(items, key=lambda i: i.item_id)
        out[ts] = pool if len(pool) <= n else rng.sample(pool, n)
    return out


def load_accepted_levels(probe_path, roster: Roster) -> dict:
    """model_id -> [levels that returned 200 in the probe]. Falls back to the
    roster candidate list (with a warning flag) when no probe file exists."""
    accepted = defaultdict(list)
    if probe_path and Path(probe_path).exists():
        with open(probe_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                if d.get("status") == 200:
                    accepted[d["model"]].append(d["level"])
        return {m.profile_id: [l for l in m.candidate_levels if l in accepted.get(m.profile_id, [])]
                for m in roster.models}
    return {m.profile_id: list(m.candidate_levels) for m in roster.models}


@dataclass
class PlannedCall:
    stage: str
    arm: str
    task_set: str
    item_id: str
    model_id: str
    effort: str
    seed: int
    kind: str = "proposal"       # proposal | aggregator | vote-event
    persona_id: str | None = None


def plan_stage0(roster: Roster, pilot_items: dict) -> list:
    plan = []
    for m in roster.models:
        for ts in TASK_SETS:
            for item in pilot_items.get(ts, []):
                plan.append(PlannedCall("stage0", "a1", ts, item.item_id,
                                        m.profile_id, m.default_level, 0))
    return plan


def plan_stage1(roster: Roster, pilot_items: dict, best_by_set: dict, a2_n: int = 5) -> list:
    """best_by_set: task_set -> profile_id of the best stage-0 model B."""
    arms_cfg = roster.arms
    panel = arms_cfg.get("a4_panel", [])
    plan = []
    for ts in TASK_SETS:
        b = best_by_set[ts]
        spec = roster.by_id(b)
        for item in pilot_items.get(ts, []):
            # A2: seeds 1..N-1 (seed 0 reuses the stage-0 record)
            for seed in range(1, a2_n):
                plan.append(PlannedCall("stage1", "a2", ts, item.item_id,
                                        b, spec.default_level, seed))
            # A3: 7 personas, seed = persona index
            for pi in range(7):
                plan.append(PlannedCall("stage1", "a3", ts, item.item_id,
                                        b, spec.default_level, pi,
                                        persona_id=f"persona-{pi}"))
            # A4 panel members not covered by stage 0 cost nothing extra
            # (stage-0 records are reused as proposals); aggregator calls:
            plan.append(PlannedCall("stage1", "a4a", ts, item.item_id,
                                    arms_cfg["a4a_aggregator"],
                                    roster.by_id(arms_cfg["a4a_aggregator"]).default_level,
                                    0, kind="aggregator"))
            plan.append(PlannedCall("stage1", "a4b", ts, item.item_id,
                                    arms_cfg["a4b_aggregator"],
                                    roster.by_id(arms_cfg["a4b_aggregator"]).default_level,
                                    0, kind="aggregator"))
    return plan


def plan_stage2(roster: Roster, pilot_items: dict, accepted_levels: dict) -> list:
    """Effort sweep. Frontier models first, then mid/cheap if budget remains.
    Skips each model's default level (covered by stage 0)."""
    ordered = sorted(roster.models, key=lambda m: {"frontier": 0, "mid": 1, "cheap": 2}[m.tier])
    plan = []
    for m in ordered:
        for level in accepted_levels.get(m.profile_id, []):
            if level == m.default_level:
                continue
            for ts in TASK_SETS:
                for item in pilot_items.get(ts, []):
                    plan.append(PlannedCall("stage2", "sweep", ts, item.item_id,
                                            m.profile_id, level, 0))
    return plan


def pick_best_by_set(records: list, task_sets=TASK_SETS) -> dict:
    """Best stage-0 model per task set by accuracy; ties break toward lower
    total conservative cost. Returns task_set -> profile_id."""
    acc = defaultdict(lambda: defaultdict(lambda: [0, 0, 0.0]))  # ts -> model -> [ok, n, cost]
    for r in records:
        if r["stage"] != "stage0" or r.get("correct") is None:
            continue
        cell = acc[r["task_set"]][r["model_id"]]
        cell[0] += 1 if r["correct"] else 0
        cell[1] += 1
        cell[2] += r.get("cost_usd") or 0.0
    best = {}
    for ts in task_sets:
        models = acc.get(ts, {})
        if not models:
            raise ValueError(f"no stage-0 records for task set {ts}; cannot pick best model")
        best[ts] = min(
            models.items(),
            key=lambda kv: (-(kv[1][0] / kv[1][1]), kv[1][2]),
        )[0]
    return best


class PilotRunner:
    """Executes planned calls with budget enforcement, grading, and resume."""

    def __init__(
        self,
        roster: Roster,
        pricing: PricingTable,
        store: RecordStore,
        guard: BudgetGuard,
        client: BedrockClient,
        items_by_set: dict,            # task_set -> [items] (the pilot sample)
        personas_dir=None,
        max_workers: int = 8,
    ):
        self.roster = roster
        self.pricing = pricing
        self.store = store
        self.guard = guard
        self.client = client
        self.items = {ts: {i.item_id: i for i in items}
                      for ts, items in items_by_set.items()}
        self.personas = load_personas(personas_dir) if personas_dir else None
        self.max_workers = max_workers
        self._existing = store.existing_keys()
        self._records_cache = {}
        for r in store.load_all():
            self._records_cache[self._key_of(r)] = r

    @staticmethod
    def _key_of(r: dict):
        return (r["stage"], r["arm"], r["task_set"], r["item_id"],
                r["model_id"], r["effort"], r["seed"])

    def _item(self, task_set: str, item_id: str):
        return self.items[task_set][item_id]

    def _prompt_for(self, call: PlannedCall):
        item = self._item(call.task_set, call.item_id)
        system = None
        if call.persona_id is not None:
            idx = int(call.persona_id.split("-")[1])
            system = self.personas[idx]["system_prompt"]
        return item.prompt, system

    def _grade(self, call: PlannedCall, text: str, truncated: bool):
        item = self._item(call.task_set, call.item_id)
        if call.task_set == "gpqa":
            return grade_gpqa(text, item.correct_letter, truncated)
        if call.task_set == "math":
            return grade_math(text, item.answer, truncated)
        return grade_code_response(text, item, truncated)

    def execute_call(self, call: PlannedCall, prompt: str, system: str | None,
                     parent_ids=()) -> dict:
        """One budgeted API call + grading + record append. Returns the record
        dict (cached one on resume)."""
        key = (call.stage, call.arm, call.task_set, call.item_id,
               call.model_id, call.effort, call.seed)
        if key in self._existing:
            return self._records_cache[key]
        spec = self.roster.by_id(call.model_id)
        item = self._item(call.task_set, call.item_id)
        with self.guard.reserve():
            result = self.client.converse(
                spec, prompt, call.effort,
                max_tokens=self.roster.default_max_tokens,
                system_prompt=system,
            )
            cost = self.pricing.cost(
                call.model_id, result.input_tokens, result.output_tokens,
                result.cache_read_tokens,
            )
            self.guard.settle(cost.cost_usd, cost.conservative_usd)
        grade = self._grade(call, result.text, result.truncated)
        params = dict(result.request_params)
        params.pop("messages", None)  # prompt text lives in raw_text, not records
        if call.persona_id is not None:
            params["persona_id"] = call.persona_id
        rec = Record(
            record_id=Record.new_id(),
            run_id=self.store.run_id,
            stage=call.stage, arm=call.arm, task_set=call.task_set,
            item_id=call.item_id, item_sha256=item.item_sha256, seed=call.seed,
            model_id=call.model_id, family=spec.family, effort=call.effort,
            request_params=params,
            stop_reason=result.stop_reason, usage=result.usage,
            input_tokens=result.input_tokens, output_tokens=result.output_tokens,
            cache_read_tokens=result.cache_read_tokens,
            cost_usd=cost.cost_usd, price_status=cost.price_status,
            latency_s=round(result.latency_s, 3),
            extracted_answer=grade.extracted if isinstance(grade.extracted, str) else None,
            correct=grade.correct, grader_details=grade.details,
            parent_record_ids=list(parent_ids),
            truncated=result.truncated,
            is_mock=False,
        )
        self.store.append(rec, response_text=result.text)
        d = json.loads(json.dumps(rec.__dict__))
        self._existing.add(key)
        self._records_cache[key] = d
        return d

    def append_vote_event(self, call: PlannedCall, winner, details: dict,
                          correct: bool, parent_records: list) -> dict:
        key = (call.stage, call.arm, call.task_set, call.item_id,
               VOTE_MODEL_ID, call.effort, call.seed)
        if key in self._existing:
            return self._records_cache[key]
        item = self._item(call.task_set, call.item_id)
        parent_costs = [r.get("cost_usd") for r in parent_records]
        from .arms import arm_cost_usd
        cost = arm_cost_usd(parent_costs, 0.0)
        rec = Record(
            record_id=Record.new_id(),
            run_id=self.store.run_id,
            stage=call.stage, arm=call.arm, task_set=call.task_set,
            item_id=call.item_id, item_sha256=item.item_sha256, seed=call.seed,
            model_id=VOTE_MODEL_ID, family="n/a", effort=call.effort,
            request_params={"aggregation": details.get("strategy", "majority-vote")},
            stop_reason=None, usage={},
            input_tokens=0, output_tokens=0, cache_read_tokens=0,
            cost_usd=cost,
            price_status="OK" if cost is not None else "UNKNOWN",
            latency_s=0.0,
            extracted_answer=winner if isinstance(winner, str) else None,
            correct=correct, grader_details=details,
            parent_record_ids=[r["record_id"] for r in parent_records],
            is_mock=False,
        )
        self.store.append(rec)
        d = json.loads(json.dumps(rec.__dict__))
        self._existing.add(key)
        self._records_cache[key] = d
        return d

    # ------------------------------------------------------------- stages

    def run_stage0(self, pilot_items: dict, progress=print) -> list:
        plan = plan_stage0(self.roster, pilot_items)
        return self._run_parallel(plan, progress)

    def run_stage1(self, pilot_items: dict, best_by_set: dict, a2_n: int = 5,
                   progress=print) -> list:
        done = []
        arms_cfg = self.roster.arms
        panel_ids = arms_cfg.get("a4_panel", [])
        # rule-4(a) is a hard error; A4b is exempt from (b) by design.
        panel_fams = [(pid, self.roster.by_id(pid).family) for pid in panel_ids]
        check_rule4(arms_cfg["a4a_aggregator"],
                    self.roster.by_id(arms_cfg["a4a_aggregator"]).family,
                    panel_fams)
        check_rule4(arms_cfg["a4b_aggregator"],
                    self.roster.by_id(arms_cfg["a4b_aggregator"]).family,
                    panel_fams, exempt_from_b=True)

        proposal_plan = [c for c in plan_stage1(self.roster, pilot_items, best_by_set, a2_n)
                         if c.kind == "proposal"]
        done += self._run_parallel(proposal_plan, progress)

        # Aggregate per item.
        for ts in TASK_SETS:
            b = best_by_set[ts]
            lvl = self.roster.by_id(b).default_level
            for item in pilot_items.get(ts, []):
                done.append(self._vote_arm("a2", ts, item, b, lvl,
                                           seeds=range(a2_n), progress=progress))
                done.append(self._vote_arm("a3", ts, item, b, lvl,
                                           seeds=range(7), arm_stage_arm="a3",
                                           progress=progress))
                done += self._a4_arms(ts, item, panel_ids, progress)
        return [d for d in done if d]

    def _recs_for(self, stage, arm, ts, item_id, model_id, effort, seeds):
        out = []
        for s in seeds:
            r = self._records_cache.get((stage, arm, ts, item_id, model_id, effort, s))
            if r:
                out.append(r)
        return out

    def _vote_arm(self, arm, ts, item, model_id, level, seeds, progress=print,
                  arm_stage_arm=None):
        """Majority vote (or code selection) over same-model samples.
        For a2, seed 0 comes from stage0/a1."""
        recs = []
        for s in seeds:
            if arm == "a2" and s == 0:
                r = self._records_cache.get(("stage0", "a1", ts, item.item_id,
                                             model_id, level, 0))
            else:
                r = self._records_cache.get(("stage1", arm, ts, item.item_id,
                                             model_id, level, s))
            if r:
                recs.append(r)
        if not recs:
            return None
        proposals = [self._to_proposal(r) for r in recs]
        call = PlannedCall("stage1", arm, ts, item.item_id, VOTE_MODEL_ID, level, 0,
                           kind="vote-event")
        return self._aggregate_and_record(call, item, proposals, recs)

    def _a4_arms(self, ts, item, panel_ids, progress=print):
        out = []
        # Panel proposals REUSE stage-0 records (same item/model/effort/seed 0).
        recs = []
        for pid in panel_ids:
            lvl = self.roster.by_id(pid).default_level
            r = self._records_cache.get(("stage0", "a1", ts, item.item_id, pid, lvl, 0))
            if r:
                recs.append(r)
        if not recs:
            return out
        proposals = [self._to_proposal(r) for r in recs]
        # Post hoc majority vote on the panel: zero extra calls.
        vote_call = PlannedCall("stage1", "a4-vote", ts, item.item_id,
                                VOTE_MODEL_ID, "default", 0, kind="vote-event")
        out.append(self._aggregate_and_record(vote_call, item, proposals, recs))
        # LLM aggregators.
        for arm, agg_key in (("a4a", "a4a_aggregator"), ("a4b", "a4b_aggregator")):
            agg_id = self.roster.arms[agg_key]
            agg_spec = self.roster.by_id(agg_id)
            call = PlannedCall("stage1", arm, ts, item.item_id, agg_id,
                               agg_spec.default_level, 0, kind="aggregator")
            prompt = build_aggregator_prompt(ts, item.prompt, proposals)
            try:
                rec = self.execute_call(call, prompt, None,
                                        parent_ids=[r["record_id"] for r in recs])
                out.append(rec)
            except (BedrockError, BedrockRetriesExhausted) as e:
                progress(f"  a4 aggregator {agg_id} failed on {item.item_id}: {e}")
        return out

    def _to_proposal(self, r: dict) -> Proposal:
        gd = r.get("grader_details") or {}
        return Proposal(
            record_id=r["record_id"],
            model_id=r["model_id"],
            extracted_answer=r.get("extracted_answer"),
            response_text=self._raw_text(r),
            public_pass=gd.get("public_pass"),
            output_signature=gd.get("public_signature", ""),
            correct=r.get("correct"),
        )

    def _raw_text(self, r: dict) -> str:
        p = self.store.raw_text_dir / f"{r['record_id']}.txt"
        return p.read_text() if p.exists() else ""

    def _aggregate_and_record(self, call: PlannedCall, item, proposals, recs):
        if call.task_set == "code":
            sel, details = select_code_response(proposals)
            correct = bool(sel.correct) if sel else False
            winner = sel.record_id if sel else None
            details = {**details, "selected_record": winner}
            return self.append_vote_event(call, winner, details, correct, recs)
        winner, details = majority_vote(proposals)
        if call.task_set == "gpqa":
            correct = winner == item.correct_letter
        else:
            from .extractors import math_answers_equal
            correct = math_answers_equal(winner, item.answer)
        return self.append_vote_event(call, winner, details, correct, recs)

    def run_stage2(self, pilot_items: dict, accepted_levels: dict, progress=print) -> list:
        plan = plan_stage2(self.roster, pilot_items, accepted_levels)
        return self._run_parallel(plan, progress)

    # ------------------------------------------------------------ parallel

    def _run_parallel(self, plan: list, progress=print) -> list:
        done, stop = [], False
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {}
            for call in plan:
                key = (call.stage, call.arm, call.task_set, call.item_id,
                       call.model_id, call.effort, call.seed)
                if key in self._existing:
                    done.append(self._records_cache[key])
                    continue
                prompt, system = self._prompt_for(call)
                futures[pool.submit(self._safe_call, call, prompt, system)] = call
            for fut in as_completed(futures):
                rec, err = fut.result()
                call = futures[fut]
                if rec:
                    done.append(rec)
                elif isinstance(err, BudgetExceeded):
                    if not stop:
                        progress(f"BUDGET CAP: {err}")
                        stop = True
                elif err:
                    progress(f"  call failed ({call.model_id} {call.task_set} "
                             f"{call.item_id} {call.effort}): {err}")
                progress(f"  running total: {self.guard.status()}")
        if stop:
            raise BudgetExceeded(str(self.guard.status()))
        return done

    def _safe_call(self, call, prompt, system):
        try:
            return self.execute_call(call, prompt, system), None
        except BudgetExceeded as e:
            return None, e
        except (BedrockError, BedrockRetriesExhausted) as e:
            return None, e
