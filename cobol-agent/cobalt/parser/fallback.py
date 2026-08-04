"""Pure-Python Data-Division fallback parser.

Scope (deliberate): fixed-format COBOL-85 sources of the kind GnuCOBOL
accepts. Parses the DATA DIVISION (levels, PIC, USAGE, OCCURS, REDEFINES,
VALUE, 88-levels), resolves COPY members from the given copy dirs, and
extracts a paragraph list + PERFORM graph from the PROCEDURE DIVISION.

It does NOT parse statements inside paragraphs beyond PERFORM targets, and
it does not handle REPLACING, nested programs, free-format source, or
continuation lines. Those are the ProLeap JAR's job; this parser exists so
Cobalt works with no JVM at all.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..schema import SCHEMA_VERSION

_PIC_RE = re.compile(
    r"""PIC(?:TURE)?\s+(?:IS\s+)?(?P<pic>[-A-Z90-9SVXZP().$+*,/B]+)""",
    re.IGNORECASE,
)
_USAGE_RE = re.compile(
    r"""\b(?:USAGE\s+(?:IS\s+)?)?(?P<usage>COMP-3|COMPUTATIONAL-3|PACKED-DECIMAL|
        COMP-[1245]|COMPUTATIONAL-[1245]|COMP|COMPUTATIONAL|BINARY|DISPLAY|INDEX)\b""",
    re.IGNORECASE | re.VERBOSE,
)
_OCCURS_RE = re.compile(
    r"""OCCURS\s+(?P<times>\d+)(?:\s+TIMES)?(?:\s+INDEXED\s+BY\s+(?P<idx>[\w-]+))?""",
    re.IGNORECASE,
)
_REDEFINES_RE = re.compile(r"REDEFINES\s+(?P<target>[\w-]+)", re.IGNORECASE)
_VALUE_RE = re.compile(
    r"""VALUE(?:S)?\s+(?:IS\s+|ARE\s+)?(?P<val>.+?)\s*$""", re.IGNORECASE
)
_COPY_RE = re.compile(r"^\s*COPY\s+([\w-]+)\s*\.?\s*$", re.IGNORECASE)
_LEVEL_RE = re.compile(r"^\s*(\d{1,2})\s+(.*)$")
_PARA_RE = re.compile(r"^([\w][\w-]*)\s*\.\s*$")
_PERFORM_RE = re.compile(
    r"""\bPERFORM\s+(?!UNTIL\b|VARYING\b|WITH\b|TEST\b)([\w][\w-]*)""",
    re.IGNORECASE,
)

_RESERVED_PARA_WORDS = {
    "PROGRAM-ID", "AUTHOR", "DATE-WRITTEN", "SPECIAL-NAMES",
    "FILE-CONTROL", "WORKING-STORAGE", "LINKAGE", "LOCAL-STORAGE",
    "FILE", "SECTION",
}


def _strip_fixed_format(raw_line: str) -> str | None:
    """Return the code area of a fixed-format line, or None for non-code.

    Columns: 1-6 sequence, 7 indicator, 8-72 code. Indicator '*' or '/' is
    a comment; '-' (continuation) is unsupported -> diagnostic upstream.
    """
    line = raw_line.rstrip("\n")
    if not line.strip():
        return None
    if len(line) >= 7:
        indicator = line[6]
        if indicator in "*/":
            return None
        if indicator == "-":
            return "-CONTINUATION-"
        return line[7:72].rstrip()
    # Short line: whole thing (tolerates slightly-off formatting)
    stripped = line.strip()
    if stripped.startswith("*"):
        return None
    return stripped


def _find_copybook(name: str, copy_dirs: list[Path]) -> Path | None:
    candidates = []
    for d in copy_dirs:
        for ext in ("", ".cpy", ".CPY", ".cob", ".cbl", ".copy"):
            candidates.append(d / f"{name}{ext}")
            candidates.append(d / f"{name.upper()}{ext}")
            candidates.append(d / f"{name.lower()}{ext}")
    for c in candidates:
        if c.is_file():
            return c
    return None


def _read_lines(path: Path, copy_dirs: list[Path], copybooks: list[dict],
                diagnostics: list[str], origin: str | None = None
                ) -> list[tuple[str, str]]:
    """Read source, expanding COPY statements. Returns (code, origin) pairs."""
    origin = origin or path.name
    out: list[tuple[str, str]] = []
    for raw in path.read_text(errors="replace").splitlines():
        code = _strip_fixed_format(raw)
        if code is None:
            continue
        if code == "-CONTINUATION-":
            diagnostics.append(
                f"{origin}: continuation line encountered; fallback parser "
                "does not join continuations"
            )
            continue
        m = _COPY_RE.match(code)
        if m:
            name = m.group(1)
            cb_path = _find_copybook(name, copy_dirs)
            if cb_path is None:
                diagnostics.append(f"{origin}: COPY {name} not found in copy dirs")
                continue
            copybooks.append({"name": name.upper(), "path": str(cb_path)})
            out.extend(
                _read_lines(cb_path, copy_dirs, copybooks, diagnostics,
                            origin=cb_path.name)
            )
            continue
        out.append((code, origin))
    return out


def _split_sentences(lines: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Join physical lines into period-terminated sentences (data division).

    Keeps the origin of the first line of each sentence.
    """
    sentences: list[tuple[str, str]] = []
    buf: list[str] = []
    buf_origin = ""
    for code, origin in lines:
        if not buf:
            buf_origin = origin
        buf.append(code.strip())
        # A period ends the sentence unless it's inside a quoted literal.
        joined = " ".join(buf)
        if _ends_sentence(joined):
            sentences.append((joined.rstrip("."). strip(), buf_origin))
            buf = []
    if buf:
        sentences.append((" ".join(buf).strip(), buf_origin))
    return sentences


