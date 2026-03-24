"""Ingest Agent — converts raw text, images, or PDFs to structured Memory records."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from agents.bedrock_client import invoke, invoke_multimodal, load_image_as_base64
from agents.utils import parse_json
from memory.models import Memory
from memory.store import MemoryStore

logger = logging.getLogger(__name__)

SYSTEM = """You are a memory extraction assistant. Given a piece of text or an image, extract structured information.
Always respond with a single JSON object (no markdown fences) containing:
- summary: string (1-3 sentence distillation of what you see/read)
- entities: list of strings (people, places, organizations, products, concepts, objects in images)
- topics: list of strings (broad thematic categories, e.g. "machine learning", "personal finance")
- importance: float between 0.0 and 1.0 (how significant/noteworthy is this information)
"""

SUPPORTED_EXTENSIONS = {
    # Text
    ".txt", ".md", ".json", ".csv", ".log", ".yaml", ".yml",
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    # Documents
    ".pdf",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


class IngestAgent:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def ingest(self, text: str, source: str = "") -> Memory:
        """Extract structured memory from *text* and persist it."""
        prompt = f"Extract structured memory from the following text:\n\n{text}"
        try:
            raw = invoke(prompt, system=SYSTEM, max_tokens=1024)
            data = parse_json(raw)
        except Exception as exc:
            logger.warning("LLM extraction failed (%s); using fallback.", exc)
            data = {}

        # Clamp importance to valid range [0.0, 1.0] to handle LLM errors
        try:
            importance = float(data.get("importance", 0.5))
            importance = max(0.0, min(1.0, importance))
        except (ValueError, TypeError):
            importance = 0.5

        memory = Memory(
            summary=data.get("summary", text[:500]),
            entities=data.get("entities", []),
            topics=data.get("topics", []),
            importance=importance,
            source=source,
        )
        return self.store.add_memory(memory)

    def ingest_file(self, file_path: Path) -> Memory:
        """Extract structured memory from a file (text, image, or PDF).

        Args:
            file_path: Path to file

        Returns:
            Created Memory record

        Raises:
            ValueError: If file type is not supported
        """
        suffix = file_path.suffix.lower()

        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {suffix}")

        # Handle images
        if suffix in IMAGE_EXTENSIONS:
            return self._ingest_image(file_path)

        # Handle PDFs
        if suffix == ".pdf":
            return self._ingest_pdf(file_path)

        # Handle text files
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return self.ingest(text[:10000], source=file_path.name)  # Truncate if too long

    def _ingest_image(self, file_path: Path) -> Memory:
        """Extract structured memory from an image using Claude vision."""
        try:
            image_data, media_type = load_image_as_base64(file_path)

            # Build multimodal content
            content = [
                {"type": "text", "text": "Extract structured memory from this image. Describe what you see, identify any text, objects, people, or concepts."},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data
                    }
                }
            ]

            raw = invoke_multimodal(content, system=SYSTEM, max_tokens=1024)
            data = parse_json(raw)
        except Exception as exc:
            logger.warning("Image extraction failed (%s); using fallback.", exc)
            data = {"summary": f"Image: {file_path.name}"}

        # Clamp importance
        try:
            importance = float(data.get("importance", 0.5))
            importance = max(0.0, min(1.0, importance))
        except (ValueError, TypeError):
            importance = 0.5

        memory = Memory(
            summary=data.get("summary", f"Image: {file_path.name}"),
            entities=data.get("entities", []),
            topics=data.get("topics", ["image"]),
            importance=importance,
            source=file_path.name,
        )
        return self.store.add_memory(memory)

    def _ingest_pdf(self, file_path: Path) -> Memory:
        """Extract text from PDF and ingest it."""
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(file_path)
            text_parts = []
            for page in reader.pages[:20]:  # Limit to first 20 pages
                text_parts.append(page.extract_text())
            text = "\n".join(text_parts)

            # Truncate if too long
            text = text[:10000]

            return self.ingest(text, source=file_path.name)
        except ImportError:
            logger.error("PyPDF2 not installed. Install with: pip install PyPDF2")
            raise
        except Exception as exc:
            logger.warning("PDF extraction failed (%s); using fallback.", exc)
            memory = Memory(
                summary=f"PDF document: {file_path.name}",
                entities=[],
                topics=["document"],
                importance=0.5,
                source=file_path.name,
            )
            return self.store.add_memory(memory)
