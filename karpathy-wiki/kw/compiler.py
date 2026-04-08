"""Compilation engine for transforming raw sources into wiki articles."""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from .llm import BedrockLLM, COMPILATION_SYSTEM, INDEX_UPDATE_SYSTEM
from .db import Database
from .ingestion import Ingester
from .config import Config


class Compiler:
    """Compile raw sources into structured wiki articles."""

    def __init__(self, config: Config, db: Database, llm: BedrockLLM):
        """Initialize compiler.

        Args:
            config: Configuration object
            db: Database connection
            llm: LLM client
        """
        self.config = config
        self.db = db
        self.llm = llm
        self.ingester = Ingester(config.raw_dir)

        # Ensure wiki directory exists
        self.config.wiki_dir.mkdir(parents=True, exist_ok=True)

    def compile_source(self, source_id: int) -> List[int]:
        """Compile a single source into wiki articles.

        Args:
            source_id: Source database ID

        Returns:
            List of article IDs created
        """
        # Get source info
        source = self.db.get_source(source_id)
        if not source:
            raise ValueError(f"Source {source_id} not found")

        # Read source content
        source_path = Path(source["path"])
        content = self.ingester.read_source(source_path)

        # Build compilation prompt
        prompt = self._build_compilation_prompt(source, content)

        # Call LLM to compile
        try:
            response = self.llm.complete(prompt, system=COMPILATION_SYSTEM)

            # Parse response into articles
            articles = self._parse_articles(response, source)

            # Save articles
            article_ids = []
            for article_data in articles:
                article_id = self._save_article(article_data, source_id)
                article_ids.append(article_id)

            # Update source status
            self.db.update_source_status(
                source_id, "compiled", datetime.utcnow().isoformat()
            )

            return article_ids

        except Exception as e:
            # Mark as failed
            self.db.update_source_status(source_id, "failed")
            raise RuntimeError(f"Compilation failed: {e}") from e

    def compile_all_pending(self) -> Dict[str, Any]:
        """Compile all pending sources.

        Returns:
            Statistics dict with counts
        """
        pending = self.db.get_pending_sources()
        results = {"success": 0, "failed": 0, "articles_created": 0}

        for source in pending:
            try:
                article_ids = self.compile_source(source["id"])
                results["success"] += 1
                results["articles_created"] += len(article_ids)
            except Exception:
                results["failed"] += 1

        # Update index if auto-update enabled
        if self.config.get("compile.auto_index_update", True):
            self.update_index()

        return results

    def _build_compilation_prompt(self, source: Dict[str, Any], content: str) -> str:
        """Build the compilation prompt.

        Args:
            source: Source metadata dict
            content: Source content

        Returns:
            Formatted prompt
        """
        source_info = f"""Source Information:
- Type: {source['source_type']}
- Path: {source['path']}
"""
        if source.get("original_url"):
            source_info += f"- Original URL: {source['original_url']}\n"

        prompt = f"""{source_info}

Source Content:
{content}

---

Compile this source material into one or more focused wiki articles. Each article should:
- Have YAML frontmatter (title, tags, created, sources)
- Use [[wikilink]] syntax for cross-references
- Include "See Also" and "Sources" sections
- Be well-structured and encyclopedic

If the source covers multiple distinct topics, create separate articles.

Output each article separated by "--- ARTICLE ---" markers."""

        return prompt

    def _parse_articles(
        self, response: str, source: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Parse LLM response into article data.

        Args:
            response: LLM response text
            source: Source metadata

        Returns:
            List of article data dicts
        """
        # Split by article marker
        article_texts = re.split(r"---\s*ARTICLE\s*---", response)

        articles = []
        for idx, text in enumerate(article_texts):
            text = text.strip()
            if not text:
                continue

            # Extract frontmatter
            frontmatter = {}
            content = text

            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    frontmatter_text = parts[1]
                    content = parts[2].strip()

                    # Parse simple YAML
                    for line in frontmatter_text.strip().split("\n"):
                        if ":" in line:
                            key, value = line.split(":", 1)
                            frontmatter[key.strip()] = value.strip()

            # Extract title
            title = frontmatter.get("title", f"Article from {source['path']} ({idx + 1})")

            # Generate filename
            safe_title = re.sub(r"[^\w\s-]", "", title.lower())
            safe_title = re.sub(r"[-\s]+", "-", safe_title)
            filename = f"{safe_title}.md"

            # Extract tags
            tags_str = frontmatter.get("tags", "")
            tags = [t.strip() for t in tags_str.split(",") if t.strip()]

            # Word count
            word_count = len(content.split())

            articles.append(
                {
                    "filename": filename,
                    "title": title,
                    "content": text,  # Full content with frontmatter
                    "tags": tags,
                    "word_count": word_count,
                }
            )

        return articles

    def _save_article(self, article_data: Dict[str, Any], source_id: int) -> int:
        """Save an article to the wiki.

        Args:
            article_data: Article data dict
            source_id: Source database ID

        Returns:
            Article database ID
        """
        # Determine file path
        article_path = self.config.wiki_dir / article_data["filename"]

        # Handle duplicates
        counter = 1
        while article_path.exists():
            stem = article_path.stem
            article_path = self.config.wiki_dir / f"{stem}-{counter}.md"
            counter += 1

        # Write article
        with open(article_path, "w", encoding="utf-8") as f:
            f.write(article_data["content"])

        # Add to database
        relative_path = str(article_path.relative_to(self.config.kb_root))
        article_id = self.db.add_article(
            path=relative_path,
            title=article_data["title"],
            summary=None,  # Could extract first paragraph
            tags=article_data["tags"],
            word_count=article_data["word_count"],
        )

        # Link to source
        self.db.link_source_to_article(source_id, article_id)

        return article_id

    def update_index(self):
        """Update the wiki index with all articles."""
        # Get all articles
        articles = self.db.get_all_articles()

        # Build index prompt
        article_list = []
        for article in articles:
            tags_str = f" [{article['tags']}]" if article.get("tags") else ""
            article_list.append(f"- {article['title']}{tags_str} ({article['path']})")

        prompt = f"""Create a wiki index.md that organizes these articles:

{chr(10).join(article_list)}

The index should:
- Group articles by logical categories
- Provide one-sentence summaries for each article
- Use [[wikilink]] syntax
- Include a table of contents
- Be navigable and useful for LLM exploration

Output the complete index.md file."""

        try:
            response = self.llm.complete(prompt, system=INDEX_UPDATE_SYSTEM)

            # Save index
            with open(self.config.index_path, "w", encoding="utf-8") as f:
                f.write(response)

        except Exception as e:
            # Non-fatal - log but don't fail
            print(f"Warning: Failed to update index: {e}")

    def get_index_content(self) -> Optional[str]:
        """Get the current index content.

        Returns:
            Index content or None if it doesn't exist
        """
        if self.config.index_path.exists():
            with open(self.config.index_path, "r", encoding="utf-8") as f:
                return f.read()
        return None
