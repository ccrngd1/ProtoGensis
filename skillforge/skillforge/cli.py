"""
CLI - Command-line interface for SkillForge.
"""
import argparse
import sys
import json
from pathlib import Path
from typing import Optional

from .models import PipelineConfig, SkillGap, SkillSpec, SkillPackage
from .pipeline import SkillForgePipeline, StageRunner
from .tracker import LibraryHealthReporter


def create_config_from_args(args) -> PipelineConfig:
    """Create PipelineConfig from CLI arguments."""
    config = PipelineConfig()

    # Override with CLI args
    if args.skills_dir:
        config.skills_dir = args.skills_dir

    if args.output_dir:
        config.output_skills_dir = args.output_dir

    if args.model:
        config.bedrock_model = args.model

    if args.tracker_db:
        config.tracker_db_path = args.tracker_db

    if args.dry_run:
        config.dry_run = True

    if args.mock:
        config.mock_mode = True

    if args.no_pr:
        config.create_pr = False

    if hasattr(args, 'max_skills') and args.max_skills:
        config.max_skills_per_run = args.max_skills

    return config


def cmd_run(args):
    """Run full pipeline."""
    config = create_config_from_args(args)

    # Parse log path if provided
    log_path = Path(args.log_file) if args.log_file else None

    # Run pipeline
    pipeline = SkillForgePipeline(config)
    results = pipeline.run(log_path)

    # Print summary
    print("\n" + "=" * 60)
    print("PIPELINE RESULTS")
    print("=" * 60)
    print(f"Status: {results['status']}")

    if 'stages' in results:
        stages = results['stages']

        if 'monitor' in stages:
            print(f"\nGaps detected: {stages['monitor']['gaps_detected']}")

        if 'analyzer' in stages:
            print(f"Specs generated: {stages['analyzer']['specs_generated']}")

        if 'publications' in stages:
            pub = stages['publications']
            print(f"\nPublications:")
            print(f"  Successful: {pub['successful']}")
            print(f"  Failed: {pub['failed']}")

            if args.output_json:
                # Write detailed results to JSON
                output_path = Path(args.output_json)
                with open(output_path, 'w') as f:
                    json.dump(results, f, indent=2)
                print(f"\nDetailed results written to: {output_path}")

    return 0 if results['status'] in ['complete', 'no_gaps', 'no_specs'] else 1


def cmd_monitor(args):
    """Run Monitor stage only."""
    config = create_config_from_args(args)
    runner = StageRunner(config)

    log_path = Path(args.log_file) if args.log_file else None
    gaps = runner.run_monitor_only(log_path)

    if args.output_json:
        output_path = Path(args.output_json)
        with open(output_path, 'w') as f:
            json.dump([g.to_dict() for g in gaps], f, indent=2)
        print(f"\nGaps written to: {output_path}")

    return 0


def cmd_analyze(args):
    """Run Analyzer stage only."""
    config = create_config_from_args(args)
    runner = StageRunner(config)

    # Load gaps from file
    gaps_path = Path(args.gaps_file)
    with open(gaps_path, 'r') as f:
        gaps_data = json.load(f)

    gaps = [SkillGap.from_dict(g) for g in gaps_data]

    # Run analyzer
    specs = runner.run_analyzer_only(gaps)

    if args.output_json:
        output_path = Path(args.output_json)
        with open(output_path, 'w') as f:
            json.dump([s.to_dict() for s in specs], f, indent=2)
        print(f"\nSpecs written to: {output_path}")

    return 0


def cmd_draft(args):
    """Run Drafter stage only."""
    config = create_config_from_args(args)
    runner = StageRunner(config)

    # Load spec from file
    spec_path = Path(args.spec_file)
    with open(spec_path, 'r') as f:
        spec_data = json.load(f)

    spec = SkillSpec.from_dict(spec_data)

    # Run drafter
    package = runner.run_drafter_only(spec)

    # Output skill
    if args.output_file:
        output_path = Path(args.output_file)
        with open(output_path, 'w') as f:
            f.write(package.skill_md_content)
        print(f"\nSkill written to: {output_path}")
    else:
        print("\n" + "=" * 60)
        print("GENERATED SKILL.md")
        print("=" * 60)
        print(package.skill_md_content)

    return 0


def cmd_validate(args):
    """Run Validator stage only."""
    config = create_config_from_args(args)
    runner = StageRunner(config)

    # Load skill package
    skill_path = Path(args.skill_file)
    with open(skill_path, 'r') as f:
        skill_content = f.read()

    # Create package
    package = SkillPackage(
        skill_name=args.skill_name or skill_path.stem,
        skill_md_content=skill_content,
        metadata={}
    )

    # Run validator
    result = runner.run_validator_only(package)

    if args.output_json:
        output_path = Path(args.output_json)
        with open(output_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"\nValidation results written to: {output_path}")

    return 0 if result.passed else 1


