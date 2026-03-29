"""
Diversity Measurement - Quantify how different persona responses really are

Metrics:
1. Semantic similarity (cosine similarity on embeddings or lexical overlap)
2. Conclusion agreement (do they reach the same recommendation?)
3. Reasoning path overlap (shared concepts and arguments)
4. Overall diversity score
"""
import re
from typing import List, Dict, Tuple
from collections import Counter
import math
from dataclasses import dataclass, asdict


@dataclass
class DiversityMetrics:
    """Diversity measurements for a set of responses"""
    avg_pairwise_similarity: float
    diversity_score: float  # 1 - similarity (higher = more diverse)
    conclusion_agreement: float  # 0-1, how much personas agree on recommendation
    lexical_overlap: float  # 0-1, shared vocabulary
    unique_concepts_per_persona: Dict[str, int]
    pairwise_similarities: Dict[str, float]
    analysis: str


def normalize_text(text: str) -> str:
    """Normalize text for comparison"""
    # Lowercase
    text = text.lower()
    # Remove special chars but keep spaces
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_words(text: str) -> List[str]:
    """Extract words from text, excluding stop words"""
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
        'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this',
        'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
    }

    normalized = normalize_text(text)
    words = normalized.split()
    return [w for w in words if w not in stop_words and len(w) > 2]


def cosine_similarity_lexical(text1: str, text2: str) -> float:
    """
    Calculate cosine similarity based on word frequency vectors

    This is a simple lexical approach that works without embeddings.
    """
    words1 = extract_words(text1)
    words2 = extract_words(text2)

    # Create word frequency vectors
    counter1 = Counter(words1)
    counter2 = Counter(words2)

    # Get all unique words
    all_words = set(counter1.keys()) | set(counter2.keys())

    if not all_words:
        return 0.0

    # Create vectors
    vec1 = [counter1.get(word, 0) for word in all_words]
    vec2 = [counter2.get(word, 0) for word in all_words]

    # Calculate cosine similarity
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)


def jaccard_similarity(text1: str, text2: str) -> float:
    """Calculate Jaccard similarity (intersection over union of word sets)"""
    words1 = set(extract_words(text1))
    words2 = set(extract_words(text2))

    if not words1 and not words2:
        return 1.0
    if not words1 or not words2:
        return 0.0

    intersection = len(words1 & words2)
    union = len(words1 | words2)

    return intersection / union if union > 0 else 0.0


def extract_conclusion_keywords(text: str) -> set:
    """
    Extract keywords that suggest a conclusion or recommendation

    Looks for phrases near decision-making language.
    """
    conclusion_markers = [
        'recommend', 'should', 'suggest', 'propose', 'conclusion',
        'therefore', 'thus', 'ultimately', 'best approach', 'go with',
        'choose', 'select', 'decision', 'verdict', 'answer is'
    ]

    text_lower = text.lower()
    conclusions = []

    # Find sentences with conclusion markers
    sentences = re.split(r'[.!?]\s+', text)
    for sentence in sentences:
        if any(marker in sentence.lower() for marker in conclusion_markers):
            conclusions.append(sentence)

    # Extract key terms from conclusion sentences
    conclusion_text = ' '.join(conclusions)
    return set(extract_words(conclusion_text))


def measure_conclusion_agreement(responses: List[str]) -> float:
    """
    Measure how much the conclusions agree

    Returns 0-1 score where 1 = identical conclusions, 0 = completely different
    """
    if len(responses) < 2:
        return 1.0

    # Extract conclusion keywords from each response
    conclusion_sets = [extract_conclusion_keywords(r) for r in responses]

    # Calculate pairwise Jaccard similarity between conclusions
    similarities = []
    for i in range(len(conclusion_sets)):
        for j in range(i + 1, len(conclusion_sets)):
            set1, set2 = conclusion_sets[i], conclusion_sets[j]

            if not set1 and not set2:
                similarities.append(1.0)
            elif not set1 or not set2:
                similarities.append(0.0)
            else:
                intersection = len(set1 & set2)
                union = len(set1 | set2)
                similarities.append(intersection / union if union > 0 else 0.0)

    return sum(similarities) / len(similarities) if similarities else 0.0


