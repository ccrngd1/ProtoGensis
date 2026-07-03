"""
Entity Binding Resolver

Implements Algorithm 1 from the paper:
1. Candidate retrieval (high recall)
2. Scoring (weighted blend)
3. Twin-test gate (tau absolute + delta margin)
4. Clarification generation

This is the core disambiguation logic.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from entity_bind.catalog.base import Catalog
from entity_bind.catalog.schema import Entity, RiskLevel, ThresholdConfig
from entity_bind.scoring.rapidfuzz_scorer import RapidFuzzScorer


@dataclass
class BindingResult:
    """
    Result of entity binding resolution.

    Represents the outcome of attempting to bind a mention to an entity.
    """

    # Resolution outcome
    resolved: bool  # True if binding is confident enough to act
    mention: str  # Original mention from tool args
    entity: Optional[Entity] = None  # Resolved entity (if resolved)
    confidence: float = 0.0  # Top candidate score

    # Candidates and scores
    candidates: List[Tuple[Entity, float]] = None  # All scored candidates
    runner_up: Optional[Entity] = None  # Second-best candidate
    runner_up_score: float = 0.0  # Second-best score
    margin: float = 0.0  # confidence - runner_up_score

    # Evidence
    matched_fields: List[str] = None  # Fields that matched (for provenance)
    clarification: Optional[str] = None  # Clarification question (if unresolved)

    # Thresholds applied
    tau: float = 0.0  # Absolute confidence threshold
    delta: float = 0.0  # Margin threshold
    passed_tau: bool = False  # Did it pass absolute threshold?
    passed_delta: bool = False  # Did it pass margin threshold?

    def __post_init__(self):
        if self.candidates is None:
            self.candidates = []
        if self.matched_fields is None:
            self.matched_fields = []

    @property
    def top_candidates(self) -> List[Tuple[Entity, float]]:
        """Get top 5 candidates for display."""
        return self.candidates[:5] if self.candidates else []


class EntityResolver:
    """
    Entity binding resolver with confidence gating.

    Resolves natural-language entity mentions to canonical catalog IDs,
    applying the twin-test gate (tau/delta) to decide ACT vs CLARIFY.
    """

    def __init__(
        self,
        catalog: Catalog,
        scorer: Optional[RapidFuzzScorer] = None,
        thresholds: Optional[Dict[RiskLevel, ThresholdConfig]] = None
    ):
        """
        Initialize resolver.

        Args:
            catalog: Entity catalog for lookup
            scorer: Entity scorer (defaults to RapidFuzzScorer)
            thresholds: Threshold configs per risk level (defaults to paper values)
        """
        self.catalog = catalog
        self.scorer = scorer or RapidFuzzScorer()
        self.thresholds = thresholds or ThresholdConfig.defaults()

    def resolve(
        self,
        mention: str,
        expected_type: Optional[str] = None,
        risk: RiskLevel = RiskLevel.MEDIUM,
        context: Optional[Dict] = None
    ) -> BindingResult:
        """
        Resolve a single entity mention.

        Args:
            mention: Entity mention from tool args (e.g., "Alex", "launch plan")
            expected_type: Expected entity type (person, document, etc.)
            risk: Risk level for threshold selection
            context: Additional context (owner, email, timestamp, etc.)

        Returns:
            BindingResult with resolution outcome
        """
        context = context or {}
        if expected_type:
            context['expected_type'] = expected_type

        # 1. Retrieve candidates (high recall)
        candidates_pool = self.catalog.find_by_type(expected_type) if expected_type else self.catalog.all()
        candidates = self.scorer.retrieve_candidates(
            mention,
            candidates_pool,
            limit=20,
            threshold=0.40  # Low threshold for recall
        )

        # 2. Re-score with full context
        scored_candidates = []
        for entity, _ in candidates:
            score = self.scorer.score(mention, entity, context)
            scored_candidates.append((entity, score))

        # Sort by score descending
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # 3. Extract top candidate and runner-up
        if not scored_candidates:
            # No candidates found
            return BindingResult(
                resolved=False,
                mention=mention,
                clarification=self._generate_clarification(mention, [], expected_type)
            )

        top_entity, top_score = scored_candidates[0]
        runner_up_entity = scored_candidates[1][0] if len(scored_candidates) > 1 else None
        runner_up_score = scored_candidates[1][1] if len(scored_candidates) > 1 else 0.0
        margin = top_score - runner_up_score

        # 4. Apply twin-test gate (tau + delta)
        threshold_config = self.thresholds[risk]
        tau = threshold_config.tau
        delta = threshold_config.delta

        passed_tau = top_score >= tau
        passed_delta = margin >= delta
        resolved = passed_tau and passed_delta

        # 5. Get matched fields for provenance
        matched_fields = self.scorer.get_matched_fields(mention, top_entity, context)

        # 6. Generate clarification if unresolved
        clarification = None
        if not resolved:
            clarification = self._generate_clarification(
                mention,
                scored_candidates[:5],  # Top 5 for clarification
                expected_type,
                failed_tau=not passed_tau,
                failed_delta=not passed_delta
            )

        return BindingResult(
            resolved=resolved,
            mention=mention,
            entity=top_entity if resolved else None,
            confidence=top_score,
            candidates=scored_candidates,
            runner_up=runner_up_entity,
            runner_up_score=runner_up_score,
            margin=margin,
            matched_fields=matched_fields,
            clarification=clarification,
            tau=tau,
            delta=delta,
            passed_tau=passed_tau,
            passed_delta=passed_delta
        )

    def resolve_many(
        self,
        mentions: Dict[str, str],
        expected_types: Optional[Dict[str, str]] = None,
        risk: RiskLevel = RiskLevel.MEDIUM,
        context: Optional[Dict] = None
    ) -> Dict[str, BindingResult]:
        """
        Resolve multiple entity mentions.

        Args:
            mentions: {slot: mention} mapping (e.g., {"recipient": "Alex", "document": "launch plan"})
            expected_types: {slot: entity_type} mapping
            risk: Risk level for threshold selection
            context: Additional context

        Returns:
            {slot: BindingResult} mapping
        """
        expected_types = expected_types or {}
        results = {}

        for slot, mention in mentions.items():
            expected_type = expected_types.get(slot)
            results[slot] = self.resolve(
                mention,
                expected_type=expected_type,
                risk=risk,
                context=context
            )

        return results

    def all_resolved(self, results: Dict[str, BindingResult]) -> bool:
        """
        Check if all required mentions resolved successfully.

        Used for the action gate: execute iff all slots resolved.
        """
        return all(r.resolved for r in results.values())

    def _generate_clarification(
        self,
        mention: str,
        candidates: List[Tuple[Entity, float]],
        expected_type: Optional[str],
        failed_tau: bool = False,
        failed_delta: bool = False
    ) -> str:
        """
        Generate a grounded clarification question.

        NOT generic "please clarify" - specific, actionable.
        Examples:
        - "Do you mean Alex Chen from the launch team or Alex Kumar from customer success?"
        - "Multiple 'Launch Plan' documents found. Did you mean the latest internal plan or the customer update?"
        """
        if not candidates:
            # No candidates found
            type_str = f" ({expected_type})" if expected_type else ""
            return f"Could not find any entity matching '{mention}'{type_str}. Please provide more details or the exact ID."

        if len(candidates) == 1 and failed_tau:
            # Single weak match
            entity = candidates[0][0]
            return f"Found a weak match for '{mention}': {entity.display_name}. Is this correct?"

        if len(candidates) >= 2 and failed_delta:
            # Ambiguous - multiple strong candidates
            top_two = candidates[:2]
            entity1, score1 = top_two[0]
            entity2, score2 = top_two[1]

            # Generate distinguishing question
            distinguishing_info = self._get_distinguishing_info(entity1, entity2)

            if distinguishing_info:
                return (
                    f"Multiple entities match '{mention}'. Please clarify: "
                    f"Do you mean {entity1.display_name} ({distinguishing_info[0]}) "
                    f"or {entity2.display_name} ({distinguishing_info[1]})?"
                )
            else:
                return (
                    f"Multiple entities match '{mention}': "
                    f"{entity1.display_name} or {entity2.display_name}. "
                    f"Please clarify which one."
                )

        # Generic fallback
        candidate_names = ", ".join([e.display_name for e, _ in candidates[:3]])
        return f"Multiple matches found for '{mention}': {candidate_names}. Please clarify."

    def _get_distinguishing_info(
        self,
        entity1: Entity,
        entity2: Entity
    ) -> Optional[Tuple[str, str]]:
        """
        Find distinguishing information between two entities.

        Returns:
            (info1, info2) tuple with distinguishing details, or None
        """
        # Email
        if entity1.email and entity2.email and entity1.email != entity2.email:
            return (entity1.email, entity2.email)

        # Owner
        if entity1.owner and entity2.owner and entity1.owner != entity2.owner:
            return (f"owner: {entity1.owner}", f"owner: {entity2.owner}")

        # System of origin
        if entity1.system_of_origin and entity2.system_of_origin and entity1.system_of_origin != entity2.system_of_origin:
            return (f"from {entity1.system_of_origin}", f"from {entity2.system_of_origin}")

        # Time (calendar events)
        if entity1.time and entity2.time and entity1.time != entity2.time:
            return (f"at {entity1.time}", f"at {entity2.time}")

        # Metadata snippet
        if entity1.metadata and entity2.metadata:
            meta1 = entity1.metadata[:50] + "..." if len(entity1.metadata) > 50 else entity1.metadata
            meta2 = entity2.metadata[:50] + "..." if len(entity2.metadata) > 50 else entity2.metadata
            return (meta1, meta2)

        return None


# ============================================================================
# Convenience Functions
# ============================================================================


def create_resolver(
    catalog: Catalog,
    scorer: Optional[RapidFuzzScorer] = None,
    tau: Optional[Dict[RiskLevel, float]] = None,
    delta: Optional[Dict[RiskLevel, float]] = None
) -> EntityResolver:
    """
    Factory function to create a resolver with custom thresholds.

    Args:
        catalog: Entity catalog
        scorer: Entity scorer (defaults to RapidFuzzScorer)
        tau: {RiskLevel: tau} mapping (absolute confidence)
        delta: {RiskLevel: delta} mapping (margin)

    Returns:
        EntityResolver instance
    """
    thresholds = None
    if tau or delta:
        defaults = ThresholdConfig.defaults()
        thresholds = {}
        for risk in RiskLevel:
            t = tau.get(risk, defaults[risk].tau) if tau else defaults[risk].tau
            d = delta.get(risk, defaults[risk].delta) if delta else defaults[risk].delta
            thresholds[risk] = ThresholdConfig(tau=t, delta=d)

    return EntityResolver(
        catalog=catalog,
        scorer=scorer,
        thresholds=thresholds
    )
