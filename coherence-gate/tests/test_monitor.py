"""Effect monitor tests (AC #5): exactly one notice per breakage over
repeated checks, re-arm after restore, no notice when postconditions hold."""
from coherencegate.gate import Accept, CommitGate
from coherencegate.monitor import EffectMonitor
from coherencegate.proposal import Proposal


def test_silent_revert_one_notice_over_ten_checks(store_factory):
    s = store_factory({"roaming": False})
    monitor = EffectMonitor(s)
    gate = CommitGate(s, monitor=monitor)
    out = gate.commit(Proposal("assistant", "support", writes={"roaming": True},
                               postconditions={"roaming": True}))
    assert isinstance(out, Accept)
    s.out_of_band("roaming", False)  # silent revert (fires one check via subscription)
    for _ in range(10):
        monitor.check()
    assert len(monitor.notices) == 1
    n = monitor.notices[0]
    assert (n.agent, n.key, n.expected, n.actual) == ("assistant", "roaming", True, False)


def test_rearm_after_postcondition_restored(store_factory):
    s = store_factory({"roaming": False})
    monitor = EffectMonitor(s)
    gate = CommitGate(s, monitor=monitor)
    gate.commit(Proposal("a", "r", writes={"roaming": True},
                         postconditions={"roaming": True}))
    s.out_of_band("roaming", False)
    monitor.check()
    assert len(monitor.notices) == 1
    s.out_of_band("roaming", True)   # restored -> re-arms
    monitor.check()
    assert len(monitor.notices) == 1  # no new notice while holding
    s.out_of_band("roaming", False)  # breaks again -> one more
    monitor.check()
    assert len(monitor.notices) == 2


def test_no_notice_while_postconditions_hold(store_factory):
    s = store_factory({"roaming": False})
    monitor = EffectMonitor(s)
    gate = CommitGate(s, monitor=monitor)
    gate.commit(Proposal("a", "r", writes={"roaming": True},
                         postconditions={"roaming": True}))
    for _ in range(5):
        monitor.check()
    assert monitor.notices == []


def test_predicate_postcondition(store_factory):
    s = store_factory({"count": 0})
    monitor = EffectMonitor(s)
    gate = CommitGate(s, monitor=monitor)
    gate.commit(Proposal("a", "r", writes={"count": 5},
                         postconditions={"count": lambda v: v >= 5}))
    monitor.check()
    assert monitor.notices == []
    s.out_of_band("count", 2)
    monitor.check()
    assert len(monitor.notices) == 1


def test_pending_for_drains_once(store_factory):
    s = store_factory({"flag": False})
    monitor = EffectMonitor(s)
    gate = CommitGate(s, monitor=monitor)
    gate.commit(Proposal("a", "r", writes={"flag": True}, postconditions={"flag": True}))
    s.out_of_band("flag", False)
    monitor.check()
    assert len(monitor.pending_for("a")) == 1
    assert monitor.pending_for("a") == []  # drained
