"""
Pipeline Orchestrator - Chains Monitor → Analyzer → Drafter → Validator → Publisher.
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from .models import PipelineConfig, SkillGap, SkillSpec, SkillPackage, ValidationResult
from .monitor import Monitor
from .analyzer import Analyzer
from .drafter import Drafter, MockDrafter
from .validator import Validator, MockValidator
from .publisher import Publisher, DryRunPublisher
from .tracker import SkillTracker


class SkillForgePipeline:
    """Main pipeline orchestrator."""

    def __init__(self, config: PipelineConfig):
        self.config = config

        # Initialize stages
        self.monitor = Monitor(config)
        self.analyzer = Analyzer(config)

        if config.mock_mode:
            self.drafter = MockDrafter(config)
            self.validator = MockValidator(config)
        else:
            self.drafter = Drafter(config)
            self.validator = Validator(config)

        if config.dry_run:
            self.publisher = DryRunPublisher(config)
        else:
            self.publisher = Publisher(config)

        self.tracker = SkillTracker(config)

    def run(
        self,
        log_path: Optional[Path] = None,
        existing_skills: Optional[Dict[str, Dict]] = None
    ) -> Dict[str, Any]:
        """Run the full pipeline."""
        print("Starting SkillForge Pipeline...")
        print("=" * 60)

        results = {
            'timestamp': datetime.now().isoformat(),
            'config': self.config.to_dict(),
            'stages': {}
        }

        try:
            # Stage 1: Monitor
            print("\n[Stage 1] Monitor - Detecting skill gaps...")
            gaps = self._run_monitor(log_path)
            results['stages']['monitor'] = {
                'gaps_detected': len(gaps),
                'gaps': [g.to_dict() for g in gaps]
            }
            print(f"  → Detected {len(gaps)} skill gaps")

            if not gaps:
                print("\n✓ No skill gaps detected. Pipeline complete.")
                results['status'] = 'no_gaps'
                return results

            # Load existing skills if not provided
            if existing_skills is None:
                from .monitor import SkillInventoryChecker
                checker = SkillInventoryChecker(self.config)
                existing_skills = checker.load_existing_skills()

            # Stage 2: Analyzer
            print("\n[Stage 2] Analyzer - Classifying and prioritizing gaps...")
            specs = self._run_analyzer(gaps, existing_skills)
            results['stages']['analyzer'] = {
                'specs_generated': len(specs),
                'specs': [s.to_dict() for s in specs]
            }
            print(f"  → Generated {len(specs)} skill specifications")

            if not specs:
                print("\n✓ No actionable skills to create. Pipeline complete.")
                results['status'] = 'no_specs'
                return results

            # Enforce skill budget
            specs = self._enforce_budget(specs, existing_skills)
            print(f"  → After budget enforcement: {len(specs)} specs")

            # Stage 3-5: Draft, Validate, Publish (for each spec)
            successful_publications = []
            failed_publications = []

            for idx, spec in enumerate(specs, 1):
                print(f"\n[Skill {idx}/{len(specs)}] Processing: {spec.proposed_scope[:60]}...")

                try:
                    # Stage 3: Drafter
                    print("  [Stage 3] Drafting skill...")
                    package, iterations = self._run_drafter(spec)
                    print(f"    → Skill drafted in {iterations} iteration(s)")

                    # Stage 4: Validator (with iterative refinement)
                    print("  [Stage 4] Validating skill...")
                    validation_result = self._run_validator(package, spec)
                    print(f"    → Tier 1: {'✓ PASS' if validation_result.tier1_passed else '✗ FAIL'}")
                    print(f"    → Tier 2: {'✓ PASS' if validation_result.tier2_passed else '✗ FAIL'}")
                    print(f"    → Overall: {'✓ PASS' if validation_result.passed else '✗ FAIL'}")

                    if not validation_result.passed:
                        print("    → Skill failed validation")
                        failed_publications.append({
                            'spec': spec.to_dict(),
                            'reason': 'validation_failed',
                            'issues': validation_result.to_dict()
                        })
                        continue

                    # Stage 5: Publisher
                    print("  [Stage 5] Publishing skill...")
                    deployment_metadata = self._run_publisher(package, validation_result)
                    print(f"    → Published: {deployment_metadata.get('status')}")

                    if deployment_metadata.get('pr_url'):
                        print(f"    → PR: {deployment_metadata['pr_url']}")

                    successful_publications.append(deployment_metadata)

                    # Track deployment
                    self.tracker.log_deployment(deployment_metadata)

                except Exception as e:
                    print(f"    ✗ Error: {e}")
                    failed_publications.append({
                        'spec': spec.to_dict(),
                        'reason': 'error',
                        'error': str(e)
                    })

            # Summary
            results['stages']['publications'] = {
                'successful': len(successful_publications),
                'failed': len(failed_publications),
                'details': {
                    'successful': successful_publications,
                    'failed': failed_publications
                }
            }

            results['status'] = 'complete'

            print("\n" + "=" * 60)
            print("Pipeline Complete!")
            print(f"  Successful: {len(successful_publications)}")
            print(f"  Failed: {len(failed_publications)}")
            print("=" * 60)

        except Exception as e:
            results['status'] = 'error'
            results['error'] = str(e)
            print(f"\n✗ Pipeline error: {e}")

        return results

    def _run_monitor(self, log_path: Optional[Path]) -> List[SkillGap]:
        """Run Monitor stage."""
        return self.monitor.run(log_path)

    def _run_analyzer(
        self,
        gaps: List[SkillGap],
        existing_skills: Dict[str, Dict]
    ) -> List[SkillSpec]:
        """Run Analyzer stage."""
        return self.analyzer.run(gaps, existing_skills)

    def _run_drafter(self, spec: SkillSpec) -> tuple[SkillPackage, int]:
        """Run Drafter stage with validation loop."""
        if self.config.mock_mode:
            return self.drafter.run(spec)

        # Real drafter with validation loop
        return self.drafter.run(spec, validator=self.validator)

    def _run_validator(
        self,
        package: SkillPackage,
        spec: SkillSpec
    ) -> ValidationResult:
        """Run Validator stage."""
        # Extract original gap info for replay validation
        original_gap = spec.metadata if hasattr(spec, 'metadata') else None

        return self.validator.run(package, original_gap)

    def _run_publisher(
        self,
        package: SkillPackage,
        validation_result: ValidationResult
    ) -> Dict[str, Any]:
        """Run Publisher stage."""
        return self.publisher.run(package, validation_result)

    def _enforce_budget(
        self,
        specs: List[SkillSpec],
        existing_skills: Dict[str, Dict]
    ) -> List[SkillSpec]:
        """Enforce skill budget per domain."""
        if not self.config.enable_merge_suggestions:
            return specs[:self.config.max_skills_per_run]

        # Count existing skills by domain (simplified - would need better domain detection)
        total_skills = len(existing_skills)

        if total_skills >= self.config.max_skills_per_domain:
            print(f"  ⚠️  Warning: Skill library at capacity ({total_skills}/{self.config.max_skills_per_domain})")
            print("  → Consider merging similar skills")

            # Filter to only highest priority or merge recommendations
            specs = [s for s in specs
                    if s.priority_score > 0.8 or
                       s.recommended_action.value == 'merge_similar'][:2]

        return specs[:self.config.max_skills_per_run]


class StageRunner:
    """Run individual pipeline stages independently."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.pipeline = SkillForgePipeline(config)

    def run_monitor_only(self, log_path: Optional[Path] = None) -> List[SkillGap]:
        """Run only the Monitor stage."""
        print("[Stage 1] Monitor - Detecting skill gaps...")
        gaps = self.pipeline._run_monitor(log_path)
        print(f"Detected {len(gaps)} skill gaps")

        for gap in gaps:
            print(f"\n  Gap: {gap.cluster_id}")
            print(f"    Type: {gap.failure_type.value}")
            print(f"    Frequency: {gap.frequency}")
            print(f"    Context: {gap.failure_context[:80]}...")

        return gaps

    def run_analyzer_only(
        self,
        gaps: List[SkillGap],
        existing_skills: Optional[Dict[str, Dict]] = None
    ) -> List[SkillSpec]:
        """Run only the Analyzer stage."""
        if existing_skills is None:
            from .monitor import SkillInventoryChecker
            checker = SkillInventoryChecker(self.config)
            existing_skills = checker.load_existing_skills()

        print("[Stage 2] Analyzer - Classifying and prioritizing gaps...")
        specs = self.pipeline._run_analyzer(gaps, existing_skills)
        print(f"Generated {len(specs)} specifications")

        for spec in specs:
            print(f"\n  Spec: {spec.gap_id}")
            print(f"    Priority: {spec.priority_score:.2f}")
            print(f"    Classification: {spec.classification.value}")
            print(f"    Action: {spec.recommended_action.value}")
            print(f"    Scope: {spec.proposed_scope[:80]}...")

        return specs

    def run_drafter_only(self, spec: SkillSpec) -> SkillPackage:
        """Run only the Drafter stage."""
        print("[Stage 3] Drafter - Generating skill...")
        package, iterations = self.pipeline._run_drafter(spec)
        print(f"Skill drafted in {iterations} iteration(s)")
        print(f"Skill name: {package.skill_name}")
        print(f"Content length: {len(package.skill_md_content)} chars")

        return package

    def run_validator_only(
        self,
        package: SkillPackage,
        spec: Optional[SkillSpec] = None
    ) -> ValidationResult:
        """Run only the Validator stage."""
        print("[Stage 4] Validator - Validating skill...")

        original_gap = spec.metadata if spec and hasattr(spec, 'metadata') else None
        result = self.pipeline.validator.run(package, original_gap)

        print(f"Tier 1: {'PASS' if result.tier1_passed else 'FAIL'}")
        print(f"Tier 2: {'PASS' if result.tier2_passed else 'FAIL'}")
        print(f"Overall: {'PASS' if result.passed else 'FAIL'}")

        if result.issues:
            print(f"\nIssues ({len(result.issues)}):")
            for issue in result.issues[:10]:
                print(f"  [{issue.severity}] {issue.message}")

        print(f"\nScores:")
        for key, value in result.scores.items():
            print(f"  {key}: {value:.2f}")

        return result

    def run_publisher_only(
        self,
        package: SkillPackage,
        validation_result: ValidationResult
    ) -> Dict[str, Any]:
        """Run only the Publisher stage."""
        print("[Stage 5] Publisher - Publishing skill...")
        metadata = self.pipeline._run_publisher(package, validation_result)
        print(f"Status: {metadata['status']}")

        if metadata.get('skill_dir'):
            print(f"Location: {metadata['skill_dir']}")
        if metadata.get('pr_url'):
            print(f"PR: {metadata['pr_url']}")

        return metadata