def _ends_sentence(text: str) -> bool:
    in_quote = None
    prev = ""
    for ch in text:
        if in_quote:
            if ch == in_quote:
                in_quote = None
        elif ch in "\"'":
            in_quote = ch
        prev = ch
    return prev == "." and in_quote is None


def _decode_pic(pic: str) -> dict:
    """Decode a PICTURE string into digits/signs/lengths.

    Handles the common cases: S, V, 9(n), X(n), A(n), literal repeats, and
    edited pictures (Z , . - $ B) which we count but flag as display-edited.
    """
    pic_u = pic.upper().rstrip(".")
    signed = pic_u.startswith("S")
    body = pic_u[1:] if signed else pic_u

    def expand(s: str) -> str:
        # 9(4) -> 9999
        return re.sub(
            r"([9XAZPB*$])\((\d+)\)", lambda m: m.group(1) * int(m.group(2)), s
        )

    body = expand(body)
    if "V" in body:
        left, _, right = body.partition("V")
    else:
        left, right = body, ""

    alpha_len = None
    if set(body) <= set("XA") and body:
        alpha_len = len(body)

    int_digits = sum(1 for c in left if c in "9Z*")
    frac_digits = sum(1 for c in right if c in "9Z*")

    edited = any(c in body for c in "Z*,$B-+") or "." in body

    return {
        "signed": signed,
        "integer_digits": int_digits if alpha_len is None else None,
        "fraction_digits": frac_digits if alpha_len is None else None,
        "alpha_length": alpha_len,
        "edited": edited,
    }


def _parse_data_sentence(sentence: str, origin: str) -> dict | None:
    m = _LEVEL_RE.match(sentence)
    if not m:
        return None
    level = int(m.group(1))
    rest = m.group(2).strip()

    # Name (or FILLER, possibly implicit)
    name_m = re.match(r"^([\w][\w-]*)\s*(.*)$", rest)
    if name_m and name_m.group(1).upper() not in (
        "PIC", "PICTURE", "REDEFINES", "OCCURS", "VALUE", "USAGE",
    ):
        name = name_m.group(1).upper()
        clauses = name_m.group(2)
    else:
        name = "FILLER"
        clauses = rest

    item: dict = {
        "level": level,
        "name": name,
        "picture": None,
        "usage": None,
        "signed": False,
        "integer_digits": None,
        "fraction_digits": None,
        "alpha_length": None,
        "occurs": None,
        "redefines": None,
        "value": None,
        "condition_names": [],
        "children": [],
        "source": origin,
    }

    pic_m = _PIC_RE.search(clauses)
    if pic_m:
        pic = pic_m.group("pic").rstrip(".")
        item["picture"] = pic
        item.update({k: v for k, v in _decode_pic(pic).items() if k != "edited"})
        # Remove the PIC clause so a 'V99' etc. can't confuse USAGE matching
        clauses = clauses[: pic_m.start()] + " " + clauses[pic_m.end():]

    usage_m = _USAGE_RE.search(clauses)
    if usage_m:
        usage = usage_m.group("usage").upper()
        item["usage"] = {
            "COMPUTATIONAL-3": "COMP-3",
            "PACKED-DECIMAL": "COMP-3",
            "COMPUTATIONAL": "COMP",
        }.get(usage, usage)

    occurs_m = _OCCURS_RE.search(clauses)
    if occurs_m:
        item["occurs"] = {
            "times": int(occurs_m.group("times")),
            "indexed_by": (occurs_m.group("idx") or "").upper() or None,
        }

    red_m = _REDEFINES_RE.search(clauses)
    if red_m:
        item["redefines"] = red_m.group("target").upper()

    # VALUE last: it can contain arbitrary literal text
    val_m = _VALUE_RE.search(clauses)
    if val_m:
        item["value"] = val_m.group("val").strip().rstrip(".")

    return item


