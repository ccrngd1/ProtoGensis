"""Shared text utilities: tokenization, stopwords, canary shapes.

One home for these so the generator, validator (AC #2d), and MockAgent tool
policy all agree on what a "content keyword" is.
"""

import re

# Standard English function-word list (no domain/content words; AC #2d is checked
# against this exact list and it must not be padded to make probes pass).
STOPWORDS = frozenset("""
a about above after again against all am an and any are aren't as at be because
been before being below between both but by can can't cannot could couldn't did
didn't do does doesn't doing don't down during each few for from further had
hadn't has hasn't have haven't having he he'd he'll he's her here here's hers
herself him himself his how how's i i'd i'll i'm i've if in into is isn't it
it's its itself let's me more most mustn't my myself no nor not of off on once
only or other ought our ours ourselves out over own same shan't she she'd
she'll she's should shouldn't so some such than that that's the their theirs
them themselves then there there's these they they'd they'll they're they've
this those through to too under until up very was wasn't we we'd we'll we're
we've were weren't what what's when when's where where's which while who who's
whom why why's with won't would wouldn't you you'd you'll you're you've your
yours yourself yourselves please give need want use first else even just
""".split())

_WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def content_keywords(text: str) -> set[str]:
    """Lowercase tokens minus stopwords. The AC #2d overlap unit."""
    return {t for t in tokenize(text) if t not in STOPWORDS}


# Canary shapes. Pools are disjoint by construction (schema: port/code/codename/date).
CODENAME_LEFT = ["amber", "cobalt", "velvet", "ivory", "crimson", "slate", "umber",
                 "teal", "onyx", "coral", "sable", "lilac", "russet", "indigo", "ochre"]
CODENAME_RIGHT = ["falcon", "osprey", "heron", "plover", "kestrel", "sandpiper",
                  "curlew", "egret", "bittern", "shrike", "wagtail", "dunlin",
                  "godwit", "petrel", "avocet"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

CANARY_PATTERNS = {
    "port": re.compile(r"\b([1-5][0-9]{4})\b"),
    "code": re.compile(r"\b(XK-[0-9]{4})\b"),
    "codename": re.compile(r"\b((?:%s)-(?:%s))\b" % ("|".join(CODENAME_LEFT), "|".join(CODENAME_RIGHT))),
    "date": re.compile(r"\b([0-3][0-9]-(?:%s))\b" % "|".join(MONTHS)),
}


def find_canaries(text: str, canary_type: str) -> list[str]:
    """All canary-shaped tokens of one type, in order of appearance."""
    return CANARY_PATTERNS[canary_type].findall(text)


def contains_canary(text: str, canary: str) -> bool:
    """Exact, case-sensitive containment with word-ish boundaries."""
    return re.search(r"(?<![\w-])" + re.escape(canary) + r"(?![\w-])", text) is not None
