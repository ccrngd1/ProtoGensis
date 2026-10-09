"""Memory backends (arms). Registry maps arm id -> class."""

from .base import ContextParts, MemoryBackend, StoreSnapshot, ToolSpec, TurnInjection, WriteReport  # noqa: F401


def registry():
    """arm id -> backend class, importing lazily to keep module load light."""
    from .none import NoneBackend
    from .oracle import OracleBackend
    from .doc_full import DocFullBackend
    from .doc_catalog import DocCatalogBackend
    from .rag_extract import RagExtractBackend, RagNaiveBackend
    from .hybrid_tiered import HybridTieredBackend, HybridTieredBgBackend
    from .transcript_grep import TranscriptGrepBackend

    return {
        "a0": NoneBackend,
        "astar": OracleBackend,
        "a1": DocFullBackend,
        "a2": DocCatalogBackend,
        "a3": RagNaiveBackend,
        "a4": RagExtractBackend,
        "a5": HybridTieredBackend,
        "a5bg": HybridTieredBgBackend,
        "a6": TranscriptGrepBackend,
    }


MVP_ARMS = ("a0", "astar", "a1", "a2", "a4", "a5", "a6")
SHOULD_SHIP_ARMS = ("a3", "a5bg")
