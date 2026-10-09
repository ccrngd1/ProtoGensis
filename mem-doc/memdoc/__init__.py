"""MemDoc: a controlled benchmark of agent-written memory (doc vs RAG vs hybrid).

Core is stdlib-only. Optional extras: [bedrock] -> boto3 (live), [vec] -> sqlite-vec.
"""

__version__ = "0.1.0"

MECHANISM_BANNER = (
    "MECHANISM DEMO: scripted agent, hashing embedder, simulated cache. "
    "Not benchmark results."
)
