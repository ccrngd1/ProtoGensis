"""PIC / USAGE -> Java type mapping rules.

This module is the "COMP-3 correctness moat": the deterministic rules that
the LLM prompts embed and that the generated-code checks verify against.

Rules (from the requirements doc):

  PIC X(n) / A(n)                      -> String
  PIC 9(n), n <= 9, no V, not COMP-3   -> int
  PIC 9(n), n > 9, no V, not COMP-3    -> long
  PIC S9(n)V9(m) COMP-3                -> BigDecimal, scale = m
  Any PIC with V (assumed decimal)     -> BigDecimal, scale = fraction digits
  Any COMP-3 field                     -> BigDecimal (even integer COMP-3:
                                          scale = 0) -- never double/float
  88-level condition names             -> boolean helper methods / enum
  OCCURS n                             -> Java array or List, fixed length n
  REDEFINES                            -> flagged for human review; the LLM
                                          must pick one interpretation and
                                          document the other

Monetary arithmetic: COBOL COMPUTE without ROUNDED truncates toward zero at
the receiving field's scale -> RoundingMode.DOWN. COBOL ROUNDED is
half-away-from-zero -> RoundingMode.HALF_UP.
"""

from __future__ import annotations

from dataclasses import dataclass

# Rounding-mode constants the prompts and tests share.
JAVA_TRUNCATION = "RoundingMode.DOWN"      # COBOL default (no ROUNDED)
JAVA_ROUNDED = "RoundingMode.HALF_UP"      # COBOL ROUNDED phrase

_COMP3_USAGES = {"COMP-3", "COMPUTATIONAL-3", "PACKED-DECIMAL"}


@dataclass
class JavaType:
    java_type: str            # "String" | "int" | "long" | "BigDecimal"
    scale: int | None = None  # BigDecimal scale, None otherwise
    note: str | None = None   # human-review flags (REDEFINES etc.)

    def render(self) -> str:
        if self.java_type == "BigDecimal":
            return f"BigDecimal(scale={self.scale})"
        return self.java_type


def is_comp3(item: dict) -> bool:
    return (item.get("usage") or "").upper() in _COMP3_USAGES


def java_type_for(item: dict) -> JavaType | None:
    """Map one parser-schema data item to its Java type.

    Returns None for group items (no PICTURE) — groups become classes.
    """
    pic = item.get("picture")
    if pic is None:
        return None

    frac = item.get("fraction_digits") or 0
    ints = item.get("integer_digits") or 0
    comp3 = is_comp3(item)

    if item.get("alpha_length") is not None:
        return JavaType("String")

    # COMP-3 always BigDecimal — packed decimal must never ride in a float,
    # and keeping integer COMP-3 in BigDecimal(0) avoids silent overflow
    # and keeps arithmetic rules uniform.
    if comp3:
        return JavaType("BigDecimal", scale=frac)

    # Assumed decimal point (V) -> BigDecimal at the declared scale.
    if frac > 0:
        return JavaType("BigDecimal", scale=frac)

    # Pure integer DISPLAY/BINARY numerics.
    if ints <= 9:
        return JavaType("int")
    if ints <= 18:
        return JavaType("long")
    return JavaType("BigDecimal", scale=0, note="more than 18 digits")


def type_table(doc: dict) -> list[dict]:
    """Flatten a parser document into rows the prompts embed.

    Each row: {name, picture, usage, java, scale, occurs, redefines,
    condition_names, source}.
    """
    from .schema import walk_items

    rows = []
    for item in walk_items(doc):
        jt = java_type_for(item)
        row = {
            "name": item["name"],
            "level": item["level"],
            "picture": item.get("picture"),
            "usage": item.get("usage") or "DISPLAY",
            "java": jt.render() if jt else "(group -> class)",
            "occurs": (item.get("occurs") or {}).get("times"),
            "redefines": item.get("redefines"),
            "condition_names": [c["name"] for c in item.get("condition_names", [])],
            "source": item.get("source"),
        }
        rows.append(row)
    return rows
