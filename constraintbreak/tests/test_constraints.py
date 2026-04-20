"""Tests for constraint engine."""

import pytest
from constraintbreak.constraints import ConstraintEngine, Constraint


class TestConstraintEngine:
    """Test ConstraintEngine."""

    def test_load_constraints(self):
        """Test loading built-in constraints."""
        engine = ConstraintEngine()
        constraints = engine.list_constraints()

        assert len(constraints) == 6
        assert all(isinstance(c, Constraint) for c in constraints)

    def test_get_constraint_by_name(self):
        """Test getting constraint by name."""
        engine = ConstraintEngine()

        constraint = engine.get_constraint("em_dash_ban")
        assert constraint is not None
        assert constraint.name == "em_dash_ban"
        assert "em dash" in constraint.description.lower()

    def test_get_nonexistent_constraint(self):
        """Test getting constraint that doesn't exist."""
        engine = ConstraintEngine()

        constraint = engine.get_constraint("nonexistent")
        assert constraint is None

    def test_constraint_has_instruction(self):
        """Test that constraints have instructions."""
        engine = ConstraintEngine()

        constraint = engine.get_constraint("colon_ban")
        assert constraint is not None
        assert constraint.get_instruction()
        assert "colon" in constraint.get_instruction().lower()

    def test_constraint_has_tokens(self):
        """Test that constraints have token lists."""
        engine = ConstraintEngine()

        constraint = engine.get_constraint("em_dash_ban")
        assert constraint is not None
        assert constraint.tokens
        assert "—" in constraint.tokens

    def test_constraint_logit_bias(self):
        """Test logit_bias generation."""
        constraint = Constraint(
            name="test",
            description="Test constraint",
            instruction="Never use X",
            tokens=["X"],
            logit_bias_value=-100.0,
        )

        token_ids = [123]
        logit_bias = constraint.get_logit_bias(token_ids)

        assert logit_bias is not None
        assert logit_bias == {123: -100.0}

    def test_constraint_categories(self):
        """Test that constraints have categories."""
        engine = ConstraintEngine()
        constraints = engine.list_constraints()

        categories = set(c.category for c in constraints)
        assert "punctuation" in categories
        assert "formatting" in categories

    def test_load_voice_preset(self):
        """Test loading VOICE preset."""
        engine = ConstraintEngine()
        voice_constraints = engine.load_preset("VOICE")

        assert len(voice_constraints) > 0
        assert voice_constraints[0].name == "VOICE"
