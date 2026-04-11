"""
Stage 2: Analyzer - Classify gaps, define scope, score priority, check conflicts.
"""
from typing import List, Dict
from pathlib import Path
import re

from .models import (
    SkillGap, SkillSpec, GapClassification, RecommendedAction,
    ConflictAnalysis, PipelineConfig
)


class GapClassifier:
    """Classify skill gaps into categories."""

    def __init__(self, config: PipelineConfig):
        self.config = config

    def classify(self, gap: SkillGap, existing_skills: Dict[str, Dict]) -> GapClassification:
        """Classify a skill gap."""
        # Check if there are related existing skills
        related_skills = self._find_related_skills(gap, existing_skills)

        if not related_skills:
            # No related skills found - likely a missing skill
            return GapClassification.MISSING_SKILL

        # Analyze the nature of the failure
        if self._indicates_outdated(gap, related_skills):
            return GapClassification.OUTDATED_SKILL

        if self._indicates_wrong_selection(gap):
            return GapClassification.WRONG_SELECTION

        if self._indicates_insufficient(gap, related_skills):
            return GapClassification.INSUFFICIENT

        # Default to missing skill
        return GapClassification.MISSING_SKILL

    def _find_related_skills(self, gap: SkillGap, existing_skills: Dict) -> List[str]:
        """Find skills related to the gap."""
        related = []
        gap_keywords = self._extract_keywords(gap.failure_context)

        for skill_name, skill_data in existing_skills.items():
            skill_content = skill_data.get('content', '').lower()
            metadata = skill_data.get('metadata', {})
            description = metadata.get('description', '').lower()

            # Check for keyword overlap
            matches = sum(1 for kw in gap_keywords
                         if kw in skill_content or kw in description)

            if matches >= 2:  # At least 2 keyword matches
                related.append(skill_name)

        return related

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        words = re.findall(r'\b\w+\b', text.lower())
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with'}
        return [w for w in words if w not in stopwords and len(w) > 3]

    def _indicates_outdated(self, gap: SkillGap, related_skills: List[str]) -> bool:
        """Check if gap indicates an outdated skill."""
        # If there are related skills but still failing, might be outdated
        return len(related_skills) > 0 and gap.frequency > 3

    def _indicates_wrong_selection(self, gap: SkillGap) -> bool:
        """Check if gap indicates wrong skill selection."""
        # Look for patterns suggesting selection issues
        selection_patterns = ['wrong.*skill', 'incorrect.*selection', 'chose.*wrong']
        return any(re.search(p, gap.failure_context, re.IGNORECASE)
                  for p in selection_patterns)

    def _indicates_insufficient(self, gap: SkillGap, related_skills: List[str]) -> bool:
        """Check if gap indicates insufficient skill guidance."""
        # Related skills exist but are incomplete
        return len(related_skills) > 0 and gap.frequency > 1


class ScopeDefiner:
    """Define narrow, focused scope for skills (compact > comprehensive)."""

    def __init__(self, config: PipelineConfig):
        self.config = config

    def define_scope(self, gap: SkillGap, classification: GapClassification) -> str:
        """Define a narrow, focused scope for the skill."""
        # Extract core task from failure context
        task_description = self._extract_task_description(gap.failure_context)

        # Create focused scope based on classification
        if classification == GapClassification.MISSING_SKILL:
            scope = f"Create a skill to handle: {task_description}"

        elif classification == GapClassification.OUTDATED_SKILL:
            scope = f"Update existing skill to properly handle: {task_description}"

        elif classification == GapClassification.INSUFFICIENT:
            scope = f"Enhance skill with specific guidance for: {task_description}"

        else:
            scope = f"Address failure in: {task_description}"

        # Ensure scope is concise (SkillsBench finding: compact > comprehensive)
        if len(scope) > 150:
            scope = scope[:147] + "..."

        return scope

    def _extract_task_description(self, context: str) -> str:
        """Extract core task description from failure context."""
        # Remove agent prefix like [AgentName]
        context = re.sub(r'^\[.*?\]\s*', '', context)

        # Extract task type if present
        task_match = re.search(r'(\w+):', context)
        if task_match:
            task_type = task_match.group(1)
            rest = context[task_match.end():].strip()
            return f"{task_type} - {rest[:100]}"

        return context[:100]


