"""
Tool definitions and execution logic.
"""

import ast
import json
import math
import operator as op
from typing import Dict, Any, List, Callable


class Tool:
    """Base class for tool definitions."""

    def __init__(self, name: str, description: str, parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.parameters = parameters

    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to dictionary format for LLM prompts."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }

    def execute(self, **kwargs) -> Any:
        """Execute the tool with given parameters."""
        raise NotImplementedError("Subclasses must implement execute()")


class CalculatorTool(Tool):
    """Calculator tool for basic arithmetic operations."""

    # Define safe operators for AST evaluation
    _SAFE_OPS = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.Pow: op.pow,
        ast.USub: op.neg,
        ast.UAdd: op.pos,
        ast.Mod: op.mod,
        ast.FloorDiv: op.floordiv,
    }

    # Define safe functions
    _SAFE_FUNCS = {
        "sqrt": math.sqrt,
        "pow": pow,
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
    }

    def __init__(self):
        super().__init__(
            name="calculator",
            description="Perform arithmetic calculations. Supports +, -, *, /, ** (power), sqrt, and parentheses.",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate (e.g., '2 + 3 * 4', 'sqrt(16)')"
                    }
                },
                "required": ["expression"]
            }
        )

    def _safe_eval(self, expr: str) -> float:
        """Safely evaluate a mathematical expression using AST parsing."""
        def _eval(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            elif isinstance(node, ast.BinOp) and type(node.op) in self._SAFE_OPS:
                return self._SAFE_OPS[type(node.op)](_eval(node.left), _eval(node.right))
            elif isinstance(node, ast.UnaryOp) and type(node.op) in self._SAFE_OPS:
                return self._SAFE_OPS[type(node.op)](_eval(node.operand))
            elif isinstance(node, ast.Call):
                # Handle function calls like sqrt(), pow(), etc.
                if isinstance(node.func, ast.Name) and node.func.id in self._SAFE_FUNCS:
                    func = self._SAFE_FUNCS[node.func.id]
                    args = [_eval(arg) for arg in node.args]
                    return func(*args)
                else:
                    raise ValueError(f"Unsafe function: {ast.dump(node.func)}")
            else:
                raise ValueError(f"Unsafe expression: {ast.dump(node)}")

        return _eval(ast.parse(expr, mode='eval').body)

    def execute(self, expression: str) -> float:
        """Safely evaluate a mathematical expression."""
        try:
            # Evaluate the expression safely using AST parsing
            result = self._safe_eval(expression)
            return float(result)
        except Exception as e:
            return f"Error: {str(e)}"


class SearchTool(Tool):
    """Mock search tool for demonstration."""

    def __init__(self):
        super().__init__(
            name="search",
            description="Search for information on a topic. Returns relevant facts.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["query"]
            }
        )

    def execute(self, query: str) -> str:
        """Mock search implementation."""
        # This is a mock - in production, this would call a real search API
        mock_results = {
            "python": "Python is a high-level programming language known for its simplicity and readability.",
            "ai": "Artificial Intelligence (AI) refers to the simulation of human intelligence in machines.",
            "weather": "Weather is the state of the atmosphere at a particular place and time.",
            "population": "The world population is approximately 8 billion people as of 2024."
        }

        query_lower = query.lower()
        for key, value in mock_results.items():
            if key in query_lower:
                return value

        return f"No specific results found for: {query}"


class GetFactTool(Tool):
    """Tool to retrieve specific facts."""

    def __init__(self):
        super().__init__(
            name="get_fact",
            description="Retrieve a specific fact about a topic.",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to get fact about"
                    },
                    "aspect": {
                        "type": "string",
                        "description": "Specific aspect to retrieve (e.g., 'population', 'capital', 'founded')"
                    }
                },
                "required": ["topic", "aspect"]
            }
        )

    def execute(self, topic: str, aspect: str) -> str:
        """Mock fact retrieval."""
        facts = {
            "france": {
                "population": "67 million",
                "capital": "Paris",
                "founded": "843 AD"
            },
            "japan": {
                "population": "125 million",
                "capital": "Tokyo",
                "founded": "660 BC"
            },
            "usa": {
                "population": "331 million",
                "capital": "Washington D.C.",
                "founded": "1776"
            }
        }

        topic_lower = topic.lower()
        aspect_lower = aspect.lower()

        if topic_lower in facts and aspect_lower in facts[topic_lower]:
            return facts[topic_lower][aspect_lower]

        return f"Fact not found for {topic} - {aspect}"


class ToolRegistry:
    """Registry for managing available tools."""

    def __init__(self):
        self.tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self.tools[tool.name] = tool

    def get_tool(self, name: str) -> Tool:
        """Get a tool by name."""
        if name not in self.tools:
            raise ValueError(f"Tool not found: {name}")
        return self.tools[name]

    def get_all_tools(self) -> List[Tool]:
        """Get all registered tools."""
        return list(self.tools.values())

    def get_tool_descriptions(self) -> List[Dict[str, Any]]:
        """Get descriptions of all tools for LLM prompts."""
        return [tool.to_dict() for tool in self.tools.values()]

    def execute_tool(self, name: str, **kwargs) -> Any:
        """Execute a tool by name."""
        tool = self.get_tool(name)
        return tool.execute(**kwargs)


def get_default_tools() -> ToolRegistry:
    """Get a registry with default tools."""
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(SearchTool())
    registry.register(GetFactTool())
    return registry
