"""Deep string extraction from nested JSON structures."""

from typing import Any, Iterator


def extract_strings(obj: Any, max_depth: int = 50) -> Iterator[str]:
    """
    Recursively extract all string values from nested JSON-like structures.

    Args:
        obj: Any JSON-serializable object (dict, list, str, int, etc.)
        max_depth: Maximum recursion depth to prevent stack overflow

    Yields:
        All string values found in the structure
    """
    if max_depth <= 0:
        return

    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from extract_strings(value, max_depth - 1)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from extract_strings(item, max_depth - 1)
    # Numbers, booleans, None are ignored
