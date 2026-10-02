"""Context assembler tests (AC #2): read set == rendered [key@vN] tags,
display-only owned resources, premise narrowing, byte-stable render."""
from coherencegate.context import ContextAssembler, tags_in
from coherencegate.proposal import Proposal


def test_read_set_equals_rendered_tags(store_factory):
    s = store_factory({"price": 100, "order": None, "flag": True})
    ctx = ContextAssembler(s).for_agent("a1", "cost")
    ctx.show("price")
    ctx.show("flag")
    text = ctx.render()
    assert tags_in(text) == ctx.read_set == {"price": 1, "flag": 1}


def test_displayed_owned_not_in_read_set(store_factory):
    s = store_factory()
    s.apply_atomic({}, {}, draws={"run_calls": 7}, role="executor")
    ctx = ContextAssembler(s).for_agent("a1", "planner")
    used = ctx.show_owned("run_calls", limit=20)
    assert used == 7
    text = ctx.render()
    assert ctx.read_set == {}
    assert tags_in(text) == {}
    assert ctx.displayed_owned == {"run_calls": 7}
    assert "run_calls used = 7/20" in text


def test_render_is_byte_stable(store_factory):
    s = store_factory({"b": 2, "a": 1})

    def build():
        ctx = ContextAssembler(s).for_agent("a1", "r")
        ctx.show("a")
        ctx.show("b")
        return ctx.render()

    assert build() == build()
    assert build().encode() == build().encode()


def test_context_frozen_after_render(store_factory):
    s = store_factory({"a": 1})
    ctx = ContextAssembler(s).for_agent("a1", "r")
    ctx.show("a")
    ctx.render()
    import pytest
    with pytest.raises(RuntimeError):
        ctx.show("a")


def test_premises_narrow_never_widen(store_factory):
    s = store_factory({"price": 100, "memo": "x"})
    ctx = ContextAssembler(s).for_agent("a1", "cost")
    ctx.show("price")
    ctx.show("memo")
    p = Proposal(agent="a1", role="cost", writes={}, read_set=ctx.read_set,
                 premises=["price", "ghost_key"])
    # narrowed to shown ∩ cited
    assert p.validated_read_set() == {"price": 1}
    # cited-but-unseen is flagged and ignored for validation
    assert p.unseen_premises() == ["ghost_key"]


def test_no_premises_means_full_read_set(store_factory):
    s = store_factory({"a": 1})
    ctx = ContextAssembler(s).for_agent("a1", "r")
    ctx.show("a")
    p = Proposal(agent="a1", role="r", writes={}, read_set=ctx.read_set)
    assert p.validated_read_set() == {"a": 1}
    assert p.unseen_premises() == []
