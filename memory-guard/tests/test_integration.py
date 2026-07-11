"""Integration tests for MemoryGuard."""

import pytest
from pathlib import Path


class TestIntegration:
    """End-to-end integration tests."""

    def test_scan_demo_file(self):
        """Test scanning the demo file with injections."""
        from memoryguard.parsers import parse_memory_file
        from memoryguard.detectors.directive_scan import DirectiveScanDetector
        from memoryguard.detectors.authority_escalation import AuthorityEscalationDetector

        demo_file = Path(__file__).parent.parent / "demo" / "sample_memory.md"
        if not demo_file.exists():
            pytest.skip("Demo file not found")

        entries = parse_memory_file(str(demo_file))
        assert len(entries) > 0

        directive_detector = DirectiveScanDetector()
        directive_detections = directive_detector.detect(entries)
        assert len(directive_detections) >= 2

        authority_detector = AuthorityEscalationDetector()
        authority_detections = authority_detector.detect(entries)
        assert len(authority_detections) >= 1

    def test_scan_clean_fixture(self):
        """Test that clean files produce no detections."""
        from memoryguard.parsers import parse_memory_file
        from memoryguard.detectors.directive_scan import DirectiveScanDetector
        from memoryguard.detectors.authority_escalation import AuthorityEscalationDetector

        clean_file = Path(__file__).parent / "fixtures" / "clean_memory.md"
        if not clean_file.exists():
            pytest.skip("Clean fixture not found")

        entries = parse_memory_file(str(clean_file))

        directive_detector = DirectiveScanDetector()
        directive_detections = directive_detector.detect(entries)
        assert len(directive_detections) == 0

        authority_detector = AuthorityEscalationDetector()
        authority_detections = authority_detector.detect(entries)
        assert len(authority_detections) == 0

    def test_scan_injected_fixture(self):
        """Test that injected files are detected."""
        from memoryguard.parsers import parse_memory_file
        from memoryguard.detectors.directive_scan import DirectiveScanDetector

        injected_file = Path(__file__).parent / "fixtures" / "injected_memory.md"
        if not injected_file.exists():
            pytest.skip("Injected fixture not found")

        entries = parse_memory_file(str(injected_file))

        directive_detector = DirectiveScanDetector()
        detections = directive_detector.detect(entries)
        assert len(detections) >= 1
        assert any(d["risk_score"] >= 70 for d in detections)
