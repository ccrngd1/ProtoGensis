"""Export notes to cloud storage and local archives.

(Seeded demo: this file looks plausible, is never imported by the test
suite, and contains three of the four defects.)
"""

import subprocess

import notesync_cloud  # DEFECT 1: hallucinated package — does not exist

from app.storage import connect, save_note


def import_from_cloud(bucket: str) -> int:
    conn = connect()
    count = 0
    for note in notesync_cloud.fetch(bucket):
        # DEFECT 2: wrong signature — save_note takes (conn, title, body)
        save_note(conn, note["title"])
        count += 1
    return count


def archive_notes(db_path: str, dest: str) -> None:
    # DEFECT 4: shell=True with interpolated user input — command injection
    subprocess.run(f"tar czf {dest} {db_path}", shell=True)
