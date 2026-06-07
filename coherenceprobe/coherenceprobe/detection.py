"""Contradiction detection using NLI and semantic clustering."""

import numpy as np
from typing import Optional
from itertools import combinations

from .models import Claim, ContradictionPair, CoherenceConfig


def detect_contradictions(
    claims: list[Claim],
    config: CoherenceConfig
) -> list[ContradictionPair]:
    """Detect contradictions among claims using NLI and clustering.

    Pipeline:
    1. Embed claims using sentence-transformers
    2. Cluster by topic using cosine similarity
    3. Run pairwise NLI within clusters (cross-agent only)
    4. Classify contradiction types

    Args:
        claims: List of claims to analyze
        config: Configuration with models and thresholds

    Returns:
        List of detected contradiction pairs
    """
    if len(claims) < 2:
        return []

    if config.verbose:
        print(f"Detecting contradictions among {len(claims)} claims...")

    # Step 1: Embed claims
    embeddings = _embed_claims(claims, config)

    # Step 2: Cluster by semantic similarity
    clusters = _cluster_claims(claims, embeddings, similarity_threshold=0.6)

    if config.verbose:
        print(f"Formed {len(clusters)} semantic clusters")

    # Step 3: Detect contradictions within clusters
    contradictions = []
    nli_model = _load_nli_model(config)

    for cluster in clusters:
        if len(cluster) < 2:
            continue

        # Only compare claims from different agents
        cross_agent_pairs = [
            (claims[i], claims[j])
            for i, j in combinations(cluster, 2)
            if claims[i].agent != claims[j].agent
        ]

        if config.verbose and cross_agent_pairs:
            print(f"Checking {len(cross_agent_pairs)} cross-agent pairs in cluster")

        for claim_a, claim_b in cross_agent_pairs:
            contradiction = _check_contradiction_nli(
                claim_a, claim_b, nli_model, config
            )
            if contradiction:
                contradictions.append(contradiction)

    if config.verbose:
        print(f"Found {len(contradictions)} contradictions")

    return contradictions


