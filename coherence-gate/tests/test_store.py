"""Store tests: version bump, atomic apply, threaded Ledger stress,
SQLite durability across reopen (AC #1)."""
import threading

from coherencegate.gate import Accept, CommitGate
from coherencegate.owners import Ledger, Unit
from coherencegate.proposal import Proposal
from coherencegate.store import SQLiteStore, Versioned


def test_missing_key_is_version_zero(store_factory):
    s = store_factory()
    assert s.get("nope") == Versioned(None, 0)


def test_every_write_bumps_version(store_factory):
    s = store_factory({"x": 1})
    assert s.get("x") == Versioned(1, 1)
    s.apply_atomic({}, {"x": 2})
    assert s.get("x") == Versioned(2, 2)
    s.out_of_band("x", 3)
    assert s.get("x") == Versioned(3, 3)


def test_apply_atomic_rejects_stale_expected(store_factory):
    s = store_factory({"x": 1})
    s.out_of_band("x", 5)  # now v2
    result = s.apply_atomic({"x": 1}, {"y": "w"})
    assert not result.ok
    assert result.stale == {"x": Versioned(5, 2)}
    assert s.get("y") == Versioned(None, 0)  # nothing applied


def test_apply_atomic_all_or_nothing(store_factory):
    s = store_factory({"a": 1, "b": 1})
    s.out_of_band("b", 9)  # b stale now
    result = s.apply_atomic({"a": 1, "b": 1}, {"a": 2, "b": 2})
    assert not result.ok
    assert s.get("a") == Versioned(1, 1)  # a untouched


def test_snapshot_consistent_cut(store_factory):
    s = store_factory({"a": 1, "b": 2})
    snap = s.snapshot(["a", "b", "missing"])
    assert snap == {"a": Versioned(1, 1), "b": Versioned(2, 1),
                    "missing": Versioned(None, 0)}


def test_draws_tracked_separately_from_versions(store_factory):
    s = store_factory({"x": 1})
    s.apply_atomic({}, {}, draws={"run_calls": 3}, role="executor")
    s.apply_atomic({}, {}, draws={"run_calls": 2}, role="planner")
    assert s.draw_total("run_calls") == 5
    assert s.draw_total_by_role("run_calls", "executor") == 3
    assert s.get("x").version == 1  # draws never bump key versions


def test_subscribe_sees_applied_changes(store_factory):
    s = store_factory()
    events = []
    s.subscribe(events.append)
    s.apply_atomic({}, {"k": 1})
    s.out_of_band("k", 2)
    kinds = [e["kind"] for e in events]
    assert kinds == ["write", "env_change"]
    assert events[1]["source"] == "environment"


def test_sqlite_durability_across_reopen(tmp_path):
    path = str(tmp_path / "durable.db")
    s1 = SQLiteStore(path, {"x": "hello"})
    s1.apply_atomic({}, {"x": "world"})
    s1.apply_atomic({}, {}, draws={"run_calls": 4}, role="executor")
    s1.close()
    s2 = SQLiteStore(path)
    assert s2.get("x") == Versioned("world", 2)
    assert s2.draw_total_by_role("run_calls", "executor") == 4
    s2.close()


def test_threaded_ledger_stress_never_exceeds_limit(store_factory):
    """>=8 threads, >=500 draws against Ledger(limit=N): never used > N (AC #1)."""
    limit = 50
    s = store_factory()
    gate = CommitGate(s, invariants=[Ledger("r", limit, Unit("tool_call", "run"))])
    accepted = []
    lock = threading.Lock()

    def worker(role):
        for _ in range(70):  # 8 threads x 70 = 560 draws
            p = Proposal(agent=role, role=role, draws={"r": 1})
            out = gate.commit(p)
            if isinstance(out, Accept):
                with lock:
                    accepted.append(1)

    threads = [threading.Thread(target=worker, args=(f"t{i}",)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert s.draw_total("r") <= limit
    assert s.draw_total("r") == len(accepted) == limit
