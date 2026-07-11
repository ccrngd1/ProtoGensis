"""Tests for memory file parsers."""

import pytest
import json
from pathlib import Path
from memoryguard.parsers import parse_markdown_memory, parse_json_memory


class TestMarkdownParser:
    """Tests for Markdown memory parser."""

    def test_parse_frontmatter_format(self, tmp_path):
        content = """---
name: test-memory
description: Test description
metadata:
  type: user
---
This is the body content"""

        file_path = tmp_path / "test.md"
        file_path.write_text(content)

        entries = parse_markdown_memory(str(file_path))

        assert len(entries) == 1
        assert entries[0]["name"] == "test-memory"
        assert entries[0]["description"] == "Test description"
        assert "This is the body content" in entries[0]["content"]

    def test_parse_multiple_entries(self, tmp_path):
        content = """---
name: entry1
description: First entry
---
Body 1

---
name: entry2
description: Second entry
---
Body 2"""

        file_path = tmp_path / "test.md"
        file_path.write_text(content)

        entries = parse_markdown_memory(str(file_path))

        assert len(entries) == 2
        assert entries[0]["name"] == "entry1"
        assert entries[1]["name"] == "entry2"

    def test_parse_simple_list_format(self, tmp_path):
        content = """# Memory Index
- [User Role](user.md) - Backend engineer
- [Feedback](feedback.md) - Prefers tests"""

        file_path = tmp_path / "test.md"
        file_path.write_text(content)

        entries = parse_markdown_memory(str(file_path))

        assert len(entries) >= 2


class TestJSONParser:
    """Tests for JSON memory parser."""

    def test_parse_array_format(self, tmp_path):
        data = [
            {"name": "entry1", "content": "Content 1"},
            {"name": "entry2", "content": "Content 2"}
        ]

        file_path = tmp_path / "test.json"
        file_path.write_text(json.dumps(data))

        entries = parse_json_memory(str(file_path))

        assert len(entries) == 2
        assert entries[0]["name"] == "entry1"

    def test_parse_object_with_memories_key(self, tmp_path):
        data = {
            "memories": [
                {"name": "entry1", "content": "Content 1"}
            ]
        }

        file_path = tmp_path / "test.json"
        file_path.write_text(json.dumps(data))

        entries = parse_json_memory(str(file_path))

        assert len(entries) == 1
        assert entries[0]["name"] == "entry1"
