"""Run log + report tests (AC #11): the report is computed from the log only,
step clock is deterministic, JSON output has stable key order."""
import json

from coherencegate.context import ContextAssembler
from coherencegate.gate import CommitGate
from coherencegate.monitor import EffectMonitor
from coherencegate.owners import Ledger, Unit
from coherencegate.proposal import Proposal
from coherencegate.report import render, summarize
from coherencegate.runlog import RunLog, StepClock


def build_run(store):
    log = RunLog(clock=StepClock(), run_id="r", arm="test", seed=0)
    monitor = EffectMonitor(store)
    gate = CommitGate(store, invariants=[Ledger("run_calls", 3, Unit("tool_call", "run"))],
                      runlog=log, monitor=monitor)
    asm = ContextAssembler(store)
    ctx = asm.for_agent("a", "r1")
    ctx.show("flag")
    gate.commit(Proposal("a", "r1", writes={"flag": True}, read_set=ctx.read_set,
                         draws={"run_calls": 2}, postconditions={"flag": True}))
    gate.commit(Proposal("b", "r2", draws={"run_calls": 2}))  # invariant reject
    store.out_of_band("flag", False)  # silent revert (subscription fires check())
    monitor.check()
    for notice in monitor.pending_for("a"):
        log.emit("notice", agent=notice.agent, key=notice.key, acted_on=False)
    return log


def test_report_computed_from_log_only(store_factory, tmp_path):
    log = build_run(store_factory({"flag": False}))
    direct = summarize(log.events)
    path = str(tmp_path / "run.jsonl")
    log.dump(path)
    reloaded = summarize(RunLog.load(path))
    assert direct == reloaded
    assert direct["counts"]["accepts"] == 1
    assert direct["counts"]["rejects"] == 1
    assert direct["rejects_by_reason"] == {"invariant": 1}
    assert direct["violations_prevented"] == 1
    assert direct["counts"]["notices"] == 1
    assert direct["draw_totals"] == {"run_calls": 2}
    assert direct["reads_by_key_version"] == {"flag@v1": 1}


def test_step_clock_no_wall_time(store_factory):
    log = build_run(store_factory({"flag": False}))
    ts = [ev["t"] for ev in log.events]
    assert ts == list(range(len(ts)))  # pure step clock, no timestamps


def test_json_render_stable_key_order(store_factory):
    log = build_run(store_factory({"flag": False}))
    report = summarize(log.events)
    j1 = render(report, "json")
    j2 = render(summarize(log.events), "json")
    assert j1 == j2
    parsed = json.loads(j1)
    assert list(parsed) == sorted(parsed)


def test_unseen_premise_flagged_in_report(store_factory):
    """AC #2: cited keys that weren't shown are ignored for validation and
    flagged unseen_premise in the report."""
    s = store_factory({"price": 100})
    log = RunLog(clock=StepClock())
    gate = CommitGate(s, runlog=log)
    asm = ContextAssembler(s)
    ctx = asm.for_agent("a", "r")
    ctx.show("price")
    s.out_of_band("ghost_key", 1)  # exists but was never shown
    out = gate.commit(Proposal("a", "r", writes={"memo": "x"}, read_set=ctx.read_set,
                               premises=["price", "ghost_key"]))
    from coherencegate.gate import Accept
    assert isinstance(out, Accept)  # ghost_key ignored for validation
    report = summarize(log.events)
    assert report["unseen_premises"] == ["ghost_key"]


def test_markdown_and_terminal_render(store_factory):
    report = summarize(build_run(store_factory({"flag": False})).events)
    md = render(report, "md")
    assert "| metric | value |" in md
    assert "Violations prevented" in md
    term = render(report, "terminal")
    assert "violations_prevented 1" in term
