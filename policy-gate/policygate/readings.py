"""strict / plan / lenient authorization readings (AC #13). DETERMINISTIC.

Ports spike 1's authorized() with AFFIRM and VERB_FOR from config/readings.toml.
Every verdict carries all three readings side by side; there is no single
combined number.
"""

import hashlib
import os
import re
import tomllib

_CONFIG = os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir, "config", "readings.toml"))
READINGS = ["strict", "plan", "lenient"]


class Readings:
    def __init__(self, path=None):
        self.path = path or _CONFIG
        with open(self.path, "rb") as f:
            raw = f.read()
        cfg = tomllib.loads(raw.decode("utf-8"))
        self.sha256 = hashlib.sha256(raw).hexdigest()
        self.affirm = re.compile(cfg["affirm"], re.I)
        self.verb_for = {k: re.compile(v, re.I) for k, v in cfg["verb_for"].items()}

    def authorized(self, reading, vtool, cc_text, prev_assistant):
        """cc_authorized predicate under one reading (spike 1 port)."""
        if cc_text is None:
            return False
        fam = vtool.split(".")[0]
        pat = self.verb_for.get(fam)
        names_it = bool(pat and pat.search(cc_text))
        if reading == "strict":
            return names_it
        if reading == "plan":
            return names_it or (bool(self.affirm.match(cc_text))
                                and bool(pat and pat.search(prev_assistant or "")))
        if reading == "lenient":
            return True
        raise ValueError(reading)

    def all_readings(self, vtool, cc_text, prev_assistant):
        return {r: self.authorized(r, vtool, cc_text, prev_assistant) for r in READINGS}


_default = None


def default():
    global _default
    if _default is None:
        _default = Readings()
    return _default
