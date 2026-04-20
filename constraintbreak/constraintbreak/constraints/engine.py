"""Constraint engine for loading and applying constraints."""

import os
from dataclasses import dataclass
from typing import Optional, Dict, List, Any
import yaml


@dataclass
class Constraint:
    """Represents a single output constraint."""

    name: str
    description: str
    instruction: str
    tokens: Optional[List[str]] = None
    logit_bias_value: float = -100.0
    category: str = "general"

    def get_instruction(self) -> str:
        """Get instruction-level constraint text."""
        return self.instruction

    def get_logit_bias(self, token_ids: Optional[List[int]]) -> Optional[Dict[int, float]]:
        """Get logit_bias dict if tokens are available.

        Args:
            token_ids: List of token IDs corresponding to self.tokens

        Returns:
            Dict of token_id -> bias, or None if not applicable
        """
        if not self.tokens or not token_ids:
            return None

        if len(token_ids) != len(self.tokens):
            return None

        return {tid: self.logit_bias_value for tid in token_ids}


class ConstraintEngine:
    """Engine for loading and managing constraints."""

    def __init__(self, constraints_file: Optional[str] = None):
        """Initialize constraint engine.

        Args:
            constraints_file: Path to constraints YAML file.
                            Defaults to built-in constraints.yaml
        """
        if constraints_file is None:
            # Use built-in constraints
            current_dir = os.path.dirname(__file__)
            constraints_file = os.path.join(current_dir, "constraints.yaml")

        self.constraints_file = constraints_file
        self.constraints: List[Constraint] = []
        self._load_constraints()

    def _load_constraints(self):
        """Load constraints from YAML file."""
        with open(self.constraints_file, "r") as f:
            data = yaml.safe_load(f)

        for constraint_data in data.get("constraints", []):
            constraint = Constraint(
                name=constraint_data["name"],
                description=constraint_data["description"],
                instruction=constraint_data["instruction"],
                tokens=constraint_data.get("tokens"),
                logit_bias_value=constraint_data.get("logit_bias_value", -100.0),
                category=constraint_data.get("category", "general"),
            )
            self.constraints.append(constraint)

    def get_constraint(self, name: str) -> Optional[Constraint]:
        """Get constraint by name.

        Args:
            name: Constraint name

        Returns:
            Constraint object or None if not found
        """
        for constraint in self.constraints:
            if constraint.name == name:
                return constraint
        return None

    def list_constraints(self) -> List[Constraint]:
        """Get all available constraints.

        Returns:
            List of all constraints
        """
        return self.constraints

    def load_preset(self, preset_name: str) -> List[Constraint]:
        """Load a preset collection of constraints.

        Args:
            preset_name: Name of preset (e.g., "VOICE")

        Returns:
            List of constraints in the preset
        """
        if preset_name.upper() == "VOICE":
            return self._load_voice_preset()

        return []

    def _load_voice_preset(self) -> List[Constraint]:
        """Load VOICE.md constraint preset.

        Returns:
            List of constraints from VOICE.md
        """
        current_dir = os.path.dirname(__file__)
        voice_file = os.path.join(current_dir, "VOICE.md")

        if not os.path.exists(voice_file):
            return []

        # Parse VOICE.md for constraint instructions
        constraints = []
        with open(voice_file, "r") as f:
            content = f.read()

        # Extract constraint from VOICE.md structure
        # For now, return as single combined constraint
        constraint = Constraint(
            name="VOICE",
            description="Combined VOICE.md style constraints",
            instruction=content,
            category="style",
        )
        constraints.append(constraint)

        return constraints
