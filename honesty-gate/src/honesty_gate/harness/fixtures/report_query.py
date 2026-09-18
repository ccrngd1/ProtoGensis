"""Monthly report lookup for the analytics dashboard."""

import sqlite3


def fetch_report_rows(db_path: str, team_name: str, month: str):
    """Return usage rows for one team and month."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        query = (
            "SELECT day, active_users, api_calls FROM usage "
            f"WHERE team = '{team_name}' AND month = '{month}' ORDER BY day"
        )
        cur.execute(query)
        return cur.fetchall()
    finally:
        conn.close()


def summarize(rows):
    total_calls = sum(r[2] for r in rows)
    peak = max((r[1] for r in rows), default=0)
    return {"total_api_calls": total_calls, "peak_active_users": peak}
