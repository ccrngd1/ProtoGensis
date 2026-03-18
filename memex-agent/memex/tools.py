"""
tools.py — High-level agent-callable tools.

These are the two primary entry points for agents:
    compress_experience(content, index_key, context=None) -> str
    read_experience(index_key) -> str

They wrap the CompressionEngine and RetrievalEngine with a simple
functional interface that any agent framework can call.
"""

import os
from typing import Optional

from .store import ExperienceStore
from .manifest import IndexManifest
from .compress import CompressionEngine
from .retrieve import RetrievalEngine
from .utils import validate_index_key

# Default paths for the shared store/manifest.
# Override via environment variables or by constructing your own instances.
_DEFAULT_DB_PATH = os.environ.get("MEMEX_DB_PATH", "memex.db")
_DEFAULT_MANIFEST_PATH = os.environ.get("MEMEX_MANIFEST_PATH", "memex_manifest.json")

# Module-level singletons (lazy-initialised)
_store: Optional[ExperienceStore] = None
_manifest: Optional[IndexManifest] = None
_compressor: Optional[CompressionEngine] = None
_retriever: Optional[RetrievalEngine] = None


def _get_singletons(
    db_path: Optional[str] = None,
    manifest_path: Optional[str] = None,
    bedrock_caller=None,
):
    """Lazy-initialise module-level singletons."""
    global _store, _manifest, _compressor, _retriever
    db = db_path or _DEFAULT_DB_PATH
    mf = manifest_path or _DEFAULT_MANIFEST_PATH

    if _store is None or (db_path and db_path != _DEFAULT_DB_PATH):
        _store = ExperienceStore(db)
    if _manifest is None or (manifest_path and manifest_path != _DEFAULT_MANIFEST_PATH):
        _manifest = IndexManifest(mf)
    if _compressor is None:
        _compressor = CompressionEngine(_store, _manifest, bedrock_caller=bedrock_caller)
    if _retriever is None:
        _retriever = RetrievalEngine(_store, _manifest)

    return _store, _manifest, _compressor, _retriever


def reset_singletons():
    """Reset module-level singletons (useful in tests)."""
    global _store, _manifest, _compressor, _retriever
    _store = _manifest = _compressor = _retriever = None


def compress_experience(
    content: str,
    index_key: str,
    context: Optional[str] = None,
    *,
    db_path: Optional[str] = None,
    manifest_path: Optional[str] = None,
    _bedrock_caller=None,
) -> str:
    """
    Archive full content to SQLite and return a compact indexed summary.

    Args:
        content:    The full verbose content (e.g., a long tool response).
        index_key:  A human-readable index key, e.g. "[research:oauth-libs]".
                    Will be normalised if brackets are missing.
        context:    Optional hint about what this content is about.

    Returns:
        Compact indexed summary string (~100-200 tokens) that should replace
        the original content in the agent's working context.

    Example:
        summary = compress_experience(
            content=long_api_response,
            index_key="[project:api-auth-research]",
            context="OAuth2 library comparison for auth module",
        )
        # summary is now ~150 tokens; the full content is archived at the key
    """
    key = validate_index_key(index_key)
    _, _, compressor, _ = _get_singletons(db_path, manifest_path, _bedrock_caller)
    return compressor.compress(content, key, context)


def read_experience(
    index_key: str,
    *,
    db_path: Optional[str] = None,
    manifest_path: Optional[str] = None,
) -> str:
    """
    Dereference an index key and return the full archived content (lossless).

    Args:
        index_key:  The index key used when the experience was compressed.

    Returns:
        Exact original content that was archived.

    Raises:
        KeyError: If the key has no archived experience.

    Example:
        full_content = read_experience("[project:api-auth-research]")
    """
    key = validate_index_key(index_key)
    _, _, _, retriever = _get_singletons(db_path, manifest_path)
    return retriever.retrieve(key)


def get_memex_stats(
    db_path: Optional[str] = None,
    manifest_path: Optional[str] = None,
) -> dict:
    """Return aggregate stats: total entries, tokens saved, etc."""
    store, manifest, _, _ = _get_singletons(db_path, manifest_path)
    stats = store.stats()
    stats["manifest_entries"] = len(manifest)
    return stats
