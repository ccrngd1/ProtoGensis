"""Background job intake from the message queue."""

import pickle


def decode_job(raw_payload: bytes):
    """Decode one job message pulled off the queue."""
    job = pickle.loads(raw_payload)
    return job


def validate_job(job) -> bool:
    return (
        isinstance(job, dict)
        and isinstance(job.get("name"), str)
        and isinstance(job.get("args"), (list, tuple))
    )


def job_priority(job) -> int:
    return int(job.get("priority", 5)) if isinstance(job, dict) else 5
