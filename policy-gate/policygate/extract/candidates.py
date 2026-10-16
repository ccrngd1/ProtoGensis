"""Builder and cached candidate loaders (AC #6).

Builder-authored candidate files are tagged origin: "builder". Cached
extraction files are tagged origin: "llm:<model-id>" and carry N runs each,
aggregated by vote.py. Each clause is classified gateable | temporal |
ordering | counting | obligation | text-only | ambiguous (the class is part of
the candidate file in v1).
"""

from .. import rules

CLASSES = {"gateable", "temporal", "ordering", "counting", "obligation",
           "text-only", "ambiguous"}


def load(path):
    """Load candidate dicts from a file or directory."""
    return rules.load_candidates(path)


def origin_of(cands):
    origins = {c.get("origin", "builder") for c in cands}
    if origins == {"builder"} or not origins:
        return "builder"
    if len(origins) == 1:
        return next(iter(origins))
    return "mixed"