def analyze_unique_concepts(responses: List[Dict]) -> Dict[str, int]:
    """
    Count unique concepts (words) contributed by each persona

    A concept is "unique" if it appears in one persona's response but not others.
    """
    persona_words = {}

    # Extract words for each persona
    for response in responses:
        persona_id = response['persona_id']
        words = set(extract_words(response['response_text']))
        persona_words[persona_id] = words

    # Find unique contributions
    unique_counts = {}
    for persona_id, words in persona_words.items():
        # Words that appear in this persona but not in others
        other_words = set()
        for other_id, other_words_set in persona_words.items():
            if other_id != persona_id:
                other_words.update(other_words_set)

        unique = words - other_words
        unique_counts[persona_id] = len(unique)

    return unique_counts


def calculate_pairwise_similarities(responses: List[Dict]) -> Dict[str, float]:
    """Calculate similarity between all pairs of responses"""
    similarities = {}

    for i in range(len(responses)):
        for j in range(i + 1, len(responses)):
            persona1 = responses[i]['persona_id']
            persona2 = responses[j]['persona_id']
            text1 = responses[i]['response_text']
            text2 = responses[j]['response_text']

            # Use both cosine and Jaccard, average them
            cos_sim = cosine_similarity_lexical(text1, text2)
            jac_sim = jaccard_similarity(text1, text2)
            avg_sim = (cos_sim + jac_sim) / 2

            pair_key = f"{persona1} vs {persona2}"
            similarities[pair_key] = avg_sim

    return similarities


def generate_diversity_analysis(metrics: DiversityMetrics) -> str:
    """Generate human-readable analysis of diversity metrics"""

    diversity_level = "low"
    if metrics.diversity_score > 0.7:
        diversity_level = "high"
    elif metrics.diversity_score > 0.4:
        diversity_level = "moderate"

    agreement_level = "strong"
    if metrics.conclusion_agreement < 0.3:
        agreement_level = "weak"
    elif metrics.conclusion_agreement < 0.6:
        agreement_level = "moderate"

    analysis = f"""**Diversity Assessment:**

**Overall Diversity: {diversity_level.upper()}** (score: {metrics.diversity_score:.2f})
- Average pairwise similarity: {metrics.avg_pairwise_similarity:.2f}
- Lower similarity = higher diversity

**Conclusion Agreement: {agreement_level.upper()}** ({metrics.conclusion_agreement:.2f})
- {agreement_level.title()} agreement on recommendations across personas

**Interpretation:**
"""

    if metrics.diversity_score > 0.6:
        analysis += "- Personas are producing **substantively different** responses with distinct reasoning paths and vocabulary.\n"
    elif metrics.diversity_score > 0.3:
        analysis += "- Personas show **moderate diversity** - some shared concepts but different emphasis and conclusions.\n"
    else:
        analysis += "- Personas are producing **similar responses** - diversity may be more cosmetic than substantive.\n"

    if metrics.conclusion_agreement < 0.4:
        analysis += "- Personas **disagree on recommendations** - this suggests genuine analytical diversity.\n"
    elif metrics.conclusion_agreement > 0.7:
        analysis += "- Personas **converge on similar recommendations** despite different reasoning paths.\n"
    else:
        analysis += "- Personas reach **partially overlapping conclusions** with some divergence.\n"

    # Highlight most unique contributors
    if metrics.unique_concepts_per_persona:
        sorted_unique = sorted(
            metrics.unique_concepts_per_persona.items(),
            key=lambda x: x[1],
            reverse=True
        )
        top_contributor = sorted_unique[0]
        analysis += f"\n**Most unique perspective:** {top_contributor[0]} ({top_contributor[1]} unique concepts)"

    return analysis


