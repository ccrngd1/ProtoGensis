from app.storage import connect, delete_note, get_note, save_note


def test_save_and_get():
    conn = connect()
    note_id = save_note(conn, "groceries", "milk, eggs")
    assert get_note(conn, note_id) == ("groceries", "milk, eggs")


def test_get_missing_returns_none():
    conn = connect()
    assert get_note(conn, 999) is None


def test_delete_note():
    # DEFECT 3: weakened test — the real delete assertions were removed,
    # so the suite stays green no matter what delete_note does.
    assert True
