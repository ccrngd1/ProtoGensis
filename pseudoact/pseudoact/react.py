"""
ReAct baseline implementation for comparison.
"""

import json
from typing import List, Dict, Any
from .tools import ToolRegistry
from .utils import get_bedrock_client, call_bedrock_model, extract_text_from_response, get_token_usage, SONNET_MODEL_ID


class ReActAgent:
    """
    ReAct (Reasoning + Acting) baseline agent.
    Uses iterative think-act-observe cycles.
    """

    def __init__(self, tool_registry: ToolRegistry, client=None, max_iterations: int = 10):
        """
        Initialize the ReAct agent.

        Args:
            tool_registry: Registry of available tools
            client: Optional Bedrock client (for testing)
            max_iterations: Maximum number of reasoning-action cycles
        """
        self.tool_registry = tool_registry
        self.client = client or get_bedrock_client()
        self.model_id = SONNET_MODEL_ID
        self.max_iterations = max_iterations

    def run(self, query: str) -> Dict[str, Any]:
        """
        Execute query using ReAct approach.

        Args:
            query: User's query/task

        Returns:
            Dictionary with 'result', 'history', and 'usage' fields
        """
        history = []
        total_usage = {"input_tokens": 0, "output_tokens": 0}

        system_prompt = self._build_system_prompt()
        conversation = []

        # Initial query
        conversation.append({
            "role": "user",
            "content": query
        })

        for iteration in range(self.max_iterations):
            # Get next action from model
            response = call_bedrock_model(
                client=self.client,
                model_id=self.model_id,
                messages=conversation,
                system=system_prompt,
                max_tokens=2048,
                temperature=0.7
            )

            assistant_message = extract_text_from_response(response)
            usage = get_token_usage(response)

            total_usage["input_tokens"] += usage["input_tokens"]
            total_usage["output_tokens"] += usage["output_tokens"]

            # Add assistant response to conversation
            conversation.append({
                "role": "assistant",
                "content": assistant_message
            })

            # Parse the response
            action = self._parse_response(assistant_message)
            history.append({
                "iteration": iteration + 1,
                "thought": action.get("thought", ""),
                "action": action.get("action", ""),
                "observation": ""
            })

            # Check if we have a final answer
            if action["type"] == "answer":
                return {
                    "result": action["content"],
                    "history": history,
                    "usage": total_usage,
                    "iterations": iteration + 1
                }

            # Execute the action
            if action["type"] == "tool":
                try:
                    tool_result = self.tool_registry.execute_tool(
                        action["tool_name"],
                        **action["arguments"]
                    )
                    observation = f"Observation: {tool_result}"
                except Exception as e:
                    observation = f"Error: {str(e)}"

                history[-1]["observation"] = observation

                # Add observation to conversation
                conversation.append({
                    "role": "user",
                    "content": observation
                })

        # Max iterations reached
        return {
            "result": "Max iterations reached without finding answer",
            "history": history,
            "usage": total_usage,
            "iterations": self.max_iterations
        }

    def _build_system_prompt(self) -> str:
        """Build the system prompt for ReAct."""
        tools_json = json.dumps(self.tool_registry.get_tool_descriptions(), indent=2)

        return f"""You are a helpful assistant that solves tasks using a ReAct (Reasoning + Acting) approach.

Available tools:
{tools_json}

For each step, you must:
1. Think about what to do next
2. Either call a tool OR provide a final answer

Format your response EXACTLY as:

Thought: [Your reasoning about what to do next]
Action: [tool_name]
Arguments: {{"param": "value"}}

OR, when you have the final answer:

Thought: [Your reasoning]
Answer: [Your final answer]

IMPORTANT:
- Always start with "Thought:"
- For tool calls, use "Action:" and "Arguments:"
- For final answer, use "Answer:"
- Only call one tool per response
"""

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse the model's response to extract thought, action, and arguments."""
        result = {
            "type": "unknown",
            "thought": "",
            "action": "",
            "content": ""
        }

        lines = response.strip().split("\n")

        for line in lines:
            line = line.strip()

            if line.startswith("Thought:"):
                result["thought"] = line[8:].strip()
            elif line.startswith("Action:"):
                result["type"] = "tool"
                result["action"] = line[7:].strip()
                result["tool_name"] = line[7:].strip()
            elif line.startswith("Arguments:"):
                try:
                    args_str = line[10:].strip()
                    result["arguments"] = json.loads(args_str)
                except json.JSONDecodeError:
                    result["arguments"] = {}
            elif line.startswith("Answer:"):
                result["type"] = "answer"
                result["content"] = line[7:].strip()

        return result
