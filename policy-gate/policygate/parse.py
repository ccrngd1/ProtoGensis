"""PARSE: markdown -> clauses with heading inheritance and provenance (AC #4).

DETERMINISTIC. Segments markdown into clauses (bullets, numbered items,
paragraphs, table rows); fenced code blocks are skipped and counted. Each
clause carries src {file, commit, line, heading}, the full heading_chain,
inherited_qualifiers (parenthesized text and without/unless/except/only-if
phrases from any ancestor heading), rule_bearing, clause_sha256 and
section_hash. cron/jobs.json payload prompts become clauses with
heading "job:<first 8 hex of id>".
"""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field, asdict

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
RULE_MARKER = re.compile(r"\bnever\b|\bdo not\b|\bmust\b|\bforbidden\b|❌|\balways\b|\bpermanent\b|\bmandatory\b", re.I)
QUALIFIER_PAREN = re.compile(r"\(([^)]*)\)")
QUALIFIER_PHRASE = re.compile(r"\b((?:without|unless|except|only if)\b[^,;:()]*)", re.I)
EMPHASIS = re.compile(r"(\*\*|__|\*|_|`)")


@dataclass
class Clause:
    text: str
    src: dict          # {file, commit, line, heading}
    heading_chain: list
    inherited_qualifiers: list
    rule_bearing: bool
    clause_sha256: str
    section_hash: str
    kind: str = "clause"   # clause | table_row | cron_payload
    subjects: list = field(default_factory=lambda: ["*"])

    @property
    def clause_id(self):
        c = (self.src.get("commit") or "worktree")[:8]
        return f"{self.src['file']}@{c}:{self.src['line']}"


def normalize_text(s):
    s = unicodedata.normalize("NFC", s)
    s = EMPHASIS.sub("", s)
    return " ".join(s.split())


def _sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _qualifiers_of(heading):
    quals = []
    for m in QUALIFIER_PAREN.finditer(heading):
        quals.append(m.group(1).strip())
    for m in QUALIFIER_PHRASE.finditer(heading):
        q = m.group(1).strip().rstrip(":").strip()
        if q and q not in quals:
            quals.append(q)
    return quals


def parse_markdown(text, file, commit, subjects=None):
    """Parse one markdown document into clauses. Returns (clauses, fenced_blocks_skipped)."""
    subjects = subjects or ["*"]
    lines = text.split("\n")
    chain = []            # list of (level, heading_text)
    clauses = []
    fenced = 0
    in_fence = False
    fence_marker = None
    para, para_start = [], None

    # First pass: record section text per heading for section_hash
    section_lines = {}    # heading text at nearest level -> [lines]
    cur_heading = ""
    fence2 = False
    for ln in lines:
        if FENCE_RE.match(ln):
            fence2 = not fence2
            continue
        if fence2:
            continue
        hm = HEADING_RE.match(ln)
        if hm:
            cur_heading = hm.group(2).strip()
            section_lines.setdefault(cur_heading, [])
            continue
        section_lines.setdefault(cur_heading, []).append(ln)
    section_hashes = {
        h: _sha(normalize_text("\n".join(ls))) for h, ls in section_lines.items()
    }

    def heading(): return chain[-1][1] if chain else ""

    def quals():
        out = []
        for _, h in chain:
            for q in _qualifiers_of(h):
                if q not in out:
                    out.append(q)
        return out

    def emit(text_, line_no, kind="clause"):
        nt = normalize_text(text_)
        if not nt:
            return
        clauses.append(Clause(
            text=nt,
            src={"file": file, "commit": commit, "line": line_no, "heading": heading()},
            heading_chain=[h for _, h in chain],
            inherited_qualifiers=quals(),
            rule_bearing=bool(RULE_MARKER.search(nt)),
            clause_sha256=_sha(nt),
            section_hash=section_hashes.get(heading(), _sha("")),
            kind=kind,
            subjects=list(subjects),
        ))

    def flush_para():
        nonlocal para, para_start
        if para:
            emit(" ".join(para), para_start)
        para, para_start = [], None

    for i, ln in enumerate(lines, start=1):
        fm = FENCE_RE.match(ln)
        if fm:
            if not in_fence:
                in_fence, fence_marker = True, fm.group(1)
                fenced += 1
                flush_para()
            elif ln.strip().startswith(fence_marker):
                in_fence = False
            continue
        if in_fence:
            continue
        hm = HEADING_RE.match(ln)
        if hm:
            flush_para()
            level = len(hm.group(1))
            while chain and chain[-1][0] >= level:
                chain.pop()
            chain.append((level, hm.group(2).strip()))
            continue
        bm = BULLET_RE.match(ln)
        if bm:
            flush_para()
            emit(bm.group(1), i)
            continue
        if TABLE_ROW_RE.match(ln):
            flush_para()
            if not TABLE_SEP_RE.match(ln):
                emit(ln.strip().strip("|").strip(), i, kind="table_row")
            continue
        if not ln.strip():
            flush_para()
            continue
        if para_start is None:
            para_start = i
        para.append(ln.strip())
    flush_para()
    return clauses, fenced


def parse_cron_payloads(text, file, commit):
    """cron/jobs.json payload prompts -> one clause per job (AC #3)."""
    clauses = []
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return clauses
    jobs = data.get("jobs", data) if isinstance(data, dict) else data
    if not isinstance(jobs, list):
        return clauses
    for j in jobs:
        if not isinstance(j, dict):
            continue
        jid = str(j.get("id", ""))
        payload = j.get("payload") or {}
        msg = payload.get("message") or payload.get("prompt") or ""
        if isinstance(msg, dict):
            msg = msg.get("text", "")
        agent = j.get("agentId") or j.get("agent") or "*"
        nt = normalize_text(str(msg))
        if not nt:
            continue
        heading = f"job:{jid[:8]}"
        clauses.append(Clause(
            text=nt,
            src={"file": file, "commit": commit, "line": 0, "heading": heading},
            heading_chain=[heading],
            inherited_qualifiers=[],
            rule_bearing=bool(RULE_MARKER.search(nt)),
            clause_sha256=_sha(nt),
            section_hash=_sha(nt),
            kind="cron_payload",
            subjects=[f"agent:{agent}" if agent not in ("*", "main") else agent],
        ))
    return clauses


def parse_bundle(bundle_at):
    """Parse every present source of a resolved bundle. Returns dict."""
    all_clauses = []
    fenced_total = 0
    for path, src in sorted(bundle_at.sources.items()):
        if src.text is None:
            continue
        if src.kind == "cron_payloads":
            all_clauses.extend(parse_cron_payloads(src.text, path, src.commit))
        else:
            cls_, fenced = parse_markdown(src.text, path, src.commit, src.subjects)
            all_clauses.extend(cls_)
            fenced_total += fenced
    return {"at": bundle_at.at, "clauses": all_clauses, "fenced_blocks_skipped": fenced_total}


def render(parsed, fmt):
    data = {
        "at": parsed["at"],
        "clauses": [asdict(c) | {"id": c.clause_id} for c in parsed["clauses"]],
        "fenced_blocks_skipped": parsed["fenced_blocks_skipped"],
        "count": len(parsed["clauses"]),
    }
    if fmt == "json":
        return json.dumps(data, sort_keys=True, indent=2)
    lines = [f"clauses: {data['count']}  fenced blocks skipped: {data['fenced_blocks_skipped']}"]
    for c in parsed["clauses"]:
        rb = "R" if c.rule_bearing else " "
        lines.append(f"  [{rb}] {c.clause_id}  {c.text[:80]}")
    return "\n".join(lines)
