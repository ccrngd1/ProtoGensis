"""
xMemory — Beyond RAG for Agent Memory

A hierarchical memory retrieval system that organizes agent conversation
history into four levels (messages → episodes → semantics → themes) and
retrieves context through structured top-down traversal instead of flat
vector similarity search.

Reference: arXiv:2602.02007 — "Beyond RAG for Agent Memory: Retrieval by
Decoupling and Aggregation" (ICML 2026)
"""

from xmemory.models import Message, Episode, SemanticNode, Theme, RetrievalResult
from xmemory.schema import init_db
from xmemory.store import MemoryStore
from xmemory.updater import MemoryUpdater
from xmemory.retrieval import MemoryRetriever

__version__ = "0.1.0"
__all__ = [
    "Message",
    "Episode",
    "SemanticNode",
    "Theme",
    "RetrievalResult",
    "init_db",
    "MemoryStore",
    "MemoryUpdater",
    "MemoryRetriever",
]
