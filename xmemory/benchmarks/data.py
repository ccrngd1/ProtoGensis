"""
Benchmark data: generate sample conversation histories.

Generates 100+ synthetic messages across multiple sessions covering
different topics, suitable for testing xMemory's retrieval quality.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import List

from xmemory.models import Message


# ---------------------------------------------------------------------------
# Synthetic conversation templates
# ---------------------------------------------------------------------------

_SESSION_TEMPLATES = {
    "project_planning": [
        "We need to decide on the tech stack for the new API. I'm thinking FastAPI.",
        "FastAPI makes sense. Should we use PostgreSQL or SQLite for the database?",
        "Let's go with PostgreSQL for production. SQLite for local dev.",
        "Agreed. What about authentication? JWT or sessions?",
        "JWT is stateless, easier to scale. Let's use JWT with a 24h expiry.",
        "We should also add rate limiting from day one. 100 requests/minute per user.",
        "Good call. What's the timeline? Can we hit the Q3 deadline?",
        "If we start this week, we can have the MVP in 6 weeks.",
        "That's tight. Let's prioritize the core endpoints and cut the analytics dashboard.",
        "Agreed. Core CRUD + auth first, analytics in v2.",
        "Who's taking the DB schema? I can do the API routes.",
        "I'll take the schema. Alice can handle auth, Bob does the routes.",
        "Let's do daily standups at 9am until the MVP ships.",
        "Works for me. Should we use GitHub Projects or Jira for tracking?",
        "GitHub Projects — we're already on GitHub, keep it simple.",
    ],
    "debugging_session": [
        "The API is returning 500 errors on the /users endpoint. Anyone looking at it?",
        "I'm on it. The logs show a NullPointerException in the auth middleware.",
        "That middleware was updated yesterday. Was it tested?",
        "It was tested in isolation but not end-to-end. My mistake.",
        "No worries. What's the fix?",
        "The token decoder assumes the 'sub' field is always present, but legacy tokens don't have it.",
        "So we need a fallback for the 'sub' field.",
        "Right. Defaulting to the 'uid' field if 'sub' is missing.",
        "That makes sense. Any other fields we might be missing?",
        "Checked all fields. Only 'sub' was the issue.",
        "Good. Can you write a regression test for this?",
        "Already done. Adding test_legacy_token_auth to the test suite.",
        "Great. When can you deploy the fix?",
        "Deploying to staging now. Production in 2 hours after staging tests pass.",
        "Thanks. I'll monitor the error rates after deployment.",
        "Error rates back to normal. Fix confirmed.",
    ],
    "architecture_review": [
        "Let's review the current architecture before scaling further.",
        "The monolith is becoming a bottleneck. We get 10k RPS at peak.",
        "Which services are hitting limits? Auth? API? DB?",
        "DB is the bottleneck. Connection pool is exhausted at peak.",
        "We could add read replicas for the DB.",
        "That would help for reads. But 80% of our traffic is writes.",
        "Then we need to look at write sharding or a queue-based approach.",
        "A message queue would decouple the API from the DB writes.",
        "Redis for the queue? Or Kafka?",
        "Redis is simpler to operate. Kafka if we need replay capabilities.",
        "We need replay for audit logging. Kafka it is.",
        "OK. So the plan is: Kafka for writes, read replicas for reads.",
        "And we should add connection pooling via PgBouncer.",
        "Good point. PgBouncer can handle 10x our current connection count.",
        "Timeline for this migration? It's a big change.",
        "Phase 1 is PgBouncer — 1 week. Phase 2 is read replicas — 2 weeks. Kafka — 1 month.",
    ],
    "product_feedback": [
        "User research results are in. Top complaint: the dashboard is too slow.",
        "How slow are we talking?",
        "P95 load time is 8 seconds. Users expect under 2.",
        "That's bad. What's causing it?",
        "Three N+1 queries in the analytics module.",
        "We knew about those. They got deprioritized.",
        "They're now a P1. Users are churning because of it.",
        "I'll fix the N+1s this sprint. Should reduce load time to under 1 second.",
        "Great. Second complaint: users can't find the export feature.",
        "It's buried in Settings > Data > Export. That's three clicks deep.",
        "Move it to the main toolbar. One-click access.",
        "Done. Any other feedback?",
        "Users want dark mode. 40% of survey respondents asked for it.",
        "Dark mode is on the roadmap for Q4. Let's not push it up.",
        "Fair. The performance fix is more impactful anyway.",
        "Agreed. Let's also add a loading indicator while the dashboard fetches data.",
    ],
    "team_retrospective": [
        "What went well this sprint?",
        "We shipped the authentication overhaul ahead of schedule.",
        "Good point. The new JWT implementation is much cleaner.",
        "Communication was better too. The daily standups helped.",
        "What could we improve?",
        "We had too many interruptions. People were pinging each other constantly.",
        "We should define focus hours — no interruptions from 10am to 12pm.",
        "I like that. Also, our PR review turnaround is too slow. Average 2 days.",
        "We need a rule: all PRs reviewed within 24 hours.",
        "Agreed. And the person with the oldest PR takes priority.",
        "What should we start doing?",
        "Pair programming for complex features. Reduces bugs and spreads knowledge.",
        "I'd like to try that. Who wants to pair on the Kafka integration?",
        "I'll pair with you on Kafka.",
        "Great. Let's also start doing architecture decision records (ADRs).",
        "ADRs are a great idea. We keep making the same decisions because we don't document them.",
    ],
}


def generate_messages(
    n_sessions: int = 5,
    session_prefix: str = "session",
    start_time: datetime | None = None,
) -> List[Message]:
    """
    Generate a synthetic conversation history.

    Args:
        n_sessions:    Number of conversation sessions to generate.
        session_prefix: Prefix for session IDs.
        start_time:    Start timestamp (default: 2025-01-01 09:00).

    Returns:
        List of Message objects (not yet persisted).
    """
    if start_time is None:
        start_time = datetime(2025, 1, 1, 9, 0, 0)

    session_keys = list(_SESSION_TEMPLATES.keys())
    messages: List[Message] = []
    current_time = start_time

    for i in range(n_sessions):
        session_id = f"{session_prefix}_{i+1:03d}"
        template_key = session_keys[i % len(session_keys)]
        template = _SESSION_TEMPLATES[template_key]

        for content in template:
            msg = Message(
                session_id=session_id,
                content=content,
                timestamp=current_time,
            )
            messages.append(msg)
            # 1-5 minute gaps between messages
            current_time += timedelta(minutes=random.randint(1, 5))

        # 1-2 hour gap between sessions
        current_time += timedelta(hours=random.randint(1, 2))

    return messages


def get_benchmark_queries() -> List[str]:
    """Return representative queries for benchmarking retrieval."""
    return [
        "What decisions were made about the database?",
        "What is the authentication approach?",
        "What are the performance problems and fixes?",
        "What did the team agree to do about code review?",
        "What is the scaling plan for the system?",
        "What user complaints were raised?",
        "Who is responsible for what tasks?",
        "What is the timeline for the MVP?",
        "What testing approach was discussed?",
        "What architectural changes are planned?",
    ]