class PriorityScorer:
    """Score priority as frequency * impact * feasibility."""

    def __init__(self, config: PipelineConfig):
        self.config = config

    def calculate_score(self, gap: SkillGap, classification: GapClassification) -> float:
        """Calculate priority score."""
        # Frequency component (0-1)
        frequency_score = min(gap.frequency / 10.0, 1.0)

        # Impact component (0-1) based on failure type
        impact_score = self._calculate_impact(gap)

        # Feasibility component (0-1) based on classification
        feasibility_score = self._calculate_feasibility(classification)

        # Combined score (0-1)
        priority = (frequency_score * 0.4 +
                   impact_score * 0.4 +
                   feasibility_score * 0.2)

        return round(priority, 3)

    def _calculate_impact(self, gap: SkillGap) -> float:
        """Calculate impact score based on failure type."""
        impact_weights = {
            'error': 0.9,
            'retry_exceeded': 0.8,
            'timeout': 0.7,
            'invalid_output': 0.7,
            'user_correction': 0.6,
            'unknown': 0.5,
        }
        return impact_weights.get(gap.failure_type.value, 0.5)

    def _calculate_feasibility(self, classification: GapClassification) -> float:
        """Calculate feasibility score based on classification."""
        feasibility_weights = {
            GapClassification.MISSING_SKILL: 0.8,  # Easier to create new
            GapClassification.INSUFFICIENT: 0.7,   # Enhancement is feasible
            GapClassification.OUTDATED_SKILL: 0.6, # Updating can be tricky
            GapClassification.WRONG_SELECTION: 0.4, # Selection is harder to fix
            GapClassification.NOT_A_SKILL_PROBLEM: 0.1,
        }
        return feasibility_weights.get(classification, 0.5)


class ConflictChecker:
    """Check for conflicts with existing skills."""

    def __init__(self, config: PipelineConfig):
        self.config = config

    def check_conflicts(
        self,
        proposed_scope: str,
        existing_skills: Dict[str, Dict]
    ) -> ConflictAnalysis:
        """Check for conflicts with existing skills."""
        conflicting = []
        overlap_descriptions = []

        scope_keywords = self._extract_keywords(proposed_scope)

        for skill_name, skill_data in existing_skills.items():
            metadata = skill_data.get('metadata', {})
            description = metadata.get('description', '')

            overlap_score = self._calculate_overlap(scope_keywords, description)

            if overlap_score > 0.6:  # Significant overlap
                conflicting.append(skill_name)
                overlap_descriptions.append(
                    f"{skill_name}: {int(overlap_score * 100)}% overlap"
                )

        has_conflict = len(conflicting) > 0
        merge_recommended = len(conflicting) > 0 and len(conflicting) <= 2

        return ConflictAnalysis(
            has_conflict=has_conflict,
            conflicting_skills=conflicting,
            overlap_description="; ".join(overlap_descriptions),
            merge_recommended=merge_recommended
        )

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        words = re.findall(r'\b\w+\b', text.lower())
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
                    'to', 'for', 'with', 'create', 'update', 'skill', 'handle'}
        return [w for w in words if w not in stopwords and len(w) > 3]

    def _calculate_overlap(self, keywords: List[str], description: str) -> float:
        """Calculate keyword overlap with existing skill."""
        if not keywords:
            return 0.0

        description_lower = description.lower()
        matches = sum(1 for kw in keywords if kw in description_lower)

        return matches / len(keywords)


class Analyzer:
    """Main Analyzer stage coordinator."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.classifier = GapClassifier(config)
        self.scope_definer = ScopeDefiner(config)
        self.priority_scorer = PriorityScorer(config)
        self.conflict_checker = ConflictChecker(config)

    def run(self, gaps: List[SkillGap], existing_skills: Dict[str, Dict]) -> List[SkillSpec]:
        """Run the Analyzer stage."""
        specs = []

        for gap in gaps:
            # Classify the gap
            classification = self.classifier.classify(gap, existing_skills)

            # Skip if not a skill problem
            if classification == GapClassification.NOT_A_SKILL_PROBLEM:
                continue

            # Define scope
            proposed_scope = self.scope_definer.define_scope(gap, classification)

            # Calculate priority
            priority_score = self.priority_scorer.calculate_score(gap, classification)

            # Check conflicts
            conflict_analysis = self.conflict_checker.check_conflicts(
                proposed_scope, existing_skills
            )

            # Determine recommended action
            recommended_action = self._determine_action(
                classification, conflict_analysis
            )

            spec = SkillSpec(
                gap_id=gap.cluster_id,
                root_cause=gap.failure_context,
                proposed_scope=proposed_scope,
                priority_score=priority_score,
                conflict_analysis=conflict_analysis,
                recommended_action=recommended_action,
                classification=classification,
                metadata={
                    'frequency': gap.frequency,
                    'failure_type': gap.failure_type.value,
                    'affected_agents': gap.affected_agents,
                }
            )
            specs.append(spec)

        # Sort by priority and return top specs
        specs = sorted(specs, key=lambda s: s.priority_score, reverse=True)
        return specs[:self.config.max_skills_per_run]

    def _determine_action(
        self,
        classification: GapClassification,
        conflict_analysis: ConflictAnalysis
    ) -> RecommendedAction:
        """Determine recommended action based on classification and conflicts."""
        if conflict_analysis.merge_recommended:
            return RecommendedAction.MERGE_SIMILAR

        if classification == GapClassification.MISSING_SKILL:
            return RecommendedAction.CREATE_NEW

        if classification in [GapClassification.OUTDATED_SKILL,
                             GapClassification.INSUFFICIENT]:
            if conflict_analysis.has_conflict:
                return RecommendedAction.UPDATE_EXISTING
            else:
                return RecommendedAction.CREATE_NEW

        return RecommendedAction.CREATE_NEW
