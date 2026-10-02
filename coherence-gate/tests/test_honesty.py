"""Honesty / positioning grep tests (AC #12), enforced in CI not just review."""
import pathlib
import re

ROOT = pathlib.Path(__file__).parent.parent
README = (ROOT / "README.md").read_text()
FIRST_40 = "\n".join(README.splitlines()[:40])

BANNED = re.compile(
    r"first (tool|library|implementation)|only tool|no existing tool|zero tools|first-ever",
    re.IGNORECASE)

ALLOWLIST = {
    "2610.02036", "2605.07073", "2506.07982", "2606.15376", "2605.17076",
    "2605.20563", "2602.14849", "2603.13906", "2511.03761", "2608.18092",
    "2603.15183", "2503.11951", "2506.07564", "2510.18893", "2606.21666",
    "2605.20173", "2503.13657", "2604.08224", "2605.30335",
}

ARXIV_ID = re.compile(r"\b[0-9]{4}\.[0-9]{5}\b")


def all_prose_files():
    files = [ROOT / "README.md"]
    docs = ROOT / "docs"
    if docs.exists():
        files.extend(docs.rglob("*.md"))
    files.extend((ROOT / "coherencegate").rglob("*.py"))
    return files


def test_no_banned_phrases_anywhere():
    for path in all_prose_files():
        text = path.read_text()
        match = BANNED.search(text)
        assert match is None, f"banned phrase {match.group(0)!r} in {path}"


def test_readme_first_screenful_citation():
    assert "2610.02036" in FIRST_40


def test_readme_first_screenful_prior_art():
    assert re.search(r"related work\s*/\s*prior art", FIRST_40, re.IGNORECASE)
    for tool in ("agent-coherence", "CoAgent", "S-Bus", "STORM", "Atomix", "ATCC"):
        assert tool in FIRST_40, f"missing prior-art credit: {tool}"


def test_readme_first_screenful_unreleased_statement():
    assert re.search(r"not yet released|unreleased", FIRST_40, re.IGNORECASE)


def test_readme_first_screenful_coherenceprobe_line():
    assert re.search(r"prevent.*commit", FIRST_40, re.IGNORECASE)
    assert re.search(r"detect.*afterward", FIRST_40, re.IGNORECASE)


def test_readme_credits_occ():
    assert "Kung & Robinson" in README


def test_arxiv_ids_in_allowlist():
    files = [ROOT / "README.md"]
    docs = ROOT / "docs"
    if docs.exists():
        files.extend(docs.rglob("*.md"))
    for path in files:
        found = set(ARXIV_ID.findall(path.read_text()))
        rogue = found - ALLOWLIST
        assert not rogue, f"non-allowlisted arXiv-shaped IDs in {path}: {rogue}"


def test_license_is_mit():
    text = (ROOT / "LICENSE").read_text()
    assert "MIT License" in text


def test_readme_clone_url_is_monorepo_path():
    assert "ccrngd1/ProtoGensis" in README
    assert "pip install coherence-gate" not in README
    assert "pip install coherencegate" not in README


def test_no_third_party_imports_in_core():
    """Core is stdlib-only; even adapters import third-party lazily."""
    pattern = re.compile(
        r"^\s*(import|from) (boto3|langgraph|requests|httpx|openai|anthropic)\b")
    for path in (ROOT / "coherencegate").rglob("*.py"):
        if "adapters" in path.parts:
            # adapters may import lazily inside functions (indented), never at module level
            for line in path.read_text().splitlines():
                if pattern.match(line) and not line.startswith((" ", "\t")):
                    raise AssertionError(f"module-level third-party import in {path}: {line}")
            continue
        for line in path.read_text().splitlines():
            assert not pattern.match(line), f"third-party import in core {path}: {line}"


def test_stale_rejections_never_called_aliasing():
    """Keep the failure modes separate: gate code never says 'aliasing'."""
    for name in ("gate.py", "store.py", "owners.py"):
        text = (ROOT / "coherencegate" / name).read_text()
        assert "alias" not in text.lower(), f"'aliasing' language leaked into {name}"
