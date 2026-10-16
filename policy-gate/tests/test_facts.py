"""Fact store tests: consumption on/off per profile (AC #12)."""

from policygate import facts as facts_mod


def test_consumption_pinned():
    store = facts_mod.FactStore("pinned")
    # a CC turn naming the gateway authorizes a restart under all readings
    store.observe_turn("cc_direct", "heuristic", "restart the gateway now", "")
    first = store.authorization_for("gateway.restart")
    assert first["strict"] is True
    store.consume_authorization("gateway.restart", first)
    # a second write without a fresh CC turn is no longer authorized (consumed)
    second = store.authorization_for("gateway.restart")
    assert second["strict"] is False


def test_no_consumption_spike_parity():
    store = facts_mod.FactStore("spike-parity")
    store.observe_turn("cc_direct", "heuristic", "restart the gateway now", "")
    first = store.authorization_for("gateway.restart")
    store.consume_authorization("gateway.restart", first)
    second = store.authorization_for("gateway.restart")
    assert second["strict"] is True


def test_non_cc_turn_clears_authorization():
    store = facts_mod.FactStore("pinned")
    store.observe_turn("cc_direct", "heuristic", "restart the gateway now", "")
    store.observe_turn("cron", "heuristic", None, "")
    out = store.authorization_for("gateway.restart")
    assert out["strict"] is False


def test_fresh_cc_turn_reauthorizes():
    store = facts_mod.FactStore("pinned")
    store.observe_turn("cc_direct", "heuristic", "restart the gateway now", "")
    first = store.authorization_for("gateway.restart")
    store.consume_authorization("gateway.restart", first)
    store.observe_turn("cc_direct", "heuristic", "restart the gateway again", "")
    out = store.authorization_for("gateway.restart")
    assert out["strict"] is True
