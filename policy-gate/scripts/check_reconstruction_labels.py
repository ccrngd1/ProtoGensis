#!/usr/bin/env python3
"""Reconstruction-label check (AC #23).

Every paragraph mentioning 2026-02-19 / Feb 19 / February 19 together with
"replay", "transcript", or "incident" must also contain "reconstruct"
(case-insensitive). Exit 0 if all such paragraphs are labeled, else 1.
"""

import re
import sys

DATE = re.compile(r"2026-02-19|feb(ruary)?\.?\s+19", re.I)
CONTEXT = re.compile(r"replay|transcript|incident", re.I)
LABEL = re.compile(r"reconstruct", re.I)
# HTML comment markers (claim/cite IDs like `feb19-ep1-pinned`) are not prose
# and must not trip the date match.
COMMENT = re.compile(r"<!--.*?-->", re.S)


def check(paths):
    problems = []
    for path in paths:
        try:
            text = open(path, encoding="utf-8").read()
        except FileNotFoundError:
            continue
        # split into paragraphs on blank lines; strip HTML comment markers first
        for i, para in enumerate(re.split(r"\n\s*\n", text)):
            para = COMMENT.sub("", para)
            if DATE.search(para) and CONTEXT.search(para) and not LABEL.search(para):
                snippet = " ".join(para.split())[:100]
                problems.append(f"{path}: unlabeled reconstruction paragraph: {snippet}")
    return problems


def main(argv):
    problems = check(argv[1:])
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
