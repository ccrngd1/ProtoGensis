"""Core Pydantic models for CoherenceProbe."""

from typing import Literal
from pydantic import BaseModel, Field


class AgentOutput(BaseModel):
    """Represents a single output from an agent in the pipeline.

    Attributes:
        agent: Name/identifier of the agent that produced this output
        timestamp: ISO8601 timestamp of when the output was generated
        input: The input provided to the agent
        output: The agent's generated output
        metadata: Optional additional metadata (model version, tokens, etc.)
    """
    agent: str
    timestamp: str
    input: str
    output: str
    metadata: dict = Field(default_factory=dict)


class Claim(BaseModel):
    """An atomic factual claim extracted from agent output.

    Attributes:
        agent: The agent that made this claim
        text: The original claim text as extracted
        normalized: Normalized version (stripped hedging, standardized refs)
        source_sentence: The original sentence from which this was extracted
    """
    agent: str
    text: str
    normalized: str
    source_sentence: str


class ContradictionPair(BaseModel):
    """A detected contradiction between two claims from different agents.

    Attributes:
        claim_a: First claim in the contradiction
        claim_b: Second claim in the contradiction
        contradiction_type: Classification of contradiction type
        confidence: NLI model confidence score (0-1)
        explanation: Optional human-readable explanation
    """
    claim_a: Claim
    claim_b: Claim
    contradiction_type: Literal["logical", "factual", "temporal"]
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str = ""


class CoherenceReport(BaseModel):
    """Complete coherence analysis report for a set of agent outputs.

    Attributes:
        score: Overall coherence score (0.0-1.0, 1.0 = fully coherent)
        agent_scores: Per-agent incoherence contribution scores
        contradictions: List of detected contradiction pairs
        total_claims: Total number of claims extracted across all agents
        total_agents: Number of agents analyzed
        metadata: Additional analysis metadata (timestamps, config, etc.)
    """
    score: float = Field(ge=0.0, le=1.0)
    agent_scores: dict[str, float]
    contradictions: list[ContradictionPair]
    total_claims: int
    total_agents: int
    metadata: dict = Field(default_factory=dict)


class CoherenceConfig(BaseModel):
    """Configuration for coherence checking.

    Attributes:
        model: LiteLLM model string for claim extraction
        threshold: Confidence threshold for flagging contradictions (0-1)
        local: Use fully local mode (no API calls, spaCy extraction)
        nli_model: HuggingFace cross-encoder model for NLI
        embedding_model: Sentence-transformers model for embeddings
        adjudicate_ambiguous: Use LLM to adjudicate ambiguous NLI cases
        verbose: Enable verbose logging output
    """
    model: str = "openai/gpt-4o-mini"
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    local: bool = False
    nli_model: str = "cross-encoder/nli-deberta-v3-large"
    embedding_model: str = "all-MiniLM-L6-v2"
    adjudicate_ambiguous: bool = False
    verbose: bool = False
