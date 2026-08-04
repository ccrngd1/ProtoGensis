"""The parser JSON contract shared by the Java (ProLeap) wrapper and the
Python fallback parser.

Both parsers MUST emit this exact shape so the rest of Cobalt is
parser-agnostic. Version bumps to the shape bump SCHEMA_VERSION and the JAR
filename together.

Top-level document:

{
  "schema_version": "cobalt-parser-v0",
  "parser": "proleap" | "fallback",
  "program_id": "CLAIMCALC",
  "source_file": "claimcalc.cbl",
  "copybooks": [{"name": "CLAIMREC", "path": "copy/CLAIMREC.cpy"}],
  "data_items": [DataItem, ...],          # top-level (01/77) items, nested
  "paragraphs": [Paragraph, ...],         # in source order
  "perform_graph": {"0000-MAIN": ["1000-INIT", ...]},
  "diagnostics": ["..."]                  # non-fatal parse warnings
}

DataItem:

{
  "level": 5,
  "name": "CLM-BILLED-AMT",               # "FILLER" for filler items
  "picture": "S9(7)V99",                  # null when group item
  "usage": "COMP-3" | "DISPLAY" | ...,
  "signed": true,
  "integer_digits": 7,                    # digits left of assumed decimal
  "fraction_digits": 2,                   # digits right of assumed decimal (V)
  "alpha_length": null,                   # length for PIC X/A items
  "occurs": {"times": 4, "indexed_by": "BEN-IDX"} | null,
  "redefines": "BENEFIT-TABLE-INIT" | null,
  "value": "\"PPO...\"" | null,           # VALUE clause literal, verbatim
  "condition_names": [                    # 88-levels attached to this item
      {"name": "CLM-TYPE-MEDICAL", "values": ["\"MD\""]}
  ],
  "children": [DataItem, ...],
  "source": "CLAIMREC.cpy" | "claimcalc.cbl"
}

Paragraph:

{
  "name": "2000-PROCESS-ONE-CLAIM",
  "performs": ["2100-LOAD-CLAIM", ...],   # PERFORM targets, in order, deduped
  "line": 104
}
"""

from __future__ import annotations

SCHEMA_VERSION = "cobalt-parser-v0"

_TOP_LEVEL_KEYS = {
    "schema_version",
    "parser",
    "program_id",
    "source_file",
    "copybooks",
    "data_items",
    "paragraphs",
    "perform_graph",
    "diagnostics",
}

_DATA_ITEM_KEYS = {
    "level",
    "name",
    "picture",
    "usage",
    "signed",
    "integer_digits",
    "fraction_digits",
    "alpha_length",
    "occurs",
    "redefines",
    "value",
    "condition_names",
    "children",
    "source",
}


class SchemaError(ValueError):
    """Parser output does not match the cobalt-parser-v0 contract."""


def validate(doc: dict) -> dict:
    """Validate a parser document against the contract. Returns the doc.

    Deliberately strict on structure and permissive on content: the goal is
    to catch a drifting Java wrapper or fallback parser early, not to
    re-validate COBOL semantics.
    """
    if not isinstance(doc, dict):
        raise SchemaError(f"parser output must be an object, got {type(doc).__name__}")
    missing = _TOP_LEVEL_KEYS - set(doc)
    if missing:
        raise SchemaError(f"parser output missing keys: {sorted(missing)}")
    if doc["schema_version"] != SCHEMA_VERSION:
        raise SchemaError(
            f"schema_version mismatch: expected {SCHEMA_VERSION!r}, "
            f"got {doc['schema_version']!r}"
        )
    if doc["parser"] not in ("proleap", "fallback"):
        raise SchemaError(f"unknown parser {doc['parser']!r}")
    for item in doc["data_items"]:
        _validate_item(item)
    for para in doc["paragraphs"]:
        if "name" not in para or "performs" not in para:
            raise SchemaError(f"paragraph missing name/performs: {para}")
    if not isinstance(doc["perform_graph"], dict):
        raise SchemaError("perform_graph must be an object")
    return doc


def _validate_item(item: dict, path: str = "") -> None:
    where = f"{path}/{item.get('name', '?')}"
    missing = _DATA_ITEM_KEYS - set(item)
    if missing:
        raise SchemaError(f"data item {where} missing keys: {sorted(missing)}")
    if not isinstance(item["level"], int):
        raise SchemaError(f"data item {where}: level must be int")
    for child in item["children"]:
        _validate_item(child, where)


def walk_items(doc: dict):
    """Yield every data item in the document, depth-first."""

    def _walk(items):
        for item in items:
            yield item
            yield from _walk(item["children"])

    yield from _walk(doc["data_items"])
