"""
Tests for tool implementations.
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pseudoact.tools import (
    CalculatorTool, SearchTool, GetFactTool,
    ToolRegistry, get_default_tools
)


class TestCalculatorTool(unittest.TestCase):
    """Test cases for CalculatorTool."""

    def setUp(self):
        """Set up test fixtures."""
        self.calculator = CalculatorTool()

    def test_simple_addition(self):
        """Test simple addition."""
        result = self.calculator.execute(expression="2 + 3")
        self.assertEqual(result, 5.0)

    def test_multiplication(self):
        """Test multiplication."""
        result = self.calculator.execute(expression="4 * 5")
        self.assertEqual(result, 20.0)

    def test_complex_expression(self):
        """Test complex expression."""
        result = self.calculator.execute(expression="(2 + 3) * 4")
        self.assertEqual(result, 20.0)

    def test_sqrt_function(self):
        """Test sqrt function."""
        result = self.calculator.execute(expression="sqrt(16)")
        self.assertEqual(result, 4.0)

    def test_power_operation(self):
        """Test power operation."""
        result = self.calculator.execute(expression="2 ** 3")
        self.assertEqual(result, 8.0)

    def test_invalid_expression(self):
        """Test invalid expression returns error."""
        result = self.calculator.execute(expression="invalid")
        self.assertIn("Error", str(result))

    def test_tool_to_dict(self):
        """Test converting tool to dictionary."""
        tool_dict = self.calculator.to_dict()
        self.assertIn("name", tool_dict)
        self.assertIn("description", tool_dict)
        self.assertIn("parameters", tool_dict)
        self.assertEqual(tool_dict["name"], "calculator")


class TestSearchTool(unittest.TestCase):
    """Test cases for SearchTool."""

    def setUp(self):
        """Set up test fixtures."""
        self.search = SearchTool()

    def test_search_python(self):
        """Test searching for Python."""
        result = self.search.execute(query="Python")
        self.assertIn("Python", result)
        self.assertIn("programming language", result)

    def test_search_ai(self):
        """Test searching for AI."""
        result = self.search.execute(query="AI")
        self.assertIn("Artificial Intelligence", result)

    def test_search_unknown(self):
        """Test searching for unknown topic."""
        result = self.search.execute(query="xyz123unknown")
        self.assertIn("No specific results found", result)

    def test_case_insensitive(self):
        """Test that search is case insensitive."""
        result1 = self.search.execute(query="PYTHON")
        result2 = self.search.execute(query="python")
        self.assertIn("Python", result1)
        self.assertIn("Python", result2)


class TestGetFactTool(unittest.TestCase):
    """Test cases for GetFactTool."""

    def setUp(self):
        """Set up test fixtures."""
        self.get_fact = GetFactTool()

    def test_get_france_population(self):
        """Test getting France population."""
        result = self.get_fact.execute(topic="France", aspect="population")
        self.assertIn("67 million", result)

    def test_get_japan_capital(self):
        """Test getting Japan capital."""
        result = self.get_fact.execute(topic="Japan", aspect="capital")
        self.assertIn("Tokyo", result)

    def test_get_usa_founded(self):
        """Test getting USA founding year."""
        result = self.get_fact.execute(topic="USA", aspect="founded")
        self.assertIn("1776", result)

    def test_unknown_topic(self):
        """Test getting fact for unknown topic."""
        result = self.get_fact.execute(topic="Unknown", aspect="population")
        self.assertIn("Fact not found", result)

    def test_unknown_aspect(self):
        """Test getting unknown aspect."""
        result = self.get_fact.execute(topic="France", aspect="unknown")
        self.assertIn("Fact not found", result)

    def test_case_insensitive(self):
        """Test that fact lookup is case insensitive."""
        result1 = self.get_fact.execute(topic="FRANCE", aspect="CAPITAL")
        result2 = self.get_fact.execute(topic="france", aspect="capital")
        self.assertIn("Paris", result1)
        self.assertIn("Paris", result2)


class TestToolRegistry(unittest.TestCase):
    """Test cases for ToolRegistry."""

    def setUp(self):
        """Set up test fixtures."""
        self.registry = ToolRegistry()

    def test_register_tool(self):
        """Test registering a tool."""
        calc = CalculatorTool()
        self.registry.register(calc)

        tool = self.registry.get_tool("calculator")
        self.assertIsInstance(tool, CalculatorTool)

    def test_get_all_tools(self):
        """Test getting all tools."""
        self.registry.register(CalculatorTool())
        self.registry.register(SearchTool())

        tools = self.registry.get_all_tools()
        self.assertEqual(len(tools), 2)

    def test_get_tool_descriptions(self):
        """Test getting tool descriptions."""
        self.registry.register(CalculatorTool())
        self.registry.register(SearchTool())

        descriptions = self.registry.get_tool_descriptions()
        self.assertEqual(len(descriptions), 2)
        self.assertIn("name", descriptions[0])
        self.assertIn("description", descriptions[0])

    def test_execute_tool(self):
        """Test executing a tool through registry."""
        self.registry.register(CalculatorTool())

        result = self.registry.execute_tool("calculator", expression="2 + 3")
        self.assertEqual(result, 5.0)

    def test_get_unknown_tool_raises_error(self):
        """Test that getting unknown tool raises error."""
        with self.assertRaises(ValueError):
            self.registry.get_tool("unknown")

    def test_execute_unknown_tool_raises_error(self):
        """Test that executing unknown tool raises error."""
        with self.assertRaises(ValueError):
            self.registry.execute_tool("unknown")


class TestDefaultTools(unittest.TestCase):
    """Test cases for default tools."""

    def test_get_default_tools(self):
        """Test getting default tools."""
        registry = get_default_tools()

        tools = registry.get_all_tools()
        self.assertGreaterEqual(len(tools), 3)

        # Check that default tools are registered
        tool_names = [tool.name for tool in tools]
        self.assertIn("calculator", tool_names)
        self.assertIn("search", tool_names)
        self.assertIn("get_fact", tool_names)


if __name__ == "__main__":
    unittest.main()
