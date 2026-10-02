"""Demo outcome tests (AC #8, #9): budget arm results, config seeds, banner,
telecom S/P/A outcomes with the A tie, single-agent tie, 0 false rejections."""
import json

from coherencegate.demos._common import BANNER
from coherencegate.demos.budget import (load_config, main as budget_main, run_arm,
                                        run_demo as run_budget)
from coherencegate.demos.single_agent import run_demo as run_single
from coherencegate.demos.telecom import run_demo as run_telecom
from coherencegate.demos.warmup_lost_update import main as warmup_main, run_demo as run_warmup


def arm_summary(result, arm):
    return next(s for s in result["summary"] if s["arm"] == arm)


class TestBudget:
    def test_pre_registered_outcomes(self):
        """AC #8 per Amendment 1 (.mastercontrol/preregistration.md): ledger and
        escrow 0/5 over; wrong_unit_ledger equals ordinary with OWN001 flagged;
        and visible_state == 0/5 over, the recorded pre-registered value. That
        last assertion is a determinism regression against the recorded
        pre-registered result, NOT a claim that visible state is safe: it held
        only because every scripted agent obeyed a conservative stop rule."""
        result = run_budget()
        assert arm_summary(result, "ledger")["over_budget"] == 0
        assert arm_summary(result, "escrow")["over_budget"] == 0
        # wrong_unit makes the same agent decisions as ordinary, by mechanism
        assert (arm_summary(result, "wrong_unit_ledger")["over_budget"]
                == arm_summary(result, "ordinary")["over_budget"])
        # determinism regression against the recorded pre-registered value
        # (Amendment 1), not a safety claim about visible state
        assert arm_summary(result, "visible_state")["over_budget"] == 0

    def test_visible_state_not_degenerate(self):
        """At least one visible_state role decision across the 5 seeds is made
        against a displayed count x > 0 (the live-budget rule actually sees a
        nonzero budget; the arm is not ordinary-by-construction)."""
        result = run_budget()
        reads = [d for run in result["runs"]["visible_state"] for d in run["reads"]]
        assert any(d["displayed"] > 0 for d in reads)

    def test_visible_state_prompt_shows_run_calls(self):
        """The rendered visible_state context contains the run_calls display
        (value and limit), i.e. x reached the role through ContextAssembler."""
        result = run_budget()
        for run in result["runs"]["visible_state"]:
            for d in run["reads"]:
                assert f"(owned) run_calls used = {d['displayed']}/20" in d["prompt"]

    def test_config_seeds(self):
        assert load_config()["seeds"] == [0, 1, 2, 3, 4]

    def test_banner_in_terminal_output(self):
        text, code = budget_main()
        assert code == 0
        assert BANNER in text
        assert "2610.02036" in text

    def test_own001_flagged(self):
        result = run_budget()
        assert any("OWN001" in msg for msg in result["lint"])

    def test_gate_arms_hold_the_limit(self):
        result = run_budget()
        for arm in ("ledger", "escrow"):
            for run in result["runs"][arm]:
                assert run["total_calls"] <= result["limit"]

    def test_wrong_unit_runs_identical_to_ordinary(self):
        result = run_budget()
        ordinary = [(r["total_calls"], r["over_budget"]) for r in result["runs"]["ordinary"]]
        wrong = [(r["total_calls"], r["over_budget"])
                 for r in result["runs"]["wrong_unit_ledger"]]
        assert ordinary == wrong

    def test_gate_arms_hold_under_lax_policy(self):
        """Mechanism claim (Amendment 1), not an empirical result: the owner
        (ledger or escrow) holds the invariant without any agent stop rule.
        Roles follow the lax rule (spend whenever x < limit, no x + batch
        check) and the gate still never lets the total past the limit — on
        the pre-registered seeds and on a range(50) property sweep. The sweep
        seeds are test-only and must not appear in any reported table."""
        config = load_config()
        for seed in list(config["seeds"]) + list(range(50)):
            for arm in ("ledger", "escrow"):
                run = run_arm(arm, seed, config, policy="lax")
                assert run["total_calls"] <= config["limit"], (arm, seed)
                assert run["over_budget"] is False, (arm, seed)

    def test_exploratory_arm_separate_and_labeled(self):
        """The exploratory visible_state_lax arm (Amendment 1) stays out of
        the pre-registered `summary` and `runs`, and its 'exploratory, added
        after the pre-registered result' label appears in the terminal and
        md output."""
        result = run_budget()
        assert all(s["arm"] != "visible_state_lax" for s in result["summary"])
        assert "visible_state_lax" not in result["runs"]
        exp = result["exploratory"]
        assert exp["label"] == "exploratory, added after the pre-registered result"
        assert [s["arm"] for s in exp["summary"]] == ["visible_state_lax"]
        for fmt in ("terminal", "md"):
            text, code = budget_main(fmt=fmt)
            assert code == 0
            assert "exploratory, added after the pre-registered result" in text
            assert "visible_state_lax" in text


