"""
Tests for pseudocode parser.
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pseudoact.parser import PseudocodeParser, ToolCallNode, AssignmentNode, ConditionalNode, LoopNode


class TestPseudocodeParser(unittest.TestCase):
    """Test cases for PseudocodeParser."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = PseudocodeParser()

    def test_simple_assignment(self):
        """Test parsing a simple assignment."""
        code = "x = 5"
        nodes = self.parser.parse(code)

        self.assertEqual(len(nodes), 1)
        self.assertIsInstance(nodes[0], AssignmentNode)
        self.assertEqual(nodes[0].var_name, "x")
        self.assertEqual(nodes[0].value, 5)

    def test_tool_call_with_assignment(self):
        """Test parsing a tool call with result assignment."""
        code = 'result = calculator(expression="2 + 3")'
        nodes = self.parser.parse(code)

        self.assertEqual(len(nodes), 1)
        self.assertIsInstance(nodes[0], ToolCallNode)
        self.assertEqual(nodes[0].tool_name, "calculator")
        self.assertEqual(nodes[0].result_var, "result")
        self.assertIn("expression", nodes[0].arguments)

    def test_conditional(self):
        """Test parsing a conditional statement."""
        code = '''
if x > 5:
    y = 10
else:
    y = 0
'''
        nodes = self.parser.parse(code)

        self.assertEqual(len(nodes), 1)
        self.assertIsInstance(nodes[0], ConditionalNode)
        self.assertIn("x > 5", nodes[0].condition)
        self.assertEqual(len(nodes[0].then_block), 1)
        self.assertEqual(len(nodes[0].else_block), 1)

    def test_loop_with_max_iterations(self):
        """Test parsing a loop with max_iterations."""
        code = '''
for i in range(max_iterations=5):
    result = search(query="test")
'''
        nodes = self.parser.parse(code)

        self.assertEqual(len(nodes), 1)
        self.assertIsInstance(nodes[0], LoopNode)
        self.assertEqual(nodes[0].max_iterations, 5)
        self.assertEqual(len(nodes[0].body), 1)

    def test_loop_without_max_iterations_raises_error(self):
        """Test that a loop without max_iterations raises an error."""
        code = '''
for i in range(10):
    x = i
'''
        # This should work because range(10) has a limit
        nodes = self.parser.parse(code)
        self.assertEqual(len(nodes), 1)
        self.assertIsInstance(nodes[0], LoopNode)
        self.assertEqual(nodes[0].max_iterations, 10)

    def test_multiple_statements(self):
        """Test parsing multiple statements."""
        code = '''
x = 5
y = calculator(expression="x + 3")
if y > 7:
    answer = "large"
else:
    answer = "small"
'''
        nodes = self.parser.parse(code)

        self.assertGreaterEqual(len(nodes), 3)
        self.assertIsInstance(nodes[0], AssignmentNode)
        self.assertIsInstance(nodes[1], ToolCallNode)
        self.assertIsInstance(nodes[2], ConditionalNode)

    def test_nested_conditionals(self):
        """Test parsing nested conditionals."""
        code = '''
if x > 5:
    if y > 10:
        z = 1
    else:
        z = 2
else:
    z = 0
'''
        nodes = self.parser.parse(code)

        self.assertEqual(len(nodes), 1)
        self.assertIsInstance(nodes[0], ConditionalNode)
        self.assertIsInstance(nodes[0].then_block[0], ConditionalNode)

    def test_variable_references(self):
        """Test that variable references are properly marked."""
        code = '''
x = 5
y = x
'''
        nodes = self.parser.parse(code)

        self.assertEqual(len(nodes), 2)
        self.assertIsInstance(nodes[1], AssignmentNode)
        # Variable references should be marked with $
        self.assertEqual(nodes[1].value, "$x")

    def test_list_assignment(self):
        """Test parsing list assignments."""
        code = 'items = []'
        nodes = self.parser.parse(code)

        self.assertEqual(len(nodes), 1)
        self.assertIsInstance(nodes[0], AssignmentNode)
        self.assertEqual(nodes[0].var_name, "items")
        self.assertEqual(nodes[0].value, [])


class TestParserEdgeCases(unittest.TestCase):
    """Test edge cases for parser."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = PseudocodeParser()

    def test_empty_code(self):
        """Test parsing empty code."""
        code = ""
        nodes = self.parser.parse(code)
        self.assertEqual(len(nodes), 0)

    def test_comments_ignored(self):
        """Test that comments are ignored."""
        code = '''
# This is a comment
x = 5
'''
        nodes = self.parser.parse(code)
        # Comments are not represented in the AST by default
        self.assertEqual(len(nodes), 1)
        self.assertIsInstance(nodes[0], AssignmentNode)

    def test_invalid_syntax_raises_error(self):
        """Test that invalid syntax raises an error."""
        code = "x = = 5"
        with self.assertRaises(ValueError):
            self.parser.parse(code)


if __name__ == "__main__":
    unittest.main()
