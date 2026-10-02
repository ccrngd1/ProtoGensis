"""CoherenceGate: a commit-time coherence harness for multi-agent systems.

An executable spec of the harness in arXiv 2610.02036 ("Global Coherence",
Heng 2026): models propose, an authoritative store holds the distinctions
that matter, and a governed commit decides which proposals change the world.
"""
from .context import AgentContext, ContextAssembler
from .gate import Accept, CommitGate, Reject, Repair
from .monitor import EffectMonitor, Notice
from .owners import Escrow, Invariant, Ledger, Unit, Violation
from .proposal import Proposal
from .runlog import RunLog, StepClock
from .store import ApplyResult, InMemoryStore, SQLiteStore, Store, Versioned
from .topology import Topology

__version__ = "0.1.0"

__all__ = [
    "Accept", "AgentContext", "ApplyResult", "CommitGate", "ContextAssembler",
    "EffectMonitor", "Escrow", "InMemoryStore", "Invariant", "Ledger",
    "Notice", "Proposal", "Reject", "Repair", "RunLog", "SQLiteStore",
    "StepClock", "Store", "Topology", "Unit", "Versioned", "__version__",
]
