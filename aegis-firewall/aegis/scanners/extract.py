"""Deep string extractor for MCP tool call arguments.

Recursively extracts all string values from nested JSON/dict structures.
"""

from typing import Any, List


def extract_strings(obj: Any, max_depth: int = 10, _depth: int = 0) -> List[str]:
    """
    Recursively extract all string values from a nested structure.

    Args:
        obj: The object to extract strings from (dict, list, or primitive)
        max_depth: Maximum recursion depth to prevent infinite loops
        _depth: Current recursion depth (internal use)

    Returns:
        List of all extracted strings

    Examples:
        >>> extract_strings({"cmd": "ls -la", "args": ["-R", "/tmp"]})
        ['ls -la', '-R', '/tmp']

        >>> extract_strings({"nested": {"deep": {"value": "found"}}})
        ['found']
    """
    if _depth >= max_depth:
        return []

    strings = []

    if isinstance(obj, str):
        strings.append(obj)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            # Extract from both keys and values
            if isinstance(key, str):
                strings.append(key)
            strings.extend(extract_strings(value, max_depth, _depth + 1))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            strings.extend(extract_strings(item, max_depth, _depth + 1))
    elif isinstance(obj, (int, float, bool)):
        # Convert to string for scanning
        strings.append(str(obj))
    elif obj is None:
        pass  # Skip None values
    else:
        # For other types, try to convert to string
        try:
            strings.append(str(obj))
        except Exception:
            pass

    return strings