def _embed_claims(claims: list[Claim], config: CoherenceConfig) -> np.ndarray:
    """Embed claims using sentence-transformers.

    Args:
        claims: List of claims to embed
        config: Configuration with embedding model name

    Returns:
        Numpy array of shape (num_claims, embedding_dim)
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise ImportError(
            "sentence-transformers is required. "
            "Install with: pip install sentence-transformers"
        )

    model = SentenceTransformer(config.embedding_model)

    # Use normalized claims for embedding
    claim_texts = [claim.normalized for claim in claims]
    embeddings = model.encode(claim_texts, convert_to_numpy=True, show_progress_bar=False)

    return embeddings


def _cluster_claims(
    claims: list[Claim],
    embeddings: np.ndarray,
    similarity_threshold: float = 0.6
) -> list[list[int]]:
    """Cluster claims by semantic similarity using cosine similarity.

    Args:
        claims: List of claims
        embeddings: Claim embeddings
        similarity_threshold: Minimum cosine similarity to be in same cluster

    Returns:
        List of clusters, where each cluster is a list of claim indices
    """
    from sklearn.metrics.pairwise import cosine_similarity

    # Compute pairwise similarities
    similarities = cosine_similarity(embeddings)

    # Simple clustering: group claims that are similar to each other
    n_claims = len(claims)
    assigned = set()
    clusters = []

    for i in range(n_claims):
        if i in assigned:
            continue

        # Start new cluster with claim i
        cluster = [i]
        assigned.add(i)

        # Find similar claims not yet assigned
        for j in range(i + 1, n_claims):
            if j not in assigned and similarities[i, j] >= similarity_threshold:
                cluster.append(j)
                assigned.add(j)

        clusters.append(cluster)

    # Add any remaining unassigned claims as singleton clusters
    for i in range(n_claims):
        if i not in assigned:
            clusters.append([i])

    return clusters


def _load_nli_model(config: CoherenceConfig):
    """Load the NLI cross-encoder model.

    Args:
        config: Configuration with NLI model name

    Returns:
        Loaded cross-encoder model
    """
    try:
        from sentence_transformers import CrossEncoder
    except ImportError:
        raise ImportError(
            "sentence-transformers is required. "
            "Install with: pip install sentence-transformers"
        )

    model = CrossEncoder(config.nli_model)
    return model


def _check_contradiction_nli(
    claim_a: Claim,
    claim_b: Claim,
    nli_model,
    config: CoherenceConfig
) -> Optional[ContradictionPair]:
    """Check if two claims contradict using NLI model.

    Args:
        claim_a: First claim
        claim_b: Second claim
        nli_model: Cross-encoder NLI model
        config: Configuration with threshold

    Returns:
        ContradictionPair if contradiction detected, None otherwise
    """
    # Run NLI
    scores = nli_model.predict([(claim_a.normalized, claim_b.normalized)])

    # scores is a 3-element array: [contradiction, entailment, neutral]
    # for cross-encoder/nli-deberta-v3-large, the order is:
    # [contradiction_score, entailment_score, neutral_score]
    # The cross-encoder may return raw logits; apply softmax to get probabilities
    import numpy as np
    raw = np.array([scores[0][0], scores[0][1], scores[0][2]], dtype=float)
    exp_raw = np.exp(raw - raw.max())  # numerically stable softmax
    probs = exp_raw / exp_raw.sum()
    contradiction_score = float(probs[0])
    entailment_score = float(probs[1])
    neutral_score = float(probs[2])

    # Check if contradiction score exceeds threshold
    if contradiction_score >= config.threshold:
        # Classify contradiction type
        contradiction_type = _classify_contradiction_type(claim_a, claim_b)

        # Generate explanation if requested
        explanation = ""
        if config.adjudicate_ambiguous and neutral_score > 0.3:
            explanation = _generate_explanation_llm(claim_a, claim_b, config)

        return ContradictionPair(
            claim_a=claim_a,
            claim_b=claim_b,
            contradiction_type=contradiction_type,
            confidence=contradiction_score,
            explanation=explanation
        )

    return None


def _classify_contradiction_type(claim_a: Claim, claim_b: Claim) -> str:
    """Classify the type of contradiction between two claims.

    Args:
        claim_a: First claim
        claim_b: Second claim

    Returns:
        One of: "logical", "factual", "temporal"
    """
    text_a = claim_a.normalized.lower()
    text_b = claim_b.normalized.lower()

    # Check for logical contradictions (negation patterns)
    negation_words = ["not", "no", "never", "none", "isn't", "aren't", "won't", "can't", "don't", "doesn't"]
    has_negation_a = any(word in text_a for word in negation_words)
    has_negation_b = any(word in text_b for word in negation_words)

    # If one has negation and they're otherwise similar, it's logical
    if has_negation_a != has_negation_b:
        return "logical"

    # Check for temporal contradictions
    temporal_words = ["before", "after", "when", "while", "during", "until", "since",
                     "first", "then", "next", "finally", "previously", "later"]
    has_temporal_a = any(word in text_a for word in temporal_words)
    has_temporal_b = any(word in text_b for word in temporal_words)

    if has_temporal_a or has_temporal_b:
        return "temporal"

    # Default to factual
    return "factual"


def _generate_explanation_llm(
    claim_a: Claim,
    claim_b: Claim,
    config: CoherenceConfig
) -> str:
    """Generate human-readable explanation for contradiction using LLM.

    Args:
        claim_a: First claim
        claim_b: Second claim
        config: Configuration with LLM model

    Returns:
        Explanation string
    """
    try:
        import litellm

        prompt = f"""Two claims from different AI agents appear to contradict each other. Explain the contradiction in one sentence.

Claim 1 (from {claim_a.agent}): {claim_a.text}
Claim 2 (from {claim_b.agent}): {claim_b.text}

Explanation:"""

        response = litellm.completion(
            model=config.model,
            messages=[
                {"role": "system", "content": "You are an expert at analyzing logical contradictions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=100,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        if config.verbose:
            print(f"Failed to generate explanation: {e}")
        return ""


async def adetect_contradictions(
    claims: list[Claim],
    config: CoherenceConfig
) -> list[ContradictionPair]:
    """Async version of detect_contradictions.

    Args:
        claims: List of claims to analyze
        config: Configuration

    Returns:
        List of detected contradiction pairs
    """
    # For now, wrap sync version
    # In production, could parallelize NLI checks
    return detect_contradictions(claims, config)
