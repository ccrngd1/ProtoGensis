"""AC #5: costmodel reproduces research §5.2 to the cent; break-evens exact."""

from memdoc import costmodel


def _cents(x):
    return round(x, 2)


def test_medium_session_table_to_the_cent():
    # research §5.2, medium session (30 calls, 5 turns), 10K store
    assert _cents(costmodel.doc_full(10000, 30, 5)) == 0.13
    assert _cents(costmodel.doc_full(10000, 30, 5, cache=False)) == 0.91
    assert _cents(costmodel.doc_catalog(10000, 30, 5)) == 0.05
    assert _cents(costmodel.rag_tail(10000, 30, 5)) == 0.08
    assert _cents(costmodel.rag_head(10000, 30, 5)) == 0.39


def test_more_52_values_to_the_cent():
    # 25K and 100K rows of the medium table
    assert _cents(costmodel.doc_full(25000, 30, 5)) == 0.32
    assert _cents(costmodel.doc_full(25000, 30, 5, cache=False)) == 2.26
    assert _cents(costmodel.doc_full(100000, 30, 5)) == 1.25
    assert _cents(costmodel.doc_full(100000, 30, 5, cache=False)) == 9.01
    assert _cents(costmodel.rag_tail(25000, 30, 5, extract=False)) == 0.03


def test_long_session_head_inject():
    assert _cents(costmodel.rag_head(10000, 150, 15)) == 5.87
    assert _cents(costmodel.rag_tail(10000, 150, 15)) == 0.44


def test_breakevens():
    assert costmodel.breakeven() == {"short": 4000, "medium": 6000, "long": 9000}


def test_tables_shape():
    t = costmodel.tables()
    assert set(t) == {"short", "medium", "long"}
    for sess in t.values():
        assert set(sess) == {"2000", "10000", "25000", "50000", "100000"}
        for row in sess.values():
            assert set(row) == {c for c, _ in costmodel.COLUMNS}


def test_no_tiktoken_anywhere():
    import pathlib
    root = pathlib.Path(costmodel.__file__).resolve().parent
    for p in root.rglob("*.py"):
        assert "tiktoken" not in p.read_text(encoding="utf-8").lower(), p
    pyproject = root.parent / "pyproject.toml"
    assert "tiktoken" not in pyproject.read_text(encoding="utf-8").lower()
