"""
Plan synthesizer using Sonnet 4.6 to generate pseudocode plans.
"""

import json
import os
from typing import List, Dict, Any
from .utils import get_bedrock_client, call_bedrock_model, extract_text_from_response, get_token_usage, SONNET_MODEL_ID


class PlanSynthesizer:
    """
    Synthesizes pseudocode execution plans from user queries and tool descriptions.
    Uses Sonnet 4.6 via Bedrock to generate structured plans.
    """

    def __init__(self, client=None):
        """
        Initialize the plan synthesizer.

        Args:
            client: Optional Bedrock client (for testing)
        """
        self.client = client or get_bedrock_client()
        self.model_id = SONNET_MODEL_ID

    def synthesize_plan(
        self,
        query: str,
        tools: List[Dict[str, Any]],
        save_path: str = None
    ) -> Dict[str, Any]:
        """
        Generate a pseudocode plan for the given query.

        Args:
            query: User's query/task
            tools: List of available tool descriptions
            save_path: Optional path to save the plan

        Returns:
            Dictionary with 'plan', 'usage', and 'raw_response' fields
        """
        system_prompt = self._build_system_prompt(tools)
        user_message = self._build_user_message(query)

        messages = [
            {
                "role": "user",
                "content": user_message
            }
        ]

        response = call_bedrock_model(
            client=self.client,
            model_id=self.model_id,
            messages=messages,
            system=system_prompt,
            max_tokens=4096,
            temperature=0.7
        )

        plan_text = extract_text_from_response(response)
        usage = get_token_usage(response)

        # Extract pseudocode from response (look for code blocks)
        plan = self._extract_pseudocode(plan_text)

        result = {
            "plan": plan,
            "usage": usage,
            "raw_response": plan_text
        }

        # Save plan if path provided
        if save_path:
            self._save_plan(result, save_path)

        return result

    def _build_system_prompt(self, tools: List[Dict[str, Any]]) -> str:
        """Build the system prompt for plan synthesis."""
        tools_json = json.dumps(tools, indent=2)

        return f"""You are a planning agent that generates executable pseudocode plans.

Given a user query and available tools, generate a step-by-step pseudocode plan that:
1. Uses Python-like syntax
2. Includes control flow (if/else, loops) where appropriate
3. Assigns results to variables for later use
4. Has BOUNDED loops - every loop MUST have max_iterations parameter

Available tools:
{tools_json}

CRITICAL RULES:
- Every loop MUST have max_iterations specified (no unbounded loops)
- Use Python-like syntax: if/elif/else, for/while with max_iterations
- Assign tool results to variables: result = tool_name(params)
- Use variables in later steps
- Include comments for clarity
- Return the final answer in a variable called 'answer'
- Do NOT use method calls like list.append() - use list concatenation instead: items = items + [item]

Example format:
```python
# Step 1: Search for information
search_result = search(query="Python programming")

# Step 2: Process results with iteration
items = []
for i in range(max_iterations=3):
    item = process_item(search_result, index=i)
    items = items + [item]

# Step 3: Conditional logic
if len(items) > 0:
    answer = summarize(items)
else:
    answer = "No results found"
```

Generate ONLY the pseudocode plan wrapped in ```python blocks. No additional explanation."""

    def _build_user_message(self, query: str) -> str:
        """Build the user message."""
        return f"""Generate a pseudocode plan for this task:

{query}

Remember: All loops must have max_iterations parameter!"""

    def _extract_pseudocode(self, text: str) -> str:
        """Extract pseudocode from the response."""
        # Look for code blocks
        if "```python" in text:
            start = text.find("```python") + len("```python")
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()

        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()

        # If no code blocks, return the whole text
        return text.strip()

    def _save_plan(self, result: Dict[str, Any], path: str) -> None:
        """Save the plan to disk."""
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, 'w') as f:
            f.write("# Generated Plan\n\n")
            f.write("## Pseudocode\n\n")
            f.write("```python\n")
            f.write(result["plan"])
            f.write("\n```\n\n")
            f.write(f"## Token Usage\n\n")
            f.write(f"- Input tokens: {result['usage']['input_tokens']}\n")
            f.write(f"- Output tokens: {result['usage']['output_tokens']}\n")
            f.write(f"- Total tokens: {result['usage']['input_tokens'] + result['usage']['output_tokens']}\n")
