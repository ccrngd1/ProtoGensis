"""Coherence scoring and per-agent contribution analysis."""

from collections import defaultdict
from typing import Dict

from .models import Claim, ContradictionPair, CoherenceReport, CoherenceConfig


def compute_coherence_score(
    claims: list[Claim],
    contradictions: list[ContradictionPair],
    config: CoherenceConfig
) -> CoherenceReport:
    """Compute overall coherence score and per-agent contributions.

    The coherence score is calculated as:
        score = 1.0 - (weighted_contradictions / total_claim_pairs_checked)

    Where weighted_contradictions is the sum of confidence scores of all contradictions.

    Args:
        claims: All extracted claims
        contradictions: Detected contradiction pairs
        config: Configuration

    Returns:
        Complete coherence report
    """
    if len(claims) < 2:
        # No contradictions possible with < 2 claims
        return CoherenceReport(
            score=1.0,
            agent_scores={},
            contradictions=[],
            total_claims=len(claims),
            total_agents=len(set(c.agent for c in claims)),
            metadata={"note": "Insufficient claims for analysis"}
        )

    # Count agents and claims per agent
    agents = set(claim.agent for claim in claims)
    claims_by_agent = defaultdict(list)
    for claim in claims:
        claims_by_agent[claim.agent].append(claim)

    # Calculate total possible cross-agent claim pairs
    total_pairs = 0
    for agent_a in agents:
        for agent_b in agents:
            if agent_a < agent_b:  # Avoid double counting
                total_pairs += len(claims_by_agent[agent_a]) * len(claims_by_agent[agent_b])

    if total_pairs == 0:
        # Only one agent, no cross-agent comparisons possible
        return CoherenceReport(
            score=1.0,
            agent_scores={agent: 0.0 for agent in agents},
            contradictions=[],
            total_claims=len(claims),
            total_agents=len(agents),
            metadata={"note": "Only one agent, no cross-agent comparison possible"}
        )

    # Calculate weighted sum of contradictions
    weighted_contradictions = sum(c.confidence for c in contradictions)

    # Compute overall coherence score
    # The more contradictions (and higher confidence), the lower the score
    # We normalize by total_pairs to make score independent of scale
    incoherence_rate = weighted_contradictions / total_pairs
    coherence_score = max(0.0, 1.0 - incoherence_rate)

    # Compute per-agent scores (incoherence contribution)
    agent_scores = _compute_agent_scores(agents, contradictions, total_pairs)

    report = CoherenceReport(
        score=coherence_score,
        agent_scores=agent_scores,
        contradictions=contradictions,
        total_claims=len(claims),
        total_agents=len(agents),
        metadata={
            "total_pairs_checked": total_pairs,
            "weighted_contradictions": weighted_contradictions,
            "claims_by_agent": {agent: len(claims_by_agent[agent]) for agent in agents}
        }
    )

    if config.verbose:
        print(f"Coherence score: {coherence_score:.3f}")
        print(f"Total contradictions: {len(contradictions)}")
        print(f"Agent scores: {agent_scores}")

    return report


def _compute_agent_scores(
    agents: set[str],
    contradictions: list[ContradictionPair],
    total_pairs: int
) -> Dict[str, float]:
    """Compute per-agent incoherence contribution scores.

    Each agent's score represents how much they contribute to overall incoherence,
    weighted by the number of contradictions they're involved in and the confidence
    of those contradictions.

    Args:
        agents: Set of all agent names
        contradictions: Detected contradiction pairs
        total_pairs: Total number of claim pairs checked

    Returns:
        Dict mapping agent name to incoherence score (0.0-1.0)
    """
    # Count weighted contradictions per agent
    agent_contradiction_weights = defaultdict(float)

    for contradiction in contradictions:
        # Both agents in a contradiction share responsibility
        agent_contradiction_weights[contradiction.claim_a.agent] += contradiction.confidence
        agent_contradiction_weights[contradiction.claim_b.agent] += contradiction.confidence

    # Normalize by total possible pairs to get per-agent incoherence scores
    agent_scores = {}
    for agent in agents:
        if total_pairs > 0:
            # Agent's score is their weighted contradiction contribution
            # normalized by total pairs
            agent_scores[agent] = agent_contradiction_weights[agent] / total_pairs
        else:
            agent_scores[agent] = 0.0

    return agent_scores


def rank_agents_by_coherence(report: CoherenceReport) -> list[tuple[str, float]]:
    """Rank agents from most coherent to least coherent.

    Args:
        report: Coherence report with agent scores

    Returns:
        List of (agent_name, coherence_score) tuples, sorted by coherence descending
    """
    # Convert incoherence scores to coherence scores
    agent_coherence = [(agent, 1.0 - score) for agent, score in report.agent_scores.items()]

    # Sort by coherence descending (most coherent first)
    agent_coherence.sort(key=lambda x: x[1], reverse=True)

    return agent_coherence


def get_most_problematic_agent(report: CoherenceReport) -> tuple[str, float] | None:
    """Identify the agent contributing most to incoherence.

    Args:
        report: Coherence report with agent scores

    Returns:
        Tuple of (agent_name, incoherence_score) or None if no agents
    """
    if not report.agent_scores:
        return None

    # Find agent with highest incoherence score
    most_problematic = max(report.agent_scores.items(), key=lambda x: x[1])
    return most_problematic


def summarize_contradictions_by_type(
    contradictions: list[ContradictionPair]
) -> Dict[str, int]:
    """Summarize contradictions by type.

    Args:
        contradictions: List of contradiction pairs

    Returns:
        Dict mapping contradiction type to count
    """
    type_counts = defaultdict(int)
    for contradiction in contradictions:
        type_counts[contradiction.contradiction_type] += 1

    return dict(type_counts)


def get_contradiction_clusters(
    contradictions: list[ContradictionPair]
) -> list[list[ContradictionPair]]:
    """Group contradictions into clusters by shared claims.

    Args:
        contradictions: List of contradiction pairs

    Returns:
        List of contradiction clusters
    """
    if not contradictions:
        return []

    # Build graph of contradictions
    # Nodes are contradictions, edges exist if they share a claim
    clusters = []
    assigned = set()

    for i, contradiction_a in enumerate(contradictions):
        if i in assigned:
            continue

        # Start new cluster
        cluster = [contradiction_a]
        assigned.add(i)

        # Find related contradictions
        for j, contradiction_b in enumerate(contradictions[i+1:], start=i+1):
            if j in assigned:
                continue

            # Check if they share any claims
            claims_a = {contradiction_a.claim_a.text, contradiction_a.claim_b.text}
            claims_b = {contradiction_b.claim_a.text, contradiction_b.claim_b.text}

            if claims_a & claims_b:  # If they share at least one claim
                cluster.append(contradiction_b)
                assigned.add(j)

        clusters.append(cluster)

    return clusters
