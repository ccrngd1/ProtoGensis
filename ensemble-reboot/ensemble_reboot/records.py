"""Append-only raw record store.

One JSONL line per API call or grading event, under results/<run_id>/records.jsonl.
Full response text goes to results/raw_text/<record_id>.txt (gitignored).
Reporting code refuses any record with is_mock=true.
"""

import hashlib
import json
import subprocess
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


class MockRecordError(ValueError):
    """Raised when reporting code encounters an is_mock record."""


# Synthetic records written for programmatic aggregation events (majority
# vote etc.). Their cost_usd is ATTRIBUTED arm cost (the sum of their parent
# proposal calls), not billed API spend.
VOTE_MODEL_ID = "programmatic-vote"


def is_billed(r) -> bool:
    """True iff the record came from a real API call (its cost is billed
    spend). Prefers the explicit `billed` field; records written before the
    field existed fall back to model_id != VOTE_MODEL_ID."""
    get = r.get if isinstance(r, dict) else lambda k, d=None: getattr(r, k, d)
    billed = get("billed")
    if billed is not None:
        return bool(billed)
    return get("model_id") != VOTE_MODEL_ID


def billed_spend(records) -> float:
    """Total billed spend over records: sum of cost_usd for billed records
    only. Vote events attribute their parents' cost; adding them on top of
    their parents double-counts, so they are excluded here."""
    get = lambda r, k: (r.get(k) if isinstance(r, dict) else getattr(r, k, None))
    return sum(get(r, "cost_usd") or 0.0 for r in records if is_billed(r))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def harness_commit(repo_dir=None) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir or Path(__file__).resolve().parent.parent,
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


@dataclass
class Record:
    record_id: str
    run_id: str
    stage: str
    arm: str
    task_set: str
    item_id: str
    item_sha256: str
    seed: int
    model_id: str
    family: str
    effort: str
    request_params: dict           # body sans token (never contains Authorization)
    stop_reason: str | None
    usage: dict
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cost_usd: float | None
    price_status: str
    latency_s: float
    extracted_answer: str | None
    correct: bool | None
    grader_details: dict = field(default_factory=dict)
    parent_record_ids: list = field(default_factory=list)
    response_sha256: str = ""
    truncated: bool = False
    timestamp: str = ""
    git_commit: str = ""
    is_mock: bool = False
    # billed=False marks synthetic records (vote events) whose cost_usd is
    # attributed arm cost, not API spend; attributed_cost_usd mirrors it there.
    billed: bool = True
    attributed_cost_usd: float | None = None

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex[:16]


class RecordStore:
    """Append-only writer/reader for a run's records.jsonl plus raw text files."""

    def __init__(self, results_dir, run_id: str):
        self.results_dir = Path(results_dir)
        self.run_id = run_id
        self.run_dir = self.results_dir / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.records_path = self.run_dir / "records.jsonl"
        self.raw_text_dir = self.results_dir / "raw_text"
        self.raw_text_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._commit = harness_commit()

    def append(self, record: Record, response_text: str = "") -> Record:
        if not record.timestamp:
            record.timestamp = datetime.now(timezone.utc).isoformat()
        if not record.git_commit:
            record.git_commit = self._commit
        if response_text:
            record.response_sha256 = sha256_text(response_text)
            (self.raw_text_dir / f"{record.record_id}.txt").write_text(response_text)
        # Defense in depth: a bearer token must never land in a record.
        blob = json.dumps(asdict(record))
        if "Authorization" in blob or "Bearer " in blob:
            raise ValueError("record appears to contain an auth header; refusing to write")
        with self._lock:
            with open(self.records_path, "a") as f:
                f.write(blob + "\n")
        return record

    def load_all(self, allow_mock: bool = False) -> list:
        """Load records for reporting. REFUSES is_mock records unless the
        caller is a test explicitly passing allow_mock=True."""
        records = []
        if not self.records_path.exists():
            return records
        with open(self.records_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                if d.get("is_mock") and not allow_mock:
                    raise MockRecordError(
                        f"record {d.get('record_id')} has is_mock=true; "
                        "reporting on mock records is forbidden"
                    )
                records.append(d)
        return records

    def existing_keys(self) -> set:
        """Keys of already-recorded calls, for resume: (stage, arm, task_set,
        item_id, model_id, effort, seed)."""
        keys = set()
        if not self.records_path.exists():
            return keys
        with open(self.records_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                keys.add((
                    d["stage"], d["arm"], d["task_set"], d["item_id"],
                    d["model_id"], d["effort"], d["seed"],
                ))
        return keys
