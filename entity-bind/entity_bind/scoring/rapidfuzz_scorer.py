"""
RapidFuzz-based Entity Scorer

Default MVP scorer using RapidFuzz for lexical similarity and
jellyfish for phonetic matching. Fast, no ML dependencies.
"""

from typing import Dict, List, Optional, Tuple

import jellyfish
from rapidfuzz import fuzz, process

from entity_bind.catalog.schema import Entity


class RapidFuzzScorer:
    """
    Lexical + phonetic entity scorer using RapidFuzz and jellyfish.

    Scoring strategy:
    1. Lexical similarity (RapidFuzz token_sort_ratio, WRatio)
    2. Phonetic matching (Soundex, Metaphone for name collisions)
    3. Structured signals (type match, owner, recency, email)
    4. Weighted blend → [0, 1] confidence score

    Tuned for recall in candidate retrieval, precision in final gate.
    """

    def __init__(
        self,
        lexical_weight: float = 0.50,
        phonetic_weight: float = 0.15,
        type_weight: float = 0.15,
        structured_weight: float = 0.20,
    ):
        """
        Initialize scorer with feature weights.

        Args:
            lexical_weight: Weight for fuzzy string matching
            phonetic_weight: Weight for phonetic matching (names)
            type_weight: Weight for entity type match
            structured_weight: Weight for structured signals (owner, email, etc.)
        """
        self.lexical_weight = lexical_weight
        self.phonetic_weight = phonetic_weight
        self.type_weight = type_weight
        self.structured_weight = structured_weight

        # Normalize weights
        total = sum([lexical_weight, phonetic_weight, type_weight, structured_weight])
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total}")

    def retrieve_candidates(
        self,
        mention: str,
        candidates: List[Entity],
        limit: int = 10,
        threshold: float = 0.50
    ) -> List[Tuple[Entity, float]]:
        """
        Retrieve top-k candidates using fuzzy matching.

        High-recall retrieval - returns candidates that might match,
        even with low scores. The gate (tau/delta) handles precision.

        Args:
            mention: Entity mention from tool args
            candidates: Pool of candidate entities
            limit: Max candidates to return
            threshold: Minimum fuzzy score (0-1) to include

        Returns:
            List of (entity, raw_score) tuples, sorted by score descending
        """
        if not candidates:
            return []

        # Build searchable strings (name/title + aliases)
        searchable = []
        for entity in candidates:
            for name in entity.all_names:
                searchable.append((name, entity))

        # RapidFuzz extraction with token_sort_ratio (handles word order)
        # Returns: [(text, score, index), ...]
        matches = process.extract(
            mention,
            [s[0] for s in searchable],
            scorer=fuzz.token_sort_ratio,
            limit=limit * 2,  # Over-retrieve for dedup
            score_cutoff=threshold * 100  # RapidFuzz uses 0-100 scale
        )

        # Deduplicate by entity ID and normalize scores
        seen = set()
        results = []
        for text, score, idx in matches:
            _, entity = searchable[idx]
            if entity.id in seen:
                continue
            seen.add(entity.id)
            results.append((entity, score / 100.0))  # Normalize to [0, 1]

            if len(results) >= limit:
                break

        return results

    def score(
        self,
        mention: str,
        entity: Entity,
        context: Optional[Dict[str, any]] = None
    ) -> float:
        """
        Score a single entity against a mention.

        Args:
            mention: Entity mention from tool args
            entity: Candidate entity to score
            context: Optional context (expected_type, owner, timestamp, etc.)

        Returns:
            Confidence score in [0, 1]
        """
        context = context or {}

        # 1. Lexical similarity
        lexical_score = self._lexical_score(mention, entity)

        # 2. Phonetic similarity (for names)
        phonetic_score = self._phonetic_score(mention, entity)

        # 3. Type match
        type_score = self._type_score(entity, context.get('expected_type'))

        # 4. Structured signals
        structured_score = self._structured_score(entity, context)

        # Weighted blend
        final_score = (
            self.lexical_weight * lexical_score +
            self.phonetic_weight * phonetic_score +
            self.type_weight * type_score +
            self.structured_weight * structured_score
        )

        return max(0.0, min(1.0, final_score))

    def score_many(
        self,
        mention: str,
        entities: List[Entity],
        context: Optional[Dict[str, any]] = None
    ) -> List[Tuple[Entity, float]]:
        """
        Score multiple entities against a mention.

        Returns:
            List of (entity, score) tuples, sorted by score descending
        """
        scored = [(e, self.score(mention, e, context)) for e in entities]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def _lexical_score(self, mention: str, entity: Entity) -> float:
        """
        Lexical similarity using RapidFuzz.

        Uses WRatio for fuzzy matching, with bonuses for exact word matches
        to better distinguish similar names (e.g., "Alice" vs "Alex").
        """
        scores = []
        mention_lower = mention.lower().strip()
        mention_words = set(mention_lower.split())

        for name in entity.all_names:
            name_lower = name.lower().strip()
            name_words = set(name_lower.split())

            # Base fuzzy score
            ratio = fuzz.WRatio(mention_lower, name_lower) / 100.0

            # Adjust score based on word matching to distinguish similar names
            if mention_lower in name_words or any(mention_lower == word for word in name_words):
                # Exact word match - strong boost
                ratio = min(1.0, ratio * 1.4)
            elif mention_words & name_words:  # Partial word overlap
                ratio = min(1.0, ratio + 0.03)
            elif ratio > 0.60:  # High fuzzy score but no exact word match
                # Penalize partial matches (e.g., "Alice" matching "Alex Chen")
                ratio = ratio * 0.75

            scores.append(ratio)

        return max(scores) if scores else 0.0

    def _phonetic_score(self, mention: str, entity: Entity) -> float:
        """
        Phonetic similarity using jellyfish (Soundex + Metaphone).

        Handles name collisions: Katherine/Catherine, Jon/John, etc.
        Only applies to person/name entities.

        Requires minimum lexical similarity to avoid false matches
        (e.g., Alice/Alex both have Soundex A420 but are different names).
        """
        # Only apply phonetic matching to person-like entities
        if entity.type not in ['person', 'contact', 'user']:
            return 0.0

        mention_lower = mention.lower().strip()
        scores = []

        for name in entity.all_names:
            name_lower = name.lower().strip()

            # Extract first/last name for better matching
            mention_parts = mention_lower.split()
            name_parts = name_lower.split()

            for m_part in mention_parts:
                # Skip very short words (initials, etc.)
                if len(m_part) < 3:
                    continue

                for n_part in name_parts:
                    if len(n_part) < 3:
                        continue

                    # Require minimum lexical similarity to avoid false phonetic matches
                    # (Alice and Alex both Soundex to A420, but differ lexically)
                    lex_sim = fuzz.ratio(m_part, n_part) / 100.0
                    if lex_sim < 0.70:  # Different names, even if phonetically similar
                        continue

                    # Soundex match (American phonetic)
                    if jellyfish.soundex(m_part) == jellyfish.soundex(n_part):
                        scores.append(1.0)
                    # Metaphone match (more sophisticated)
                    elif jellyfish.metaphone(m_part) == jellyfish.metaphone(n_part):
                        scores.append(0.9)

        return max(scores) if scores else 0.0

    def _type_score(self, entity: Entity, expected_type: Optional[str]) -> float:
        """Type match score."""
        if not expected_type:
            return 0.5  # Neutral when type is unknown

        if entity.type == expected_type.lower():
            return 1.0

        # Partial credit for related types
        related_types = {
            'person': ['user', 'contact', 'member'],
            'document': ['file', 'attachment'],
            'calendar_event': ['event', 'meeting'],
        }

        for primary, aliases in related_types.items():
            if entity.type == primary and expected_type.lower() in aliases:
                return 0.8
            if entity.type in aliases and expected_type.lower() == primary:
                return 0.8

        return 0.0

    def _structured_score(
        self,
        entity: Entity,
        context: Dict[str, any]
    ) -> float:
        """
        Score based on structured signals (owner, email, timestamp, etc.).

        This is where temporal/ownership disambiguation happens.
        """
        signals = []

        # Owner match
        if 'owner' in context and entity.owner:
            if entity.owner.lower() == context['owner'].lower():
                signals.append(1.0)

        # Email match
        if 'email' in context and entity.email:
            if entity.email.lower() == context['email'].lower():
                signals.append(1.0)

        # System of origin match
        if 'system' in context and entity.system_of_origin:
            if entity.system_of_origin.lower() == context['system'].lower():
                signals.append(1.0)

        # Metadata hint matching (fuzzy match against entity metadata)
        if 'metadata_hint' in context and entity.metadata:
            hint = context['metadata_hint'].lower()
            metadata = entity.metadata.lower()
            # Use fuzzy matching to see if hint appears in metadata
            if hint in metadata or fuzz.partial_ratio(hint, metadata) > 80:
                signals.append(0.8)

        # Recency boost (for temporal disambiguation)
        if 'prefer_recent' in context and context['prefer_recent']:
            if entity.updated_at or entity.timestamp:
                # Give newer items a boost (simplified - real impl would parse timestamps)
                signals.append(0.7)

        # Temporal recency for documents (2025 > 2024)
        if entity.updated_at:
            try:
                # Simple year comparison
                year = int(entity.updated_at.split('-')[0])
                if year >= 2025:
                    signals.append(0.8)
                elif year >= 2024:
                    signals.append(0.5)
            except:
                pass

        # Status preference (active > archived)
        if entity.status:
            if entity.status.lower() in ['active', 'open']:
                signals.append(0.6)
            elif entity.status.lower() in ['archived', 'closed', 'deleted']:
                signals.append(0.2)

        # Average of available signals (or neutral if none)
        return sum(signals) / len(signals) if signals else 0.5

    def get_matched_fields(
        self,
        mention: str,
        entity: Entity,
        context: Optional[Dict[str, any]] = None
    ) -> List[str]:
        """
        Get list of fields that contributed to the match.

        Used for provenance and clarification generation.
        """
        matched = []
        context = context or {}

        # Check primary name/title
        if entity.name and fuzz.WRatio(mention.lower(), entity.name.lower()) > 80:
            matched.append('name')
        if entity.title and fuzz.WRatio(mention.lower(), entity.title.lower()) > 80:
            matched.append('title')

        # Check aliases
        for alias in entity.aliases:
            if fuzz.WRatio(mention.lower(), alias.lower()) > 80:
                matched.append(f'alias:{alias}')
                break

        # Check structured signals
        if 'owner' in context and entity.owner and entity.owner.lower() == context['owner'].lower():
            matched.append('owner')
        if 'email' in context and entity.email and entity.email.lower() == context['email'].lower():
            matched.append('email')
        if entity.type == context.get('expected_type', '').lower():
            matched.append('type')

        return matched

    def score_all(
        self,
        mention: str,
        candidates: List[Entity],
        expected_type: Optional[str] = None,
        context: Optional[str] = None
    ) -> List["ScoredEntity"]:
        """
        Score all candidates and return structured results.

        This is the high-level API expected by tests and resolvers.

        Args:
            mention: Entity mention from tool args
            candidates: List of candidate entities
            expected_type: Expected entity type (for type scoring)
            context: Optional context string (for metadata matching)

        Returns:
            List of ScoredEntity objects with entity, score, and matched_fields
        """
        if not candidates:
            return []

        # Build context dict
        context_dict = {'expected_type': expected_type} if expected_type else {}
        if context:
            # If context is a string, use it for metadata matching
            context_dict['metadata_hint'] = context

        # Score each candidate
        results = []
        for entity in candidates:
            # Calculate score
            score = self.score(mention, entity, context_dict)

            # Get matched fields
            matched_fields = self.get_matched_fields(mention, entity, context_dict)

            # Create result object
            result = ScoredEntity(entity=entity, score=score, matched_fields=matched_fields)
            results.append(result)

        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)
        return results


class ScoredEntity:
    """Result object for scored entities."""

    def __init__(self, entity: Entity, score: float, matched_fields: List[str]):
        self.entity = entity
        self.score = score
        self.matched_fields = matched_fields

    def __repr__(self):
        return f"ScoredEntity(entity={self.entity.id}, score={self.score:.3f})"
