#!/usr/bin/env python3
"""
Test script to verify bearer token authentication works.
"""

import os
import sys
from moa import BedrockClient


def test_bearer_token():
    """Test that bearer token is set and client initializes."""
    print("=" * 60)
    print("Bearer Token Authentication Test")
    print("=" * 60)

    # Check environment variable
    token = os.environ.get('AWS_BEARER_TOKEN_BEDROCK')

    if not token:
        print("\n❌ FAILED: AWS_BEARER_TOKEN_BEDROCK not set")
        print("\nTo fix:")
        print("  export AWS_BEARER_TOKEN_BEDROCK=your_bearer_token_here")
        return False

    print(f"\n✓ Bearer token is set (length: {len(token)} chars)")

    # Try to initialize client
    try:
        client = BedrockClient()
        print("✓ BedrockClient initialized successfully")
        print(f"✓ Region: {client.client.region}")
        print(f"✓ Rate limit: {client.client.min_delay}s between calls")
        print("\n" + "=" * 60)
        print("✅ Authentication check PASSED")
        print("=" * 60)
        print("\nReady to run live Bedrock API calls!")
        return True

    except Exception as e:
        print(f"\n❌ FAILED: Could not initialize client: {e}")
        return False


if __name__ == "__main__":
    success = test_bearer_token()
    sys.exit(0 if success else 1)
