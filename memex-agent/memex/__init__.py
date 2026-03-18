"""
Memex — Indexed Experience Memory for Agents
============================================

Two core agent tools:
- compress_experience(content, index_key, context=None)
- read_experience(index_key)
"""

from .store import ExperienceStore
from .manifest import IndexManifest
from .compress import CompressionEngine
from .retrieve import RetrievalEngine
from .tools import compress_experience, read_experience
from .triggers import ContextTriggers

__version__ = "0.1.0"

__all__ = [
    "ExperienceStore",
    "IndexManifest",
    "CompressionEngine",
    "RetrievalEngine",
    "compress_experience",
    "read_experience",
    "ContextTriggers",
]
