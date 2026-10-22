"""LiveCodeBench code_generation_lite slice.

REQUIREMENTS asks for problems dated after 2026-06-01 "or the most recent
window available; record the window". As of 2026-10-22 the newest official
release file (test6.jsonl, release_v6) ends at contest_date 2025-04-06, so the
slice is the most recent window available: contest_date >= WINDOW_START,
hard difficulty preferred. The window actually used is recorded in the
manifest and in every summary.

Public/example tests (usable for best-of-N selection) are kept separate from
private tests (the only ones used for grading).
"""

import base64
import hashlib
import json
import pickle
import zlib
from dataclasses import dataclass, field
from pathlib import Path

LCB_REPO = "livecodebench/code_generation_lite"
LCB_FILE = "test6.jsonl"          # newest official release as of 2026-10-22
WINDOW_START = "2025-02-01"       # most recent ~2-month window of release_v6
REQUESTED_WINDOW_START = "2026-06-01"  # what REQUIREMENTS wanted; not available


@dataclass
class LCBItem:
    item_id: str
    title: str
    question: str
    starter_code: str
    public_tests: list      # [{input, output, testtype}] — selection only
    private_tests: list     # grading only
    difficulty: str
    platform: str
    contest_date: str
    item_sha256: str
    metadata: dict = field(default_factory=dict)

    @property
    def prompt(self) -> str:
        parts = [
            "Solve the following programming problem in Python 3.",
            "",
            self.question.strip(),
            "",
        ]
        if self.starter_code.strip():
            parts += [
                "Use this starter code (complete the function; do not change its signature):",
                "```python",
                self.starter_code.strip(),
                "```",
                "Your solution must define the same class/function so the tests can call it.",
            ]
        else:
            parts += [
                "Read input from stdin and write the answer to stdout.",
            ]
        parts += [
            "",
            "Give the complete final solution in a single ```python code block.",
        ]
        return "\n".join(parts)


def _decode_private(blob: str) -> list:
    """private_test_cases is either plain JSON or base64(zlib(pickle(json)))."""
    try:
        return json.loads(blob)
    except (json.JSONDecodeError, ValueError):
        return json.loads(pickle.loads(zlib.decompress(base64.b64decode(blob))))


def download_lcb(data_dir) -> Path:
    from huggingface_hub import hf_hub_download
    import shutil

    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    dest = data_dir / f"lcb_{LCB_FILE}"
    if not dest.exists():
        src = hf_hub_download(LCB_REPO, LCB_FILE, repo_type="dataset")
        shutil.copy(src, dest)
    return dest


def load_lcb_items(data_dir, difficulties=("hard",), window_start=WINDOW_START) -> list:
    path = download_lcb(data_dir)
    items = []
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if r["contest_date"] < window_start:
                continue
            if difficulties and r["difficulty"] not in difficulties:
                continue
            question = r["question_content"]
            items.append(LCBItem(
                item_id=f"lcb-{r['question_id']}",
                title=r["question_title"],
                question=question,
                starter_code=r.get("starter_code", "") or "",
                public_tests=json.loads(r["public_test_cases"]),
                private_tests=_decode_private(r["private_test_cases"]),
                difficulty=r["difficulty"],
                platform=r["platform"],
                contest_date=r["contest_date"],
                item_sha256=hashlib.sha256(question.encode()).hexdigest(),
                metadata=json.loads(r.get("metadata") or "{}"),
            ))
    items.sort(key=lambda x: (x.contest_date, x.item_id))
    return items


def window_info(items) -> dict:
    return {
        "requested_window_start": REQUESTED_WINDOW_START,
        "actual_window_start": WINDOW_START,
        "release_file": LCB_FILE,
        "n_items": len(items),
        "date_min": min((i.contest_date for i in items), default=None),
        "date_max": max((i.contest_date for i in items), default=None),
        "note": (
            "No post-2026-06-01 problems exist in the newest official "
            "code_generation_lite release (release_v6 ends 2025-04-06); "
            "using the most recent window available, hard difficulty."
        ),
    }
