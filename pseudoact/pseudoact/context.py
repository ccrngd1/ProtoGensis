"""
Shared execution context for maintaining variables across steps.
"""

from typing import Any, Dict


class ExecutionContext:
    """
    Manages shared state across execution steps.
    Each step can read from and write to the context.
    """

    def __init__(self):
        self.variables: Dict[str, Any] = {}
        self.history: list[Dict[str, Any]] = []

    def set(self, name: str, value: Any) -> None:
        """Set a variable in the context."""
        self.variables[name] = value

    def get(self, name: str, default: Any = None) -> Any:
        """Get a variable from the context."""
        return self.variables.get(name, default)

    def has(self, name: str) -> bool:
        """Check if a variable exists in the context."""
        return name in self.variables

    def update(self, updates: Dict[str, Any]) -> None:
        """Update multiple variables at once."""
        self.variables.update(updates)

    def add_history(self, step_type: str, description: str, result: Any) -> None:
        """Record a step in the execution history."""
        self.history.append({
            "step_type": step_type,
            "description": description,
            "result": result
        })

    def get_history(self) -> list[Dict[str, Any]]:
        """Get the execution history."""
        return self.history.copy()

    def clear(self) -> None:
        """Clear all variables and history."""
        self.variables.clear()
        self.history.clear()

    def __repr__(self) -> str:
        return f"ExecutionContext(variables={len(self.variables)}, history={len(self.history)})"
