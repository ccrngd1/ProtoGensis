"""Parsers for different memory store formats."""

import json
import re
from typing import List, Dict, Any
from pathlib import Path


def parse_markdown_memory(file_path: str) -> List[Dict[str, Any]]:
    """
    Parse MEMORY.md style markdown files with frontmatter.

    Expected format:
    ---
    name: memory-name
    description: One line description
    metadata:
      type: user|feedback|project|reference
    ---
    Body content here
    """
    content = Path(file_path).read_text()
    entries = []

    file_pattern = r'---\n(.*?)\n---\n(.*?)(?=\n---\n|\Z)'
    matches = re.finditer(file_pattern, content, re.DOTALL)

    for idx, match in enumerate(matches):
        frontmatter_text = match.group(1)
        body = match.group(2).strip()

        entry = {"content": body}

        for line in frontmatter_text.split('\n'):
            if ':' in line and not line.startswith(' '):
                key, value = line.split(':', 1)
                entry[key.strip()] = value.strip()
            elif line.startswith('  ') and 'metadata' in entry:
                if not isinstance(entry['metadata'], dict):
                    entry['metadata'] = {}
                if ':' in line:
                    key, value = line.strip().split(':', 1)
                    entry['metadata'][key.strip()] = value.strip()

        if 'metadata' in entry and isinstance(entry['metadata'], str):
            entry['metadata'] = {}

        entries.append(entry)

    if not entries:
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        for idx, line in enumerate(lines):
            if line.startswith('- '):
                entries.append({
                    "name": f"item_{idx}",
                    "content": line[2:],
                    "metadata": {"type": "reference"}
                })

    return entries


def parse_json_memory(file_path: str) -> List[Dict[str, Any]]:
    """Parse JSON memory stores."""
    with open(file_path, 'r') as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    elif isinstance(data, dict) and "memories" in data:
        return data["memories"]
    elif isinstance(data, dict) and "entries" in data:
        return data["entries"]
    else:
        return [data]


def parse_memory_file(file_path: str) -> List[Dict[str, Any]]:
    """Auto-detect format and parse memory file."""
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Memory file not found: {file_path}")

    if path.suffix == '.json':
        return parse_json_memory(file_path)
    elif path.suffix == '.md':
        return parse_markdown_memory(file_path)
    else:
        try:
            return parse_json_memory(file_path)
        except json.JSONDecodeError:
            return parse_markdown_memory(file_path)
