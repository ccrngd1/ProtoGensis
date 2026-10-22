"""GPQA-Diamond loader.

Source: the official https://github.com/idavidrein/gpqa/raw/main/dataset.zip.
The zip password is published in that repo's README ("Dataset Download"
section); we read it from the downloaded README rather than hard-coding a
secret that isn't ours to re-publish.

Answer choices are shuffled with a fixed per-item seed and the correct letter
recorded; grading is exact letter extraction. Dataset text is NEVER committed
(data/ is gitignored); the manifest keeps item ids + sha256 only.
"""

import csv
import hashlib
import io
import random
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests

GPQA_ZIP_URL = "https://github.com/idavidrein/gpqa/raw/main/dataset.zip"
GPQA_README_URL = "https://raw.githubusercontent.com/idavidrein/gpqa/main/README.md"
LETTERS = ["A", "B", "C", "D"]


@dataclass
class GPQAItem:
    item_id: str
    question: str
    choices: dict          # letter -> text
    correct_letter: str
    subdomain: str
    item_sha256: str

    @property
    def prompt(self) -> str:
        lines = [
            "Answer the following multiple-choice question.",
            "",
            self.question.strip(),
            "",
        ]
        for letter in LETTERS:
            lines.append(f"{letter}) {self.choices[letter]}")
        lines += [
            "",
            'End your response with a line of the form "Answer: X" where X is'
            " one of A, B, C, D.",
        ]
        return "\n".join(lines)


def _read_password_from_readme(readme_text: str) -> str:
    m = re.search(r"password[^`]*`([^`]+)`", readme_text, re.I)
    if not m:
        raise RuntimeError("could not find the zip password in the GPQA README")
    return m.group(1)


def download_gpqa(data_dir) -> Path:
    """Download dataset.zip + README into data_dir; return the extracted csv path."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / "gpqa" / "dataset" / "gpqa_diamond.csv"
    if csv_path.exists():
        return csv_path
    readme = requests.get(GPQA_README_URL, timeout=60).text
    password = _read_password_from_readme(readme)
    blob = requests.get(GPQA_ZIP_URL, timeout=300).content
    z = zipfile.ZipFile(io.BytesIO(blob))
    z.setpassword(password.encode())
    z.extractall(data_dir / "gpqa")
    if not csv_path.exists():
        raise RuntimeError("gpqa_diamond.csv not found after extraction")
    return csv_path


def _item_id(question: str) -> str:
    return "gpqa-" + hashlib.sha256(question.encode()).hexdigest()[:12]


def load_gpqa_diamond(data_dir, shuffle_salt: str = "gpqa-shuffle-v1") -> list:
    """Load the 198 Diamond items with deterministically shuffled choices.

    The per-item RNG is seeded from (salt, question hash) so the letter
    assignment is stable across runs and machines.
    """
    csv_path = download_gpqa(data_dir)
    items = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            question = row["Question"].strip()
            correct = row["Correct Answer"].strip()
            wrong = [
                row["Incorrect Answer 1"].strip(),
                row["Incorrect Answer 2"].strip(),
                row["Incorrect Answer 3"].strip(),
            ]
            iid = _item_id(question)
            rng = random.Random(f"{shuffle_salt}:{iid}")
            order = [correct] + wrong
            rng.shuffle(order)
            choices = dict(zip(LETTERS, order))
            correct_letter = LETTERS[order.index(correct)]
            items.append(GPQAItem(
                item_id=iid,
                question=question,
                choices=choices,
                correct_letter=correct_letter,
                subdomain=row.get("Subdomain", ""),
                item_sha256=hashlib.sha256(question.encode()).hexdigest(),
            ))
    return items
