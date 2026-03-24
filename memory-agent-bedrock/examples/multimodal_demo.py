#!/usr/bin/env python3
"""Demo script for multimodal ingestion (text, images, PDFs)."""

import requests
from pathlib import Path

API_URL = "http://localhost:8000"


def test_text_ingestion():
    """Test basic text ingestion."""
    print("\n1. Testing text ingestion...")
    response = requests.post(
        f"{API_URL}/ingest",
        json={
            "text": "Claude Haiku 4.5 now supports vision capabilities, allowing it to analyze images.",
            "source": "demo"
        }
    )
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Success: {data['summary']}")
    else:
        print(f"   ✗ Failed: {response.text}")


def test_file_upload(file_path: str):
    """Test file upload (image or PDF)."""
    file_path = Path(file_path)
    if not file_path.exists():
        print(f"   ✗ File not found: {file_path}")
        return

    print(f"\n2. Testing file upload: {file_path.name}")
    with open(file_path, "rb") as f:
        response = requests.post(
            f"{API_URL}/ingest/file",
            files={"file": (file_path.name, f, "application/octet-stream")}
        )

    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Success: {data['summary'][:100]}...")
        print(f"   Entities: {data['entities']}")
        print(f"   Topics: {data['topics']}")
    else:
        print(f"   ✗ Failed: {response.text}")


def test_query():
    """Test querying memories."""
    print("\n3. Testing query...")
    response = requests.get(
        f"{API_URL}/query",
        params={"q": "What have you learned from the images and documents?"}
    )
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Answer: {data['answer']}")
    else:
        print(f"   ✗ Failed: {response.text}")


def test_status():
    """Test status endpoint."""
    print("\n4. Checking status...")
    response = requests.get(f"{API_URL}/status")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Total memories: {data['memory_count']}")
        print(f"   ✓ Consolidations: {data['consolidation_count']}")
        print(f"   ✓ Unconsolidated: {data['unconsolidated_count']}")
    else:
        print(f"   ✗ Failed: {response.text}")


if __name__ == "__main__":
    print("=" * 60)
    print("Multimodal Memory Agent Demo")
    print("=" * 60)
    print("\nMake sure the API is running: uvicorn api.main:app --reload")
    print()

    # Test basic text
    test_text_ingestion()

    # Test file upload (provide your own test files)
    print("\nTo test file uploads, provide image or PDF paths:")
    print("Example usage:")
    print("  test_file_upload('path/to/image.png')")
    print("  test_file_upload('path/to/document.pdf')")

    # Test query
    test_query()

    # Test status
    test_status()

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)
