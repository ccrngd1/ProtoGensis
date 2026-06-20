"""Frontier model escalation via AWS Bedrock."""

import sys
import json
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod

from needleroute.config import EscalationConfig
from needleroute.schemas import MCPTool, EscalationRequest, EscalationResponse


class EscalationProvider(ABC):
    """Abstract interface for frontier model escalation."""

    @abstractmethod
    async def escalate(self, request: EscalationRequest) -> EscalationResponse:
        """
        Escalate tool selection to frontier model.

        Args:
            request: Escalation request with query and available tools

        Returns:
            EscalationResponse with selected tool and arguments
        """
        pass


class BedrockEscalationProvider(EscalationProvider):
    """AWS Bedrock escalation provider (Claude Haiku 4.5)."""

    def __init__(self, config: EscalationConfig):
        """
        Initialize Bedrock client.

        Args:
            config: Escalation configuration
        """
        self.config = config
        self._client = None
        self._available = False

        self._try_init_client()

    def _try_init_client(self) -> None:
        """Try to initialize Bedrock client."""
        try:
            import boto3

            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self.config.region
            )
            self._available = True
            print("Bedrock client initialized successfully", file=sys.stderr)

        except ImportError:
            print("Warning: boto3 not available, escalation disabled", file=sys.stderr)
            self._available = False

        except Exception as e:
            print(f"Warning: Failed to initialize Bedrock client: {e}", file=sys.stderr)
            self._available = False

    def _build_prompt(self, request: EscalationRequest) -> str:
        """Build prompt for frontier model."""
        # Format tools as JSON
        tools_json = []
        for tool in request.available_tools:
            tools_json.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema
            })

        tools_str = json.dumps(tools_json, indent=2)

        prompt = f"""You are a tool selection assistant. Given a user query and a list of available tools, select the most appropriate tool and generate the correct arguments.

User Query:
{request.query}

Available Tools:
{tools_str}

Respond with a JSON object containing:
- "tool": the name of the selected tool
- "arguments": a dictionary of arguments for the tool
- "reasoning": brief explanation of why this tool was selected

Example response:
{{
  "tool": "read_file",
  "arguments": {{"path": "/etc/hosts"}},
  "reasoning": "User wants to read a file, so read_file is appropriate"
}}

Your response (JSON only):"""

        return prompt

    async def escalate(self, request: EscalationRequest) -> EscalationResponse:
        """Escalate to Bedrock Claude Haiku."""
        if not self._available:
            # Fallback: return first tool with empty arguments
            return EscalationResponse(
                selected_tool=request.available_tools[0].name if request.available_tools else "error",
                arguments={},
                reasoning="Bedrock unavailable, returning first tool",
                model_used="fallback",
                tokens_used=0
            )

        try:
            # Build prompt
            prompt = self._build_prompt(request)

            # Call Bedrock
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }

            response = self._client.invoke_model(
                modelId=self.config.model,
                body=json.dumps(request_body)
            )

            # Parse response
            response_body = json.loads(response["body"].read())
            content = response_body["content"][0]["text"]

            # Extract JSON from response (handle markdown code blocks)
            json_str = content.strip()
            if json_str.startswith("```"):
                # Remove markdown code block
                lines = json_str.split("\n")
                json_str = "\n".join(lines[1:-1])

            result = json.loads(json_str)

            # Extract tokens used
            usage = response_body.get("usage", {})
            tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

            return EscalationResponse(
                selected_tool=result.get("tool", "error"),
                arguments=result.get("arguments", {}),
                reasoning=result.get("reasoning"),
                model_used=self.config.model,
                tokens_used=tokens_used
            )

        except Exception as e:
            print(f"Error during Bedrock escalation: {e}", file=sys.stderr)
            # Fallback
            return EscalationResponse(
                selected_tool=request.available_tools[0].name if request.available_tools else "error",
                arguments={},
                reasoning=f"Escalation failed: {e}",
                model_used="fallback",
                tokens_used=0
            )


class MockEscalationProvider(EscalationProvider):
    """Mock escalation provider for testing."""

    def __init__(self, config: EscalationConfig):
        """Initialize mock provider."""
        self.config = config

    async def escalate(self, request: EscalationRequest) -> EscalationResponse:
        """Mock escalation: return first tool with empty arguments."""
        if not request.available_tools:
            return EscalationResponse(
                selected_tool="error",
                arguments={},
                reasoning="No tools available",
                model_used="mock",
                tokens_used=0
            )

        # Simple heuristic: pick first tool that matches keywords in query
        query_lower = request.query.lower()
        selected = request.available_tools[0]

        for tool in request.available_tools:
            if tool.name.lower() in query_lower:
                selected = tool
                break

        return EscalationResponse(
            selected_tool=selected.name,
            arguments={},
            reasoning=f"Mock escalation selected {selected.name}",
            model_used="mock",
            tokens_used=100
        )


def create_escalation_provider(config: EscalationConfig) -> EscalationProvider:
    """
    Factory function to create escalation provider.

    Args:
        config: Escalation configuration

    Returns:
        EscalationProvider instance
    """
    if config.provider == "bedrock":
        return BedrockEscalationProvider(config)
    elif config.provider == "mock":
        return MockEscalationProvider(config)
    else:
        raise ValueError(f"Unknown escalation provider: {config.provider}")
