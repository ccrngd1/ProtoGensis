"""Hard competition math: MathArena AIME 2026 + HMMT Feb 2026 (HF parquet).

Keep only items with a single exact answer (integer or exactly normalizable
fraction). Grading: extract \\boxed{} / "Final answer:" and compare normalized
exact values.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ..extractors import is_single_exact_answer

HF_REPOS = {
    "aime_2026": "MathArena/aime_2026",
    "hmmt_feb_2026": "MathArena/hmmt_feb_2026",
}
PARQUET_FILE = "data/train-00000-of-00001.parquet"


@dataclass
class MathItem:
    item_id: str
    problem: str
    answer: str
    source_set: str
    item_sha256: str

    @property
    def prompt(self) -> str:
        return (
            "Solve the following competition math problem. Show your reasoning,"
            " then give the final answer inside \\boxed{}.\n\n"
            + self.problem.strip()
        )


def download_math(data_dir) -> dict:
    """Download both parquet files into data_dir; return {set_name: path}."""
    from huggingface_hub import hf_hub_download
    import shutil

    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, repo in HF_REPOS.items():
        dest = data_dir / f"{name}.parquet"
        if not dest.exists():
            src = hf_hub_download(repo, PARQUET_FILE, repo_type="dataset")
            shutil.copy(src, dest)
        paths[name] = dest
    return paths


def load_math_items(data_dir) -> list:
    """AIME 2026 + HMMT Feb 2026, filtered to single-exact-answer items."""
    import pyarrow.parquet as pq

    paths = download_math(data_dir)
    items = []
    for name, path in sorted(paths.items()):
        table = pq.read_table(path)
        for row in table.to_pylist():
            answer = str(row["answer"]).strip()
            if not is_single_exact_answer(answer):
                continue
            problem = row["problem"].strip()
            iid = f"{name}-{row['problem_idx']}"
            items.append(MathItem(
                item_id=iid,
                problem=problem,
                answer=answer,
                source_set=name,
                item_sha256=hashlib.sha256(problem.encode()).hexdigest(),
            ))
    return items
