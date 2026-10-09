"""SQLite entry store with brute-force cosine + pure-Python BM25 (AC #1, A4/A5).

Vectors are float32 BLOBs; cosine is brute force (fine at <=100K-token stores,
a few thousand chunks). BM25 uses k1=1.2, b=0.75 with deterministic tie-breaks
by entry id. BM25 postings are maintained incrementally in memory alongside the
sqlite rows; sqlite is the persisted store, the postings are a cache.

If the optional [vec] extra (sqlite-vec) is installed it may be used as a faster
index, but results must match brute force to 1e-6; the core never requires it.
"""

import math
import sqlite3

from ..text import tokenize
from .embedders import cosine, from_blob, to_blob

K1, B = 1.2, 0.75

# Module-level tokenize memo: distractor chunks repeat across thousands of
# cells, so caching by text is a large constant-factor win and stays exact.
_TOKENIZE_MEMO: dict[str, list[str]] = {}


def _tokens(text: str) -> list[str]:
    toks = _TOKENIZE_MEMO.get(text)
    if toks is None:
        toks = tokenize(text)
        if len(_TOKENIZE_MEMO) < 200_000:
            _TOKENIZE_MEMO[text] = toks
    return toks


class EntryStore:
    def __init__(self, path):
        self.path = str(path)
        self._db = sqlite3.connect(self.path)
        # benchmark stores are rebuilt per run; durability is not needed
        self._db.execute("PRAGMA journal_mode=MEMORY")
        self._db.execute("PRAGMA synchronous=OFF")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS entries ("
            " id INTEGER PRIMARY KEY, key TEXT, text TEXT, session INTEGER,"
            " superseded INTEGER DEFAULT 0, vec BLOB)")
        self._db.commit()
        self._vecs: dict[int, dict] = {}       # id -> sparse vec cache
        self._tf: dict[int, dict] = {}         # id -> term frequencies
        self._df: dict[str, int] = {}          # term -> doc frequency
        self._rows: dict[int, dict] = {}       # id -> row cache
        self._postings: dict[int, list] = {}   # dim -> [(entry_id, weight)]
        self._term_ids: dict[str, set] = {}    # term -> entry ids containing it
        # hydrate caches when reopening an existing store
        for r in self._db.execute(
                "SELECT id, key, text, session, superseded, vec FROM entries ORDER BY id"):
            self._rows[r[0]] = {"id": r[0], "key": r[1], "text": r[2],
                                "session": r[3], "superseded": bool(r[4])}
            self._index_terms(r[0], r[2])
            if r[5]:
                self._vecs[r[0]] = from_blob(r[5])
        self._rebuild_postings()

    def close(self):
        self._db.close()

    # -- internal caches --------------------------------------------------------
    def _index_terms(self, entry_id: int, text: str):
        old = self._tf.pop(entry_id, None)
        if old:
            for t in old:
                self._df[t] -= 1
                if not self._df[t]:
                    del self._df[t]
                ids = self._term_ids.get(t)
                if ids:
                    ids.discard(entry_id)
        tf: dict[str, int] = {}
        for t in _tokens(text):
            tf[t] = tf.get(t, 0) + 1
        self._tf[entry_id] = tf
        for t in tf:
            self._df[t] = self._df.get(t, 0) + 1
            self._term_ids.setdefault(t, set()).add(entry_id)

    # -- writes ---------------------------------------------------------------
    def add(self, key: str, text: str, session: int, vec=None, commit=True) -> int:
        cur = self._db.execute(
            "INSERT INTO entries (key, text, session, vec) VALUES (?,?,?,?)",
            (key, text, session, to_blob(vec) if vec else None))
        if commit:
            self._db.commit()
        eid = cur.lastrowid
        if vec:
            self._vecs[eid] = vec
            for dim, w in vec.items():
                self._postings.setdefault(dim, []).append((eid, w))
        self._index_terms(eid, text)
        self._rows[eid] = {"id": eid, "key": key, "text": text, "session": session,
                           "superseded": False}
        return eid

    def add_many(self, rows):
        """rows: iterable of (key, text, session, vec). One transaction."""
        for key, text, session, vec in rows:
            self.add(key, text, session, vec, commit=False)
        self._db.commit()

    def update(self, entry_id: int, text: str, session: int, vec=None):
        self._db.execute(
            "UPDATE entries SET text=?, session=?, vec=? WHERE id=?",
            (text, session, to_blob(vec) if vec else None, entry_id))
        self._db.commit()
        if vec:
            self._vecs[entry_id] = vec
        else:
            self._vecs.pop(entry_id, None)
        self._rebuild_postings()
        self._index_terms(entry_id, text)
        row = self._rows.get(entry_id)
        if row:
            row["text"], row["session"] = text, session

    def mark_superseded(self, entry_id: int):
        self._db.execute("UPDATE entries SET superseded=1 WHERE id=?", (entry_id,))
        self._db.commit()
        if entry_id in self._rows:
            self._rows[entry_id]["superseded"] = True

    def _rebuild_postings(self):
        self._postings = {}
        for eid, vec in self._vecs.items():
            for dim, w in vec.items():
                self._postings.setdefault(dim, []).append((eid, w))

    def delete(self, entry_id: int):
        self._db.execute("DELETE FROM entries WHERE id=?", (entry_id,))
        self._db.commit()
        self._vecs.pop(entry_id, None)
        self._rebuild_postings()
        self._rows.pop(entry_id, None)
        old = self._tf.pop(entry_id, None)
        if old:
            for t in old:
                self._df[t] -= 1
                if not self._df[t]:
                    del self._df[t]

    # -- reads ----------------------------------------------------------------
    def all_entries(self, include_superseded=True):
        rows = [self._rows[i] for i in sorted(self._rows)]
        if not include_superseded:
            rows = [r for r in rows if not r["superseded"]]
        return rows

    def count(self) -> int:
        return len(self._rows)

    def _vec(self, entry_id: int):
        v = self._vecs.get(entry_id)
        if v is None:
            row = self._db.execute("SELECT vec FROM entries WHERE id=?",
                                   (entry_id,)).fetchone()
            if row and row[0]:
                v = from_blob(row[0])
                self._vecs[entry_id] = v
        return v

    def similar(self, query_vec, k=5, include_superseded=True):
        """Cosine top-k via an inverted index over nonzero dims; identical results
        to brute force (dot products accumulate the same terms), ties by id."""
        acc: dict[int, float] = {}
        for dim, qw in query_vec.items():
            for eid, w in self._postings.get(dim, ()):
                acc[eid] = acc.get(eid, 0.0) + qw * w
        scored = []
        for eid, s in acc.items():
            e = self._rows.get(eid)
            if e is None or (not include_superseded and e["superseded"]):
                continue
            scored.append((-s, eid, e))
        # entries with zero overlap score 0 and are only needed when fewer than
        # k entries matched at all
        if len(scored) < k:
            for e in self.all_entries(include_superseded):
                if e["id"] not in acc and self._vec(e["id"]):
                    scored.append((0.0, e["id"], e))
        scored.sort(key=lambda t: (t[0], t[1]))
        return [(-s, e) for s, _, e in scored[:k]]

    def bm25(self, query: str, k=5, include_superseded=True):
        """Pure-Python BM25 (k1=1.2, b=0.75); ties break by entry id ascending.

        Only entries containing >=1 query term can score > 0, so the candidate
        set comes from the term index (identical results to a full scan)."""
        if not self._rows:
            return []
        n = len(self._rows)
        total_len = sum(sum(tf.values()) or 1 for tf in self._tf.values())
        avgdl = total_len / n
        q_terms = _tokens(query)
        candidates = set()
        for t in q_terms:
            candidates |= self._term_ids.get(t, set())
        scored = []
        for eid in candidates:
            e = self._rows.get(eid)
            if e is None or (not include_superseded and e["superseded"]):
                continue
            tf = self._tf[eid]
            dl = sum(tf.values()) or 1
            score = 0.0
            for t in q_terms:
                f = tf.get(t)
                if not f:
                    continue
                df = self._df.get(t, 0)
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                score += idf * f * (K1 + 1) / (f + K1 * (1 - B + B * dl / avgdl))
            if score > 0.0:
                scored.append((-score, eid, e))
        scored.sort(key=lambda t: (t[0], t[1]))
        return [(-s, e) for s, _, e in scored[:k]]
