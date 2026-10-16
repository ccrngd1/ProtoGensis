"""scan-artifacts: secret / PII / transcript-leak scan over committed artifacts (AC #21).

Scans every file from `git ls-files` plus untracked files not ignored, using
the vendored AEGIS scanners plus the extra patterns below. Exceptions only via
docs/SCAN_ALLOWLIST.toml (file, pattern, justification); secret-class hits
cannot be allowlisted. --against-archive hashes 8-token shingles of user-turn
text and exec command strings in the legacy archive (in memory only) and fails
on any committed line containing a matching shingle.

Known-real IDs (P1-P3 of the main review): two extra non-allowlistable
checks run over every scanned file, tests/ and scripts/ included, on the line
as written AND on a "joined" view with string-concatenation seams removed
(`"ab" + "cd"`, `"ab""cd"`, `'ab' 'cd'`), so an ID split across literals to
dodge a grep is still caught:

- `banned_id`: the sha256 of a UUID- or Slack-ID-shaped token is in
  BANNED_ID_SHA256 (real cron job IDs / channel ID; only hashes are committed,
  so the scanner itself holds no real ID). Callers may pass extra hashes.
- `real_prefix_fragment`: an `<8hex>-<4hex>` fragment whose 8-hex prefix is a
  redacted-fixture prefix (a synthetic-form UUID `<8hex>-0000-4000-8000-...`
  found anywhere in the scanned tree, i.e. a real prefix kept per AC #16) but
  whose next group is not `0000` - the real suffix leaking back in.
"""

import hashlib
import os
import re
import subprocess
import tomllib

from .vendor.aegis_scanners import SecretScanner, PIIDetector

SECRET_SCANNER = SecretScanner(check_entropy=False)
PII = PIIDetector(sensitivity="high")

SLACK_ID = re.compile(r"\b[CDGUW][A-Z0-9]{8,11}\b")
SYNTH_UUID = re.compile(r"^[0-9a-f]{8}-0000-4000-8000-[0-9a-f]{12}$")
ANY_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
RFC1918 = re.compile(r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b")
XOX = re.compile(r"xox[abposr]-")
AKIA = re.compile(r"AKIA[0-9A-Z]{16}")
# token assignment: a credential keyword followed by a separator and a
# credential-like value. The value is constrained to credential characters so
# the rule does not self-match source that merely *names* the keywords (e.g. a
# regex literal); see docs/DESIGN_NOTES.md "Ambiguities".
TOKEN_ASSIGN = re.compile(r"(token|key|secret|password|bearer)[=:]\s*[A-Za-z0-9+/_.\-]{8,}", re.I)
# SecretScanner finding types we trust: high-confidence credential formats.
# heroku_api matches any UUID (our synthetic job IDs are UUIDs), and the
# keyword/entropy heuristics flag ordinary prose/source, so those are excluded
# here; UUIDs are judged by our own synthetic-form rule instead.
_SCANNER_IGNORED_TYPES = {"heroku_api", "secret_keyword", "high_entropy_string"}
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# sha256 of the full real IDs the reconstruction redacts (the 2026-02-19
# Slack channel and the six cron job IDs named in research §6.1). Hashes only:
# the plaintext never enters the repo. Candidate tokens are hashed and looked
# up; nothing here is reversible short of brute force over the full ID.
BANNED_ID_SHA256 = frozenset({
    "ee555d7503256db5664dd1e745eed7d54114fe35917ff62a6c7993d8357ada2a",
    "65846820e10b7befc0c1c1453978d68c9d8cc561fb1af43a7a780da6da7c1dc4",
    "3fc9d94cd05a1214587af9cc879031b451ca460a3691a58ec1e27c5c6977f8db",
    "9be6e99a1343ee49912849b7b333891c1202d9482cf2c181893c938c68106298",
    "c770e8871de08a0d0b016963eacacf72482230f65cf6cfc2e9f1a7e516c2b0e8",
    "c498c1dde544c076b97ce55fdafce20c3493261a00dd4dbb35a3f7650fbd9443",
    "c49f6fce28d2fb0d9acdcc420ee7bdaa84b437b9551f8308e7fb97f5db8f9a42",
})
# string-concatenation seams: closing quote, optional `+`, opening quote
CONCAT_SEAM = re.compile(r"[\"']\s*\+?\s*[\"']")
ID_TOKEN = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
                      r"|[CDGUW][A-Z0-9]{8,11}")
