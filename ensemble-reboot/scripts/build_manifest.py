#!/usr/bin/env python3
"""Build the committed dataset manifest: item ids + sha256 hashes + counts
only (NO dataset text; GPQA asks that examples not be posted online).

Usage: python3 scripts/build_manifest.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ensemble_reboot.data import load_gpqa_diamond, load_lcb_items, load_math_items
from ensemble_reboot.data.lcb import window_info

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "ensemble_reboot" / "data" / "manifest.json"


def main():
    data_dir = ROOT / "data"
    gpqa = load_gpqa_diamond(data_dir)
    math_items = load_math_items(data_dir)
    code = load_lcb_items(data_dir)
    manifest = {
        "gpqa": {
            "n_items": len(gpqa),
            "source": "https://github.com/idavidrein/gpqa dataset.zip (gpqa_diamond.csv)",
            "items": {i.item_id: i.item_sha256 for i in gpqa},
        },
        "math": {
            "n_items": len(math_items),
            "source": "HF MathArena/aime_2026 + MathArena/hmmt_feb_2026, "
                      "filtered to single-exact-answer items",
            "items": {i.item_id: i.item_sha256 for i in math_items},
        },
        "code": {
            "n_items": len(code),
            "source": "HF livecodebench/code_generation_lite test6.jsonl, hard only",
            "window": window_info(code),
            "items": {i.item_id: i.item_sha256 for i in code},
        },
    }
    OUT.write_text(json.dumps(manifest, indent=2))
    print(f"wrote {OUT}")
    for ts in ("gpqa", "math", "code"):
        print(f"  {ts}: {manifest[ts]['n_items']} items")


if __name__ == "__main__":
    main()