def measure_diversity(responses: List[Dict]) -> DiversityMetrics:
    """
    Measure diversity across all persona responses

    Args:
        responses: List of persona response dictionaries from runner

    Returns:
        DiversityMetrics with comprehensive diversity measurements
    """
    if len(responses) < 2:
        return DiversityMetrics(
            avg_pairwise_similarity=0.0,
            diversity_score=1.0,
            conclusion_agreement=1.0,
            lexical_overlap=1.0,
            unique_concepts_per_persona={},
            pairwise_similarities={},
            analysis="Not enough responses to measure diversity (need at least 2)"
        )

    # Calculate pairwise similarities
    pairwise_sims = calculate_pairwise_similarities(responses)
    avg_similarity = sum(pairwise_sims.values()) / len(pairwise_sims) if pairwise_sims else 0.0

    # Diversity is inverse of similarity
    diversity_score = 1.0 - avg_similarity

    # Measure conclusion agreement
    response_texts = [r['response_text'] for r in responses]
    conclusion_agreement = measure_conclusion_agreement(response_texts)

    # Lexical overlap (average Jaccard across all pairs)
    jaccard_sims = []
    for i in range(len(responses)):
        for j in range(i + 1, len(responses)):
            jac = jaccard_similarity(responses[i]['response_text'], responses[j]['response_text'])
            jaccard_sims.append(jac)
    lexical_overlap = sum(jaccard_sims) / len(jaccard_sims) if jaccard_sims else 0.0

    # Unique concept contributions
    unique_concepts = analyze_unique_concepts(responses)

    # Create metrics object
    metrics = DiversityMetrics(
        avg_pairwise_similarity=avg_similarity,
        diversity_score=diversity_score,
        conclusion_agreement=conclusion_agreement,
        lexical_overlap=lexical_overlap,
        unique_concepts_per_persona=unique_concepts,
        pairwise_similarities=pairwise_sims,
        analysis=""  # Will be filled next
    )

    # Generate analysis
    metrics.analysis = generate_diversity_analysis(metrics)

    return metrics


def print_diversity_report(metrics: DiversityMetrics):
    """Print formatted diversity report"""
    print("\n" + "="*60)
    print("DIVERSITY ANALYSIS")
    print("="*60 + "\n")

    print(metrics.analysis)

    print(f"\n{'='*60}")
    print("DETAILED METRICS")
    print("="*60 + "\n")

    print(f"Diversity Score: {metrics.diversity_score:.3f}")
    print(f"Avg Pairwise Similarity: {metrics.avg_pairwise_similarity:.3f}")
    print(f"Conclusion Agreement: {metrics.conclusion_agreement:.3f}")
    print(f"Lexical Overlap: {metrics.lexical_overlap:.3f}")

    print(f"\n{'='*60}")
    print("PAIRWISE SIMILARITIES")
    print("="*60 + "\n")

    for pair, similarity in sorted(metrics.pairwise_similarities.items()):
        print(f"{pair}: {similarity:.3f}")

    print(f"\n{'='*60}")
    print("UNIQUE CONCEPTS PER PERSONA")
    print("="*60 + "\n")

    for persona, count in sorted(
        metrics.unique_concepts_per_persona.items(),
        key=lambda x: x[1],
        reverse=True
    ):
        print(f"{persona}: {count} unique concepts")

    print(f"\n{'='*60}\n")


def main():
    """Demo usage"""
    # Mock responses for testing
    mock_responses = [
        {
            "persona_id": "first_principles",
            "persona_name": "First Principles Thinker",
            "response_text": "From fundamental axioms, authentication requires cryptographic identity verification and secure session management. Building from first principles, we need hash functions, token generation, and secure storage. The question is resource allocation—should we build from axioms or use existing implementations?"
        },
        {
            "persona_id": "domain_expert",
            "persona_name": "Domain Expert",
            "response_text": "Industry best practice for small teams: use Auth0 or Clerk. Historical data shows custom auth takes 2-3x estimated time. Common anti-pattern: underestimating complexity. Recommendation: third-party service with abstraction layer for future flexibility."
        },
        {
            "persona_id": "devils_advocate",
            "persona_name": "Devil's Advocate",
            "response_text": "Arguing against third-party: vendor lock-in risk, pricing scales with growth, outage dependency, customization constraints. If it's truly a solved problem, why are there dozens of competing solutions? Consider building in-house with modern frameworks—may be faster than assumed."
        },
        {
            "persona_id": "creative_solver",
            "persona_name": "Creative Problem Solver",
            "response_text": "What if we reframe: use passwordless authentication (magic links, biometric)? Or hybrid: Auth0 for MVP, design abstraction layer, evaluate after 6 months. Could we learn from gaming industry's approach to persistent sessions? Think of auth as 'identity continuity' rather than 'password checking'."
        }
    ]

    metrics = measure_diversity(mock_responses)
    print_diversity_report(metrics)


if __name__ == "__main__":
    main()
