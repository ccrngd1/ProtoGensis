"""
Tests for plan executor with mocked Bedrock calls.
"""

import unittest
from unittest.mock import Mock, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pseudoact.executor import PlanExecutor
from pseudoact.parser import PseudocodeParser, ToolCallNode, AssignmentNode, ConditionalNode, LoopNode
from pseudoact.context import ExecutionContext
from pseudoact.tools import ToolRegistry, CalculatorTool


class TestPlanExecutor(unittest.TestCase):
    """Test cases for PlanExecutor."""

    def setUp(self):
        """Set up test fixtures."""
        self.tool_registry = ToolRegistry()
        self.tool_registry.register(CalculatorTool())

        # Mock Bedrock client
        self.mock_client = Mock()
        self.executor = PlanExecutor(self.tool_registry, client=self.mock_client)

    def test_execute_tool_call(self):
        """Test executing a tool call node."""
        context = ExecutionContext()
        node = ToolCallNode("calculator", {"expression": "2 + 3"}, result_var="result")

        self.executor._execute_tool_call(node, context)

        self.assertTrue(context.has("result"))
        self.assertEqual(context.get("result"), 5.0)

    def test_execute_assignment(self):
        """Test executing an assignment node."""
        context = ExecutionContext()
        node = AssignmentNode("x", 10)

        self.executor._execute_assignment(node, context)

        self.assertTrue(context.has("x"))
        self.assertEqual(context.get("x"), 10)

    def test_execute_conditional_true_branch(self):
        """Test executing a conditional with true condition."""
        context = ExecutionContext()
        context.set("x", 10)

        # Mock LLM response for condition evaluation
        self.mock_client.invoke_model = Mock(return_value={
            "body": Mock(read=Mock(return_value=b'{"content": [{"type": "text", "text": "true"}], "usage": {"input_tokens": 10, "output_tokens": 5}}'))
        })

        then_block = [AssignmentNode("y", 1)]
        else_block = [AssignmentNode("y", 0)]
        node = ConditionalNode("x > 5", then_block, else_block)

        self.executor._execute_conditional(node, context)

        # True branch should execute
        self.assertEqual(context.get("y"), 1)

    def test_execute_conditional_false_branch(self):
        """Test executing a conditional with false condition."""
        context = ExecutionContext()
        context.set("x", 3)

        # Mock LLM response for condition evaluation
        self.mock_client.invoke_model = Mock(return_value={
            "body": Mock(read=Mock(return_value=b'{"content": [{"type": "text", "text": "false"}], "usage": {"input_tokens": 10, "output_tokens": 5}}'))
        })

        then_block = [AssignmentNode("y", 1)]
        else_block = [AssignmentNode("y", 0)]
        node = ConditionalNode("x > 5", then_block, else_block)

        self.executor._execute_conditional(node, context)

        # False branch should execute
        self.assertEqual(context.get("y"), 0)

    def test_execute_loop(self):
        """Test executing a loop node."""
        context = ExecutionContext()

        # Mock LLM response for condition evaluation
        self.mock_client.invoke_model = Mock(return_value={
            "body": Mock(read=Mock(return_value=b'{"content": [{"type": "text", "text": "true"}], "usage": {"input_tokens": 10, "output_tokens": 5}}'))
        })

        body = [AssignmentNode("counter", 1)]
        node = LoopNode("for", "i in range(3)", body, max_iterations=3)

        iterations = self.executor._execute_loop(node, context)

        self.assertEqual(iterations, 3)

    def test_execute_plan_complete(self):
        """Test executing a complete plan."""
        parser = PseudocodeParser()
        code = '''
x = 5
result = calculator(expression="x + 3")
answer = result
'''
        nodes = parser.parse(code)

        result = self.executor.execute_plan(nodes)

        self.assertIn("result", result)
        self.assertIsNotNone(result["context"])
        self.assertIn("usage", result)

    def test_resolve_variable_references(self):
        """Test resolving variable references in arguments."""
        context = ExecutionContext()
        context.set("x", 10)

        arguments = {"value": "$x"}
        resolved = self.executor._resolve_arguments(arguments, context)

        self.assertEqual(resolved["value"], 10)

    def test_execution_history(self):
        """Test that execution history is recorded."""
        context = ExecutionContext()
        node = AssignmentNode("x", 5)

        self.executor._execute_assignment(node, context)

        history = context.get_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["step_type"], "assignment")


class TestExecutorEdgeCases(unittest.TestCase):
    """Test edge cases for executor."""

    def setUp(self):
        """Set up test fixtures."""
        self.tool_registry = ToolRegistry()
        self.tool_registry.register(CalculatorTool())
        self.mock_client = Mock()
        self.executor = PlanExecutor(self.tool_registry, client=self.mock_client)

    def test_execute_empty_plan(self):
        """Test executing an empty plan."""
        nodes = []
        result = self.executor.execute_plan(nodes)

        self.assertEqual(result["result"], "No answer variable found")

    def test_unknown_tool_raises_error(self):
        """Test that calling an unknown tool raises an error."""
        context = ExecutionContext()
        node = ToolCallNode("unknown_tool", {}, result_var="result")

        with self.assertRaises(ValueError):
            self.executor._execute_tool_call(node, context)

    def test_loop_respects_max_iterations(self):
        """Test that loops respect max_iterations bound."""
        context = ExecutionContext()

        # Mock LLM to always return true (infinite loop condition)
        self.mock_client.invoke_model = Mock(return_value={
            "body": Mock(read=Mock(return_value=b'{"content": [{"type": "text", "text": "true"}], "usage": {"input_tokens": 10, "output_tokens": 5}}'))
        })

        body = [AssignmentNode("x", 1)]
        node = LoopNode("while", "true", body, max_iterations=5)

        iterations = self.executor._execute_loop(node, context)

        # Should stop at max_iterations even though condition is always true
        self.assertEqual(iterations, 5)


if __name__ == "__main__":
    unittest.main()
