"""
Utility functions for Bedrock API interactions.
"""

import json
import logging
import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any, List, Optional

# Set up logging
logger = logging.getLogger(__name__)


# Model IDs
SONNET_MODEL_ID = "us.anthropic.claude-sonnet-4-6-20251001-v2:0"
HAIKU_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
BEDROCK_REGION = "us-east-1"


def get_bedrock_client():
    """Create and return a Bedrock runtime client."""
    return boto3.client(
        service_name="bedrock-runtime",
        region_name=BEDROCK_REGION
    )


def call_bedrock_model(
    client,
    model_id: str,
    messages: List[Dict[str, Any]],
    system: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 1.0
) -> Dict[str, Any]:
    """
    Call a Bedrock model using the Messages API format.

    Args:
        client: Bedrock runtime client
        model_id: Model ID to use
        messages: List of message dictionaries with 'role' and 'content'
        system: Optional system prompt
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature

    Returns:
        Response dictionary with 'content', 'stop_reason', and 'usage' fields
    """
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature
    }

    if system:
        request_body["system"] = system

    try:
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body)
        )

        response_body = json.loads(response["body"].read())
        return response_body
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        logger.error(f"Bedrock API error: {error_code} - {error_message}")
        raise RuntimeError(f"Bedrock API call failed: {error_code} - {error_message}") from e
    except Exception as e:
        logger.error(f"Unexpected error calling Bedrock API: {str(e)}")
        raise RuntimeError(f"Unexpected error calling Bedrock API: {str(e)}") from e


def extract_text_from_response(response: Dict[str, Any]) -> str:
    """
    Extract text content from a Bedrock response.

    Args:
        response: Response dictionary from call_bedrock_model

    Returns:
        Extracted text content
    """
    content = response.get("content", [])
    if not content:
        return ""

    # Content is a list of content blocks
    text_parts = []
    for block in content:
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))

    return "".join(text_parts)


def get_token_usage(response: Dict[str, Any]) -> Dict[str, int]:
    """
    Extract token usage from a Bedrock response.

    Args:
        response: Response dictionary from call_bedrock_model

    Returns:
        Dictionary with 'input_tokens' and 'output_tokens'
    """
    usage = response.get("usage", {})
    return {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0)
    }
