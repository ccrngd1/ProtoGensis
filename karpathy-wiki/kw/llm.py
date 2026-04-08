"""LLM integration using AWS Bedrock."""

import json
from typing import Optional, List, Dict, Any
import boto3
from botocore.exceptions import ClientError


class BedrockLLM:
    """AWS Bedrock client for Claude."""

    def __init__(
        self,
        model: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
        region: str = "us-east-1",
        max_tokens: int = 4096,
        temperature: float = 1.0,
    ):
        """Initialize Bedrock client.

        Args:
            model: Model identifier
            region: AWS region
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
        """
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        self.client = boto3.client("bedrock-runtime", region_name=region)

    def invoke(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Invoke the model with a system prompt and messages.

        Args:
            system: System prompt
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Override default max_tokens
            temperature: Override default temperature

        Returns:
            Model response text

        Raises:
            RuntimeError: If the API call fails
        """
        try:
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "system": system,
                "messages": messages,
                "max_tokens": max_tokens or self.max_tokens,
                "temperature": temperature if temperature is not None else self.temperature,
            }

            response = self.client.invoke_model(
                modelId=self.model,
                body=json.dumps(request_body),
            )

            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]

        except ClientError as e:
            raise RuntimeError(f"Bedrock API error: {e}") from e
        except (KeyError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Failed to parse Bedrock response: {e}") from e

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Simple completion with a single prompt.

        Args:
            prompt: User prompt
            system: Optional system prompt
            max_tokens: Override default max_tokens
            temperature: Override default temperature

        Returns:
            Model response text
        """
        messages = [{"role": "user", "content": prompt}]
        return self.invoke(
            system=system or "",
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )


# System prompts for different tasks

COMPILATION_SYSTEM = """You are a knowledge compiler. Your task is to transform raw source material into structured wiki articles in markdown format.

Guidelines:
- Create well-structured, focused articles from the source material
- Use [[wikilink]] syntax for cross-references to related concepts
- Include YAML frontmatter with: title, tags, created, sources
- Break complex sources into multiple focused articles if needed
- Add a "See Also" section with [[wikilinks]] to related topics
- Add a "Sources" section listing the original materials
- Write in clear, encyclopedic style
- Extract key concepts, facts, and relationships
- Maintain objectivity and accuracy

Output format: One or more complete markdown articles with frontmatter."""

QUERY_SYSTEM = """You are a knowledge base navigator. Your task is to:

1. Read the wiki index to understand available articles
2. Navigate to relevant articles to gather information
3. Synthesize a comprehensive answer to the user's question
4. Produce a new wiki article capturing the Q&A

Guidelines:
- Start by examining the index
- Follow [[wikilinks]] to relevant articles
- Combine information from multiple articles when needed
- Provide accurate, well-sourced answers
- Create an article that would be useful for future similar queries
- Include cross-references to the articles you consulted

Output format: A complete markdown article answering the question, with frontmatter."""

HEALTH_CHECK_SYSTEM = """You are a knowledge base auditor. Review the wiki for:

1. Contradictions: Conflicting information across articles
2. Coverage gaps: Missing articles on related topics
3. Outdated claims: Information that may be stale
4. Broken wikilinks: References to non-existent articles
5. Redundancy: Overlapping articles that should be merged

For each issue found:
- Type: contradiction | gap | outdated | broken_link | redundancy
- Severity: high | medium | low
- Affected articles: List of article paths
- Description: What the issue is
- Recommendation: Suggested action

Output format: JSON array of issues."""

INDEX_UPDATE_SYSTEM = """You are a wiki index maintainer. Update the index.md file to:

1. List all articles in logical categories
2. Provide one-sentence summaries for each article
3. Maintain a table of contents structure
4. Keep it concise and navigable

The index is the entry point for LLM navigation. Make it useful.

Output format: Complete index.md markdown file."""