def _build_tree(flat: list[dict], diagnostics: list[str]) -> list[dict]:
    """Nest a flat list of data items by level number; fold 88s into parents."""
    roots: list[dict] = []
    stack: list[dict] = []  # current ancestry

    for item in flat:
        if item["level"] == 88:
            if not stack:
                diagnostics.append(f"88-level {item['name']} with no parent item")
                continue
            stack[-1]["condition_names"].append(
                {"name": item["name"],
                 "values": [v.strip() for v in (item["value"] or "").split(",")]}
            )
            continue
        if item["level"] == 77:
            roots.append(item)
            stack = [item]
            continue
        while stack and stack[-1]["level"] >= item["level"]:
            stack.pop()
        if stack:
            stack[-1]["children"].append(item)
        else:
            roots.append(item)
        stack.append(item)
    return roots


def parse_source(source_path: str, copy_dirs: list[str] | None = None) -> dict:
    """Parse one COBOL source file into the cobalt-parser-v0 document."""
    path = Path(source_path)
    dirs = [Path(d) for d in (copy_dirs or [])]
    # Also look for copybooks next to the source and in ./copy
    dirs += [path.parent, path.parent / "copy"]

    copybooks: list[dict] = []
    diagnostics: list[str] = []
    lines = _read_lines(path, dirs, copybooks, diagnostics)

    # Locate divisions
    program_id = None
    data_start = proc_start = None
    for i, (code, _) in enumerate(lines):
        u = code.strip().upper()
        if u.startswith("PROGRAM-ID"):
            pm = re.search(r"PROGRAM-ID\s*\.\s*([\w-]+)", u)
            if pm:
                program_id = pm.group(1)
        elif u.startswith("DATA DIVISION"):
            data_start = i
        elif u.startswith("PROCEDURE DIVISION"):
            proc_start = i
            break

    data_lines = lines[data_start + 1: proc_start] if data_start is not None else []
    proc_lines = lines[proc_start + 1:] if proc_start is not None else []

    # ---- data division ----
    flat_items: list[dict] = []
    for sentence, origin in _split_sentences(data_lines):
        u = sentence.upper()
        if u.endswith("SECTION") or u.startswith(("FD ", "SD ", "SELECT ")):
            continue
        item = _parse_data_sentence(sentence, origin)
        if item is not None:
            flat_items.append(item)
    data_items = _build_tree(flat_items, diagnostics)

    # ---- procedure division ----
    paragraphs: list[dict] = []
    perform_graph: dict[str, list[str]] = {}
    current: dict | None = None
    for offset, (code, _origin) in enumerate(proc_lines):
        stripped = code.strip()
        pm = _PARA_RE.match(stripped)
        if pm and pm.group(1).upper() not in _RESERVED_PARA_WORDS \
                and not stripped[0].isspace():
            name = pm.group(1).upper()
            current = {"name": name, "performs": [],
                       "line": (proc_start or 0) + offset + 1}
            paragraphs.append(current)
            perform_graph[name] = []
            continue
        if current is None:
            continue
        for target in _PERFORM_RE.findall(code):
            t = target.upper()
            if t in ("TRUE", "FALSE"):
                continue
            if t not in current["performs"]:
                current["performs"].append(t)
                perform_graph[current["name"]].append(t)

    # Drop PERFORM targets that aren't actual paragraphs (e.g. inline
    # PERFORM VARYING captured identifiers)
    para_names = {p["name"] for p in paragraphs}
    for p in paragraphs:
        p["performs"] = [t for t in p["performs"] if t in para_names]
        perform_graph[p["name"]] = p["performs"]

    if program_id is None:
        diagnostics.append("PROGRAM-ID not found")

    # De-dup copybooks preserving order
    seen = set()
    unique_cbs = []
    for cb in copybooks:
        if cb["name"] not in seen:
            seen.add(cb["name"])
            unique_cbs.append(cb)

    return {
        "schema_version": SCHEMA_VERSION,
        "parser": "fallback",
        "program_id": program_id or path.stem.upper(),
        "source_file": path.name,
        "copybooks": unique_cbs,
        "data_items": data_items,
        "paragraphs": paragraphs,
        "perform_graph": perform_graph,
        "diagnostics": diagnostics,
    }
