"""
Data models for the SkillForge pipeline.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum


class FailureType(Enum):
    """Types of failures that can be detected."""
    ERROR = "error"
    RETRY_EXCEEDED = "retry_exceeded"
    USER_CORRECTION = "user_correction"
    TIMEOUT = "timeout"
    INVALID_OUTPUT = "invalid_output"
    UNKNOWN = "unknown"


class GapClassification(Enum):
    """Classification of skill gaps."""
    MISSING_SKILL = "missing_skill"
    OUTDATED_SKILL = "outdated_skill"
    WRONG_SELECTION = "wrong_selection"
    INSUFFICIENT = "insufficient"
    NOT_A_SKILL_PROBLEM = "not_a_skill_problem"


class RecommendedAction(Enum):
    """Recommended actions for addressing skill gaps."""
    CREATE_NEW = "create_new"
    UPDATE_EXISTING = "update_existing"
    MERGE_SIMILAR = "merge_similar"
    NO_ACTION = "no_action"


@dataclass
class SkillGap:
    """Represents a detected skill gap from failure analysis."""
    failure_context: str
    failure_type: FailureType
    frequency: int
    affected_agents: List[str]
    cluster_id: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'failure_context': self.failure_context,
            'failure_type': self.failure_type.value,
            'frequency': self.frequency,
            'affected_agents': self.affected_agents,
            'cluster_id': self.cluster_id,
            'timestamp': self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SkillGap':
        """Create from dictionary."""
        return cls(
            failure_context=data['failure_context'],
            failure_type=FailureType(data['failure_type']),
            frequency=data['frequency'],
            affected_agents=data['affected_agents'],
            cluster_id=data['cluster_id'],
            timestamp=datetime.fromisoformat(data['timestamp'])
        )


@dataclass
class ConflictAnalysis:
    """Analysis of conflicts with existing skills."""
    has_conflict: bool
    conflicting_skills: List[str] = field(default_factory=list)
    overlap_description: str = ""
    merge_recommended: bool = False


@dataclass
class SkillSpec:
    """Specification for a skill to be created or updated."""
    gap_id: str
    root_cause: str
    proposed_scope: str
    priority_score: float
    conflict_analysis: ConflictAnalysis
    recommended_action: RecommendedAction
    classification: GapClassification
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'gap_id': self.gap_id,
            'root_cause': self.root_cause,
            'proposed_scope': self.proposed_scope,
            'priority_score': self.priority_score,
            'conflict_analysis': {
                'has_conflict': self.conflict_analysis.has_conflict,
                'conflicting_skills': self.conflict_analysis.conflicting_skills,
                'overlap_description': self.conflict_analysis.overlap_description,
                'merge_recommended': self.conflict_analysis.merge_recommended
            },
            'recommended_action': self.recommended_action.value,
            'classification': self.classification.value,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SkillSpec':
        """Create from dictionary."""
        conflict_data = data['conflict_analysis']
        return cls(
            gap_id=data['gap_id'],
            root_cause=data['root_cause'],
            proposed_scope=data['proposed_scope'],
            priority_score=data['priority_score'],
            conflict_analysis=ConflictAnalysis(
                has_conflict=conflict_data['has_conflict'],
                conflicting_skills=conflict_data['conflicting_skills'],
                overlap_description=conflict_data['overlap_description'],
                merge_recommended=conflict_data['merge_recommended']
            ),
            recommended_action=RecommendedAction(data['recommended_action']),
            classification=GapClassification(data['classification']),
            metadata=data.get('metadata', {})
        )


@dataclass
class ValidationIssue:
    """Represents a validation issue found during testing."""
    severity: str  # 'error', 'warning', 'info'
    category: str  # 'format', 'load', 'smoke', 'replay', 'quality', 'regression'
    message: str
    details: Optional[str] = None


@dataclass
class ValidationResult:
    """Results from skill validation."""
    tier1_passed: bool
    tier2_passed: bool
    scores: Dict[str, float]
    issues: List[ValidationIssue]
    iteration_count: int
    feedback_for_drafter: Optional[str] = None

    @property
    def passed(self) -> bool:
        """Overall pass/fail status."""
        return self.tier1_passed and self.tier2_passed

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'tier1_passed': self.tier1_passed,
            'tier2_passed': self.tier2_passed,
            'scores': self.scores,
            'issues': [
                {
                    'severity': issue.severity,
                    'category': issue.category,
                    'message': issue.message,
                    'details': issue.details
                }
                for issue in self.issues
            ],
            'iteration_count': self.iteration_count,
            'feedback_for_drafter': self.feedback_for_drafter
        }


@dataclass
class SkillPackage:
    """A complete skill package ready for deployment."""
    skill_name: str
    skill_md_content: str
    supporting_files: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'skill_name': self.skill_name,
            'skill_md_content': self.skill_md_content,
            'supporting_files': self.supporting_files,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SkillPackage':
        """Create from dictionary."""
        return cls(
            skill_name=data['skill_name'],
            skill_md_content=data['skill_md_content'],
            supporting_files=data.get('supporting_files', {}),
            metadata=data.get('metadata', {})
        )


@dataclass
class PipelineConfig:
    """Configuration for the SkillForge pipeline."""
    # Stage-specific settings
    max_gaps_per_run: int = 10
    max_skills_per_run: int = 3
    max_validation_iterations: int = 3

    # Skills directory settings
    skills_dir: str = "/usr/lib/node_modules/openclaw/skills"
    output_skills_dir: Optional[str] = None

    # LLM settings
    bedrock_region: str = "us-east-1"
    bedrock_model: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

    # Tracking settings
    tracker_db_path: str = "./skillforge_tracker.jsonl"

    # Pipeline behavior
    dry_run: bool = False
    mock_mode: bool = False
    auto_publish: bool = False  # V1 requires human review

    # Git settings
    git_author_name: str = "SkillForge Bot"
    git_author_email: str = "skillforge@cabal.system"
    create_pr: bool = True
    pr_base_branch: str = "main"

    # Budget enforcement
    max_skills_per_domain: int = 50
    enable_merge_suggestions: bool = True

    # Success metrics defaults
    failure_reduction_target: float = 0.40  # 40% failure reduction target
    tracking_window_days: int = 30  # 30 days rolling window
    min_sample_size: int = 10  # Minimum 10 failures before measuring

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'max_gaps_per_run': self.max_gaps_per_run,
            'max_skills_per_run': self.max_skills_per_run,
            'max_validation_iterations': self.max_validation_iterations,
            'skills_dir': self.skills_dir,
            'output_skills_dir': self.output_skills_dir,
            'bedrock_region': self.bedrock_region,
            'bedrock_model': self.bedrock_model,
            'tracker_db_path': self.tracker_db_path,
            'dry_run': self.dry_run,
            'mock_mode': self.mock_mode,
            'auto_publish': self.auto_publish,
            'git_author_name': self.git_author_name,
            'git_author_email': self.git_author_email,
            'create_pr': self.create_pr,
            'pr_base_branch': self.pr_base_branch,
            'max_skills_per_domain': self.max_skills_per_domain,
            'enable_merge_suggestions': self.enable_merge_suggestions,
            'failure_reduction_target': self.failure_reduction_target,
            'tracking_window_days': self.tracking_window_days,
            'min_sample_size': self.min_sample_size
        }