FRAGMENT = re.compile(r"([0-9a-f]{8})-([0-9a-f]{4})")
SYNTH_PREFIX = re.compile(r"\b([0-9a-f]{8})-0000-4000-8000-[0-9a-f]{12}\b")

# secret-class patterns can never be allowlisted (banned IDs neither)
SECRET_CLASS = {"akia", "xox", "token_assign", "secret_scanner",
                "banned_id", "real_prefix_fragment"}

# binary / non-text extensions skipped
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".pyc", ".so", ".whl"}


def _git_files(repo):
    files = set()
    try:
        tracked = subprocess.run(["git", "-C", repo, "ls-files"], capture_output=True,
                                 text=True).stdout.splitlines()
        files.update(tracked)
        untracked = subprocess.run(["git", "-C", repo, "ls-files", "--others",
                                    "--exclude-standard"], capture_output=True,
                                   text=True).stdout.splitlines()
        files.update(untracked)
    except Exception:
        for root, _, fns in os.walk(repo):
            for fn in fns:
                files.add(os.path.relpath(os.path.join(root, fn), repo))
    return sorted(f for f in files if f)


def _load_allowlist(repo):
    path = os.path.join(repo, "docs", "SCAN_ALLOWLIST.toml")
    if not os.path.exists(path):
        return []
    with open(path, "rb") as f:
        return tomllib.load(f).get("exception", [])


def _allowed(allowlist, file, pattern_name):
    for e in allowlist:
        if e.get("file") in (file, "*") and e.get("pattern") in (pattern_name, "*"):
            if pattern_name in SECRET_CLASS:
                return False  # secret-class hits cannot be allowlisted
            return True
    return False


def _scan_line(line):
    """Return list of (pattern_name, is_secret_class)."""
    hits = []
    if AKIA.search(line):
        hits.append(("akia", True))
    if XOX.search(line):
        hits.append(("xox", True))
    if TOKEN_ASSIGN.search(line):
        hits.append(("token_assign", True))
    if SLACK_ID.search(line):
        # avoid matching ordinary all-caps words: require a digit
        for m in SLACK_ID.finditer(line):
            if any(ch.isdigit() for ch in m.group(0)):
                hits.append(("slack_id", False))
                break
    for m in ANY_UUID.finditer(line):
        if not SYNTH_UUID.match(m.group(0)):
            hits.append(("real_uuid", False))
            break
    if RFC1918.search(line):
        hits.append(("rfc1918", False))
    if EMAIL.search(line):
        hits.append(("email", False))
    sc = SECRET_SCANNER.scan([line])
    for f in sc["findings"]:
        if f["type"] in _SCANNER_IGNORED_TYPES:
            continue
        hits.append(("secret_scanner", True))
        break
    return hits


def _sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def joined_view(line):
    """The line with string-concatenation seams removed."""
    return CONCAT_SEAM.sub("", line)


def banned_id_hits(line, banned_hashes=BANNED_ID_SHA256, real_prefixes=frozenset()):
    """Known-real-ID hits on the raw line and its joined view."""
    hits = []
    views = {line, joined_view(line)}
    for view in views:
        for m in ID_TOKEN.finditer(view):
            if _sha(m.group(0)) in banned_hashes or _sha(m.group(0).lower()) in banned_hashes:
                hits.append(("banned_id", True))
                break
        if real_prefixes:
            for m in FRAGMENT.finditer(view):
                if m.group(1) in real_prefixes and m.group(2) != "0000":
                    hits.append(("real_prefix_fragment", True))
                    break
    return sorted(set(hits))


