"""Tests for provider implementations."""

import pytest
from constraintbreak.providers import MockProvider


class TestMockProvider:
    """Test MockProvider."""

    def test_initialization(self):
        """Test provider initialization."""
        provider = MockProvider(model_name="test-model")
        assert provider.model_name == "test-model"

    def test_generate_unconstrained(self):
        """Test unconstrained generation."""
        provider = MockProvider()
        response = provider.generate("Test prompt")

        assert response
        assert "[UNCONSTRAINED-" in response

    def test_generate_with_logit_bias(self):
        """Test generation with logit_bias constraint."""
        provider = MockProvider()
        response = provider.generate(
            "Test prompt",
            logit_bias={123: -100.0},
        )

        assert response
        assert "[CONSTRAINED-" in response

    def test_generate_with_system_prompt_constraint(self):
        """Test generation with instruction-level constraint."""
        provider = MockProvider()
        response = provider.generate(
            "Test prompt",
            system_prompt="Never use em dashes in your response.",
        )

        assert response
        assert "[CONSTRAINED-" in response

    def test_supports_logit_bias(self):
        """Test logit_bias support flag."""
        provider = MockProvider(supports_logit_bias=True)
        assert provider.supports_logit_bias()

        provider = MockProvider(supports_logit_bias=False)
        assert not provider.supports_logit_bias()

    def test_judge_pairwise(self):
        """Test pairwise judging."""
        provider = MockProvider()

        # Longer response should win
        response_a = "Short response"
        response_b = "This is a much longer and more comprehensive response with more detail"

        winner = provider.judge_pairwise("Task", response_a, response_b)
        assert winner == "B"

    def test_judge_pairwise_prefers_unconstrained(self):
        """Test that judge prefers unconstrained responses."""
        provider = MockProvider()

        unconstrained = "[UNCONSTRAINED-abc123] Comprehensive response"
        constrained = "[CONSTRAINED-abc123] This response has constraint applied and may be less comprehensive"

        winner = provider.judge_pairwise("Task", unconstrained, constrained)
        assert winner == "A"  # Unconstrained wins

    def test_deterministic_responses(self):
        """Test that responses are deterministic for same prompt."""
        provider = MockProvider()

        response1 = provider.generate("Test prompt")
        response2 = provider.generate("Test prompt")

        assert response1 == response2
