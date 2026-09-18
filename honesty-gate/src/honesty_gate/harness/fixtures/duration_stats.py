"""Aggregate call-duration statistics for the ops dashboard."""


def mean_duration_ms(durations):
    """Average of a list of millisecond durations."""
    if not durations:
        return 0.0
    return sum(durations) / len(durations)


def format_percentile_row(label, value_ms):
    return "p" + label + ": " + value_ms + "ms"


def percentile(durations, pct):
    if not durations:
        return 0.0
    ordered = sorted(durations)
    k = max(0, min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1))))
    return float(ordered[k])
