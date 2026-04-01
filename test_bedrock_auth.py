#!/usr/bin/env python3
"""Test Bedrock authentication with a simple Haiku call."""

import os
import json
import requests
import time

def test_bedrock_haiku():
    """Test Bedrock API with Claude Haiku."""

    # Get token from environment
    token = os.environ.get('AWS_BEARER_TOKEN_BEDROCK')
    if not token:
        print("ERROR: AWS_BEARER_TOKEN_BEDROCK environment variable not set")
        return False

    print(f"✓ Token found (length: {len(token)})")

    # Try different model IDs
    region = "us-east-1"
    model_ids = [
        "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "anthropic.claude-haiku-4-5-20251001-v1:0",
        "us.anthropic.claude-sonnet-4-6",
        "anthropic.claude-3-5-haiku-20241022-v1:0"
    ]

    # Request body
    body = {
        "messages": [
            {
                "role": "user",
                "content": [{"text": "Say 'Hello from Bedrock!' in exactly 5 words."}]
            }
        ],
        "inferenceConfig": {
            "maxTokens": 100,
            "temperature": 0.7
        }
    }

    for model_id in model_ids:
        url = f"https://bedrock-runtime.{region}.amazonaws.com/model/{model_id}/converse"

        # Headers
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        print(f"\nTesting Model: {model_id}")
        print(f"Endpoint: {url}")

        try:
            start_time = time.time()
            response = requests.post(url, headers=headers, json=body, timeout=30)
            latency_ms = int((time.time() - start_time) * 1000)

            print(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                # Extract response text
                content = data.get('output', {}).get('message', {}).get('content', [])
                response_text = content[0].get('text', '') if content else ''

                # Extract token usage
                usage = data.get('usage', {})
                input_tokens = usage.get('inputTokens', 0)
                output_tokens = usage.get('outputTokens', 0)

                print(f"\n✓ SUCCESS with model: {model_id}")
                print(f"Response: {response_text}")
                print(f"Input tokens: {input_tokens}")
                print(f"Output tokens: {output_tokens}")
                print(f"Latency: {latency_ms}ms")

                return True
            else:
                print(f"✗ Failed: {response.text}")
                print(f"Trying next model...")
                time.sleep(1)

        except Exception as e:
            print(f"✗ Exception: {str(e)}")
            print(f"Trying next model...")
            time.sleep(1)

    print("\n✗ All models failed!")
    return False

if __name__ == "__main__":
    success = test_bedrock_haiku()
    exit(0 if success else 1)
