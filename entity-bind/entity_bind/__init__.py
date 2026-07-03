"""
EntityBind - Entity Binding Failure Detection for Tool-Augmented Agents

Middleware to catch wrong-entity actions: right tool, wrong target.
Based on "Entity Binding Failures in Tool-Augmented Agents" (arXiv 2606.30531).
"""

__version__ = "0.1.0"

# Core API
from .catalog import (
    Catalog,
    DynamicCatalog,
    Entity,
    EntityType,
    Precondition,
    RiskLevel,
    SQLiteCatalog,
    StaticCatalog,
    ThresholdConfig,
    ToolSpec,
    create_catalog,
)
from .core import (
    BindingResult,
    EntityGate,
    EntityResolver,
    GateDecision,
    GateResult,
    create_resolver,
    gate,
)
from .provenance import (
    JSONLProvenanceStore,
    ProvenanceRecord,
    ProvenanceStore,
    SQLiteProvenanceStore,
    create_provenance_store,
)
from .scoring import RapidFuzzScorer

# Optional adapters
try:
    from .adapters import OpenAIEntityBind, EntityBoundToolRegistry
    _HAS_ADAPTERS = True
except ImportError:
    _HAS_ADAPTERS = False

# Optional bench
try:
    from .bench import BenchScorer, EntityBindHarness, Task, TaskResult, run_benchmark
    _HAS_BENCH = True
except ImportError:
    _HAS_BENCH = False


__all__ = [
    # Core
    "gate",
    "EntityGate",
    "GateDecision",
    "GateResult",
    "EntityResolver",
    "BindingResult",
    "create_resolver",
    # Catalog
    "Catalog",
    "StaticCatalog",
    "SQLiteCatalog",
    "DynamicCatalog",
    "create_catalog",
    "Entity",
    "EntityType",
    "ToolSpec",
    "Precondition",
    "RiskLevel",
    "ThresholdConfig",
    # Scoring
    "RapidFuzzScorer",
    # Provenance
    "ProvenanceStore",
    "JSONLProvenanceStore",
    "SQLiteProvenanceStore",
    "ProvenanceRecord",
    "create_provenance_store",
]

# Conditionally add adapters
if _HAS_ADAPTERS:
    __all__.extend(["OpenAIEntityBind", "EntityBoundToolRegistry"])

# Conditionally add bench
if _HAS_BENCH:
    __all__.extend(["BenchScorer", "EntityBindHarness", "Task", "TaskResult", "run_benchmark"])
