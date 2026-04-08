"""Ingestion utilities for various source types."""

import shutil
from pathlib import Path
from typing import Tuple, Optional
import httpx
from PyPDF2 import PdfReader
import re


class Ingester:
    """Handle ingestion of various source types."""

    def __init__(self, raw_dir: Path):
        """Initialize ingester.

        Args:
            raw_dir: Path to raw/ directory
        """
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def ingest_file(self, file_path: str) -> Tuple[str, str, Optional[str]]:
        """Ingest a local file.

        Args:
            file_path: Path to the file to ingest

        Returns:
            Tuple of (relative_path, source_type, original_url)
        """
        source_path = Path(file_path)
        if not source_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Determine source type
        suffix = source_path.suffix.lower()
        if suffix == ".pdf":
            source_type = "pdf"
        elif suffix in [".md", ".markdown"]:
            source_type = "markdown"
        elif suffix == ".txt":
            source_type = "text"
        else:
            source_type = "unknown"

        # Copy to raw/ directory
        dest_path = self.raw_dir / source_path.name
        counter = 1
        while dest_path.exists():
            stem = source_path.stem
            dest_path = self.raw_dir / f"{stem}_{counter}{source_path.suffix}"
            counter += 1

        shutil.copy2(source_path, dest_path)

        return str(dest_path.relative_to(self.raw_dir.parent)), source_type, None

    def ingest_url(self, url: str) -> Tuple[str, str, str]:
        """Ingest content from a URL.

        Args:
            url: URL to fetch

        Returns:
            Tuple of (relative_path, source_type, original_url)
        """
        # Detect GitHub URLs
        if "github.com" in url:
            return self._ingest_github_url(url)

        # Fetch generic URL
        return self._ingest_generic_url(url)

    def _ingest_github_url(self, url: str) -> Tuple[str, str, str]:
        """Ingest a GitHub URL (repo, file, or issue).

        Args:
            url: GitHub URL

        Returns:
            Tuple of (relative_path, source_type, original_url)
        """
        # Simple GitHub URL handling - save the URL and metadata
        # In a real implementation, you might clone repos or fetch specific files

        # Extract info from URL
        safe_name = re.sub(r"[^\w\-.]", "_", url.split("github.com/")[-1])
        dest_path = self.raw_dir / f"{safe_name}.md"

        # Create a markdown file with the GitHub URL
        content = f"# GitHub Resource\n\nSource: {url}\n\nType: GitHub\n"

        # Try to fetch README or main page content
        try:
            response = httpx.get(url, follow_redirects=True, timeout=30.0)
            if response.status_code == 200:
                content += f"\n## Retrieved Content\n\n{response.text[:5000]}\n"
        except Exception:
            pass

        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(content)

        return str(dest_path.relative_to(self.raw_dir.parent)), "github", url

    def _ingest_generic_url(self, url: str) -> Tuple[str, str, str]:
        """Ingest a generic URL.

        Args:
            url: URL to fetch

        Returns:
            Tuple of (relative_path, source_type, original_url)
        """
        try:
            response = httpx.get(url, follow_redirects=True, timeout=30.0)
            response.raise_for_status()

            # Generate filename from URL
            safe_name = re.sub(r"[^\w\-.]", "_", url.split("://")[-1][:100])
            dest_path = self.raw_dir / f"{safe_name}.txt"

            counter = 1
            while dest_path.exists():
                dest_path = self.raw_dir / f"{safe_name}_{counter}.txt"
                counter += 1

            # Save content
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(f"Source: {url}\n\n")
                f.write(response.text)

            return str(dest_path.relative_to(self.raw_dir.parent)), "url", url

        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to fetch URL: {e}") from e

    def read_source(self, source_path: Path) -> str:
        """Read content from a source file.

        Args:
            source_path: Path to source file (relative to kb root)

        Returns:
            Text content of the source
        """
        full_path = source_path if source_path.is_absolute() else self.raw_dir.parent / source_path

        suffix = full_path.suffix.lower()

        if suffix == ".pdf":
            return self._read_pdf(full_path)
        elif suffix in [".md", ".markdown", ".txt"]:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            # Try to read as text
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                raise RuntimeError(f"Cannot read file {full_path}: {e}") from e

    def _read_pdf(self, pdf_path: Path) -> str:
        """Extract text from a PDF file.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Extracted text
        """
        try:
            reader = PdfReader(str(pdf_path))
            text_parts = []

            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                if text.strip():
                    text_parts.append(f"--- Page {page_num} ---\n{text}\n")

            return "\n".join(text_parts)

        except Exception as e:
            raise RuntimeError(f"Failed to read PDF {pdf_path}: {e}") from e


def detect_source_type(path: Path) -> str:
    """Detect the type of a source file.

    Args:
        path: Path to the source file

    Returns:
        Source type string
    """
    suffix = path.suffix.lower()

    type_map = {
        ".pdf": "pdf",
        ".md": "markdown",
        ".markdown": "markdown",
        ".txt": "text",
    }

    return type_map.get(suffix, "unknown")