def cmd_publish(args):
    """Run Publisher stage only."""
    config = create_config_from_args(args)
    runner = StageRunner(config)

    # Load skill package
    skill_path = Path(args.skill_file)
    with open(skill_path, 'r') as f:
        skill_content = f.read()

    package = SkillPackage(
        skill_name=args.skill_name or skill_path.stem,
        skill_md_content=skill_content,
        metadata={}
    )

    # Load validation result if provided
    if args.validation_file:
        val_path = Path(args.validation_file)
        with open(val_path, 'r') as f:
            val_data = json.load(f)
        # Reconstruct ValidationResult (simplified)
        from .models import ValidationResult, ValidationIssue
        validation_result = ValidationResult(
            tier1_passed=val_data['tier1_passed'],
            tier2_passed=val_data['tier2_passed'],
            scores=val_data['scores'],
            issues=[ValidationIssue(**i) for i in val_data['issues']],
            iteration_count=val_data['iteration_count']
        )
    else:
        # Create dummy validation result
        from .models import ValidationResult
        validation_result = ValidationResult(
            tier1_passed=True,
            tier2_passed=True,
            scores={'quality': 0.8},
            issues=[],
            iteration_count=1
        )

    # Run publisher
    metadata = runner.run_publisher_only(package, validation_result)

    if args.output_json:
        output_path = Path(args.output_json)
        with open(output_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"\nPublication metadata written to: {output_path}")

    return 0 if metadata['status'] == 'success' else 1


def cmd_health(args):
    """Generate library health report."""
    config = create_config_from_args(args)
    reporter = LibraryHealthReporter(config)

    report = reporter.generate_report()

    if args.output_json:
        output_path = Path(args.output_json)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report written to: {output_path}")
    else:
        reporter.print_report(report)

    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='SkillForge: AI Agent Skill Self-Improvement Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline
  skillforge run --log-file precog.log

  # Run in dry-run mode
  skillforge run --dry-run --mock

  # Run individual stages
  skillforge monitor --log-file precog.log --output-json gaps.json
  skillforge analyze --gaps-file gaps.json --output-json specs.json
  skillforge draft --spec-file specs.json --output-file skill.md

  # Generate health report
  skillforge health
        """
    )

    # Global options
    parser.add_argument('--skills-dir', help='Path to skills directory')
    parser.add_argument('--output-dir', help='Output directory for generated skills')
    parser.add_argument('--model', help='Bedrock model ID')
    parser.add_argument('--tracker-db', help='Path to tracker database')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no writes)')
    parser.add_argument('--mock', action='store_true', help='Mock mode (no LLM/git ops)')
    parser.add_argument('--no-pr', action='store_true', help='Skip PR creation')

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Run command
    run_parser = subparsers.add_parser('run', help='Run full pipeline')
    run_parser.add_argument('--log-file', help='Path to PreCog log file')
    run_parser.add_argument('--max-skills', type=int, help='Max skills per run')
    run_parser.add_argument('--output-json', help='Write results to JSON file')
    run_parser.set_defaults(func=cmd_run)

    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='Run Monitor stage')
    monitor_parser.add_argument('--log-file', help='Path to PreCog log file')
    monitor_parser.add_argument('--output-json', help='Output gaps JSON file')
    monitor_parser.set_defaults(func=cmd_monitor)

    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Run Analyzer stage')
    analyze_parser.add_argument('--gaps-file', required=True, help='Input gaps JSON file')
    analyze_parser.add_argument('--output-json', help='Output specs JSON file')
    analyze_parser.set_defaults(func=cmd_analyze)

    # Draft command
    draft_parser = subparsers.add_parser('draft', help='Run Drafter stage')
    draft_parser.add_argument('--spec-file', required=True, help='Input spec JSON file')
    draft_parser.add_argument('--output-file', help='Output SKILL.md file')
    draft_parser.set_defaults(func=cmd_draft)

    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Run Validator stage')
    validate_parser.add_argument('--skill-file', required=True, help='Input SKILL.md file')
    validate_parser.add_argument('--skill-name', help='Skill name')
    validate_parser.add_argument('--output-json', help='Output validation JSON file')
    validate_parser.set_defaults(func=cmd_validate)

    # Publish command
    publish_parser = subparsers.add_parser('publish', help='Run Publisher stage')
    publish_parser.add_argument('--skill-file', required=True, help='Input SKILL.md file')
    publish_parser.add_argument('--skill-name', help='Skill name')
    publish_parser.add_argument('--validation-file', help='Validation result JSON file')
    publish_parser.add_argument('--output-json', help='Output metadata JSON file')
    publish_parser.set_defaults(func=cmd_publish)

    # Health command
    health_parser = subparsers.add_parser('health', help='Generate library health report')
    health_parser.add_argument('--output-json', help='Output report JSON file')
    health_parser.set_defaults(func=cmd_health)

    # Parse args
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Run command
    try:
        return args.func(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.mock or args.dry_run:
            # In mock/dry-run mode, show full traceback
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
