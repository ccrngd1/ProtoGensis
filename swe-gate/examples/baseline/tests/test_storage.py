from app.storage import connect, delete_note, get_note, save_note


def test_save_and_get():
    conn = connect()
    note_id = save_note(conn, "groceries", "milk, eggs")
    assert get_note(conn, note_id) == ("groceries", "milk, eggs")


def test_get_missing_returns_none():
    conn = connect()
    assert get_note(conn, 999) is None


def test_delete_note():
    conn = connect()
    note_id = save_note(conn, "temp", "delete me")
    assert delete_note(conn, note_id) is True
    assert get_note(conn, note_id) is None
    assert delete_note(conn, note_id) is False