def _read_text(full):
    try:
        return open(full, encoding="utf-8", errors="strict").read()
    except (UnicodeDecodeError, OSError):
        return None


def _scannable(repo):
    for rel in _git_files(repo):
        if rel.startswith("local/") or rel.startswith(".venv/"):
            continue
        if os.path.splitext(rel)[1] in SKIP_EXT:
            continue
        full = os.path.join(repo, rel)
        if not os.path.isfile(full):
            continue
        text = _read_text(full)
        if text is None:
            continue
        yield rel, text


def redacted_prefixes(repo):
    """8-hex prefixes of synthetic-form UUIDs in the tree (AC #16 redactions)."""
    out = set()
    for _, text in _scannable(repo):
        out.update(SYNTH_PREFIX.findall(text))
    return frozenset(out)


def scan_ids(repo, extra_banned_hashes=()):
    """Known-real-ID check only (banned_id + real_prefix_fragment), all files
    incl. tests/ and scripts/. Returns (ok, lines)."""
    repo = os.path.abspath(repo)
    banned = BANNED_ID_SHA256 | frozenset(extra_banned_hashes)
    prefixes = redacted_prefixes(repo)
    findings = []
    for rel, text in _scannable(repo):
        for lineno, line in enumerate(text.splitlines(), 1):
            for name, _ in banned_id_hits(line, banned, prefixes):
                findings.append(f"{rel}:{lineno}: {name}")
    if findings:
        return False, ["SCAN FAIL:"] + findings
    return True, [f"SCAN OK (ids only; {len(prefixes)} redacted prefixes, "
                  f"{len(banned)} banned hashes)"]


def _archive_shingles(agents_dir):
    """8-token shingles of user-turn text and exec command strings (in memory)."""
    from .adapters import legacy_jsonl
    shingles = set()
    for path in legacy_jsonl.iter_files(agents_dir):
        for ev in legacy_jsonl.read_file(path, agents_dir):
            if ev["type"] == "turn":
                text = ev.get("text", "")
            elif ev["type"] == "call" and ev.get("tool") == "exec":
                text = str((ev.get("args") or {}).get("command", ""))
            else:
                continue
            toks = text.split()
            for i in range(0, max(0, len(toks) - 7)):
                sh = " ".join(toks[i:i + 8])
                shingles.add(hashlib.sha256(sh.encode("utf-8")).hexdigest())
    return shingles


def scan_repo(repo, against_archive=None, extra_banned_hashes=()):
    repo = os.path.abspath(repo)
    allowlist = _load_allowlist(repo)
    banned = BANNED_ID_SHA256 | frozenset(extra_banned_hashes)
    prefixes = redacted_prefixes(repo)
    findings = []
    for rel, text in _scannable(repo):
        for lineno, line in enumerate(text.splitlines(), 1):
            hits = _scan_line(line) + banned_id_hits(line, banned, prefixes)
            for pattern_name, is_secret in hits:
                if _allowed(allowlist, rel, pattern_name):
                    continue
                findings.append(f"{rel}:{lineno}: {pattern_name}")

    shingle_findings = []
    if against_archive:
        shingles = _archive_shingles(against_archive)
        for rel in _git_files(repo):
            if rel.startswith("local/"):
                continue
            if os.path.splitext(rel)[1] in SKIP_EXT:
                continue
            full = os.path.join(repo, rel)
            if not os.path.isfile(full):
                continue
            try:
                text = open(full, encoding="utf-8", errors="strict").read()
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                toks = line.split()
                for i in range(0, max(0, len(toks) - 7)):
                    sh = " ".join(toks[i:i + 8])
                    h = hashlib.sha256(sh.encode("utf-8")).hexdigest()
                    if h in shingles and not _allowed(allowlist, rel, "transcript_shingle"):
                        shingle_findings.append(f"{rel}:{lineno}: transcript shingle match")
                        break

    all_findings = findings + shingle_findings
    if all_findings:
        return False, ["SCAN FAIL:"] + all_findings
    return True, ["SCAN OK"]
