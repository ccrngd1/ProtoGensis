"""
Tests for plan synthesizer with mocked Bedrock calls.
"""

import unittest
from unittest.mock import Mock
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pseudoact.synthesizer import PlanSynthesizer


class TestPlanSynthesizer(unittest.TestCase):
    """Test cases for PlanSynthesizer."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.synthesizer = PlanSynthesizer(client=self.mock_client)

    def test_synthesize_plan_basic(self):
        """Test basic plan synthesis."""
        # Mock Bedrock response
        mock_plan = """```python
# Calculate result
result = calculator(expression="2 + 3")
answer = result
```"""

        self.mock_client.invoke_model = Mock(return_value={
            "body": Mock(read=Mock(return_value=json.dumps({
                "content": [{"type": "text", "text": mock_plan}],
                "usage": {"input_tokens": 100, "output_tokens": 50}
            }).encode()))
        })

        tools = [
            {
                "name": "calculator",
                "description": "Perform calculations",
                "parameters": {}
            }
        ]

        result = self.synthesizer.synthesize_plan(
            query="Calculate 2 + 3",
            tools=tools
        )

        self.assertIn("plan", result)
        self.assertIn("usage", result)
        self.assertIn("calculator", result["plan"])
        self.assertEqual(result["usage"]["input_tokens"], 100)
        self.assertEqual(result["usage"]["output_tokens"], 50)

    def test_extract_pseudocode_from_code_block(self):
        """Test extracting pseudocode from markdown code blocks."""
        text = """Here is the plan:

```python
x = 5
y = calculator(expression="x + 3")
answer = y
```

This completes the plan."""

        plan = self.synthesizer._extract_pseudocode(text)

        self.assertIn("x = 5", plan)
        self.assertIn("calculator", plan)
        self.assertNotIn("Here is the plan", plan)
        self.assertNotIn("```", plan)

    def test_extract_pseudocode_no_code_block(self):
        """Test extracting pseudocode when there's no code block."""
        text = "x = 5\ny = 10"

        plan = self.synthesizer._extract_pseudocode(text)

        self.assertEqual(plan, "x = 5\ny = 10")

    def test_build_system_prompt(self):
        """Test building the system prompt."""
        tools = [
            {
                "name": "calculator",
                "description": "Perform calculations",
                "parameters": {"type": "object"}
            }
        ]

        prompt = self.synthesizer._build_system_prompt(tools)

        self.assertIn("pseudocode", prompt.lower())
        self.assertIn("max_iterations", prompt)
        self.assertIn("calculator", prompt)

    def test_build_user_message(self):
        """Test building the user message."""
        query = "Calculate 2 + 3"

        message = self.synthesizer._build_user_message(query)

        self.assertIn(query, message)
        self.assertIn("max_iterations", message)

    def test_synthesize_with_save(self):
        """Test synthesizing and saving a plan."""
        mock_plan = "result = calculator(expression='2+3')\nanswer = result"

        self.mock_client.invoke_model = Mock(return_value={
            "body": Mock(read=Mock(return_value=json.dumps({
                "content": [{"type": "text", "text": mock_plan}],
                "usage": {"input_tokens": 100, "output_tokens": 50}
            }).encode()))
        })

        tools = [{"name": "calculator", "description": "Calculate", "parameters": {}}]

        # Use a temporary path
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            temp_path = f.name

        try:
            result = self.synthesizer.synthesize_plan(
                query="Calculate 2 + 3",
                tools=tools,
                save_path=temp_path
            )

            # Check that file was created
            self.assertTrue(os.path.exists(temp_path))

            # Read and verify content
            with open(temp_path, 'r') as f:
                content = f.read()
                self.assertIn("Generated Plan", content)
                self.assertIn("calculator", content)

        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestSynthesizerEdgeCases(unittest.TestCase):
    """Test edge cases for synthesizer."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.synthesizer = PlanSynthesizer(client=self.mock_client)

    def test_empty_response(self):
        """Test handling empty response from LLM."""
        self.mock_client.invoke_model = Mock(return_value={
            "body": Mock(read=Mock(return_value=json.dumps({
                "content": [],
                "usage": {"input_tokens": 10, "output_tokens": 0}
            }).encode()))
        })

        result = self.synthesizer.synthesize_plan(
            query="Test",
            tools=[]
        )

        self.assertEqual(result["plan"], "")

    def test_response_without_code_blocks(self):
        """Test handling response without code blocks."""
        plain_text = "result = calculator(expression='2+3')"

        self.mock_client.invoke_model = Mock(return_value={
            "body": Mock(read=Mock(return_value=json.dumps({
                "content": [{"type": "text", "text": plain_text}],
                "usage": {"input_tokens": 10, "output_tokens": 20}
            }).encode()))
        })

        result = self.synthesizer.synthesize_plan(
            query="Test",
            tools=[]
        )

        self.assertEqual(result["plan"], plain_text)


if __name__ == "__main__":
    unittest.main()