class TestTelecom:
    def test_stale_quote_outcomes(self):
        result = run_telecom()
        by = {(r["task"], r["arm"]): r for r in result["results"]}
        # conventional commits the stale price; coherence repairs -> 140
        assert by[("S", "conventional")]["committed_stale"] is True
        assert by[("S", "conventional")]["conventional_precondition_passed"] is True
        assert by[("S", "coherence")]["final_unit_price"] == 140
        assert by[("S", "coherence")]["repaired"] is True

    def test_silent_revert_outcomes(self):
        result = run_telecom()
        by = {(r["task"], r["arm"]): r for r in result["results"]}
        assert by[("P", "coherence")]["postcondition_holds"] is True
        assert by[("P", "coherence")]["notices"] == 1
        assert by[("P", "conventional")]["postcondition_holds"] is False
        assert by[("P", "unguarded")]["postcondition_holds"] is False

    def test_authority_tie(self):
        result = run_telecom()
        assert result["authority_tie"] is True
        by = {(r["task"], r["arm"]): r for r in result["results"]}
        assert by[("A", "conventional")]["blocked"] == by[("A", "coherence")]["blocked"] is True
        assert by[("A", "unguarded")]["blocked"] is False

    def test_zero_false_rejections(self):
        assert run_telecom()["false_rejections"] == 0

    def test_tie_labeled_in_output(self):
        from coherencegate.demos.telecom import main
        text, _ = main()
        assert "TIE" in text or "tie" in text


class TestSingleAgent:
    def test_tie(self):
        result = run_single()
        assert result["tie"] is True
        gated = next(a for a in result["arms"] if a["arm"] == "gated")
        assert gated["rejections"] == 0 and gated["notices"] == 0

    def test_tie_labeled_in_output(self):
        from coherencegate.demos.single_agent import main
        text, _ = main()
        assert "TIE" in text or "tie" in text


class TestWarmup:
    def test_lost_update_caught_only_when_gated(self):
        result = run_warmup()
        by = {a["arm"]: a for a in result["arms"]}
        assert by["ungated"]["lost_update"] is True
        assert by["gated"]["repaired"] is True
        assert by["gated"]["final"] == "on"  # B's write survives

    def test_credits_agent_coherence(self):
        text, _ = warmup_main()
        assert "agent-coherence` already prevents this. Shown for completeness." in text


class TestDemoHeaders:
    def test_every_demo_prints_citation_and_banner(self):
        from coherencegate.demos import (budget, identifiability, single_agent,
                                         telecom, warmup_lost_update)
        for mod in (budget, identifiability, telecom, single_agent, warmup_lost_update):
            text, _ = mod.main()
            assert "2610.02036" in text
            assert BANNER in text

    def test_json_outputs_parse_and_sorted(self):
        from coherencegate.demos import budget
        text, _ = budget.main(fmt="json")
        payload = json.loads(text)
        assert list(payload) == sorted(payload)
