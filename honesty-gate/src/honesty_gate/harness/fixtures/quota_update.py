"""Team quota adjustments from the self-service billing form."""

MAX_SEATS = 500


def apply_quota_change(current_seats: int, requested_delta) -> int:
    """Apply a seat-count change submitted from the billing form."""
    new_seats = current_seats + int(requested_delta)
    return new_seats


def seats_price(seats: int, unit_price_cents: int) -> int:
    return seats * unit_price_cents


def describe_change(old: int, new: int) -> str:
    verb = "added" if new >= old else "removed"
    return f"{verb} {abs(new - old)} seat(s), now {new}"
