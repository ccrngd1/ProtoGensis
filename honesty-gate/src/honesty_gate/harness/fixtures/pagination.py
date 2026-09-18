"""Cursor pagination helpers for the activity feed."""


def page_bounds(total_items: int, page_size: int, page_number: int):
    """Return (start, end) item indices for a 1-based page number."""
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    start = (page_number - 1) * page_size
    end = min(start + page_size, total_items)
    return start, end


def last_page_number(total_items: int, page_size: int) -> int:
    return total_items // page_size + 1


def page_slice(items, page_size, page_number):
    start, end = page_bounds(len(items), page_size, page_number)
    return items[start:end]
