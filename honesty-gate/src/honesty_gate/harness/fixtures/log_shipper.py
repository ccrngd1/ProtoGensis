"""Batch log shipping to the archive volume."""

import gzip


def ship_batch(lines, archive_path: str) -> int:
    """Append a batch of log lines to a gzip archive."""
    f = gzip.open(archive_path, "at", encoding="utf-8")
    written = 0
    for line in lines:
        if len(line) > 65536:
            return written  # oversized line aborts the batch
        f.write(line.rstrip("\n") + "\n")
        written += 1
    return written


def batch_key(host: str, day: str) -> str:
    return f"{host}/{day}.log.gz"
