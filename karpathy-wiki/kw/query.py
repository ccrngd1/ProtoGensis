"""Query engine for navigating the wiki and answering questions."""

import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from .llm import BedrockLLM, QUERY_SYSTEM
from .db import Database
from .config import Config


class QueryEngine:
    """Navigate wiki and answer questions."""

    def __init__(self, config: Config, db: Database, llm: BedrockLLM):
        """Initialize query engine.

        Args:
            config: Configuration object
            db: Database connection
            llm: LLM client
        """
        self.config = config
        self.db = db
        self.llm = llm

    def query(self, question: str, save_as_article: bool = True) -> str:
        """Answer a question by navigating the wiki.

        Args:
            question: User's question
            save_as_article: Whether to save the answer as a wiki article

        Returns:
            Answer text
        """
        # Get index content
        index_content = self._read_index()

        # Build initial prompt with index
        prompt = self._build_query_prompt(question, index_content)

        # Get response
        response = self.llm.complete(prompt, system=QUERY_SYSTEM, max_tokens=8192)

        # Parse response to extract article content
        article_content = self._extract_article(response)

        # Save as article if requested
        if save_as_article and article_content:
            self._save_query_article(question, article_content)

        return response

    def _read_index(self) -> Optional[str]:
        """Read the wiki index.

        Returns:
            Index content or None
        """
        if self.config.index_path.exists():
            with open(self.config.index_path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def _read_article(self, article_path: str) -> Optional[str]:
        """Read a wiki article.

        Args:
            article_path: Relative path to article

        Returns:
            Article content or None
        """
        full_path = self.config.kb_root / article_path
        if full_path.exists():
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def _build_query_prompt(self, question: str, index_content: Optional[str]) -> str:
        """Build the query prompt.

        Args:
            question: User's question
            index_content: Wiki index content

        Returns:
            Formatted prompt
        """
        if index_content:
            prompt = f"""Wiki Index:
{index_content}

---

Question: {question}

Instructions:
1. Review the wiki index to identify relevant articles
2. Read the relevant articles (use [[wikilink]] references from the index)
3. Synthesize an answer to the question
4. Create a complete markdown article that captures the Q&A

The article should:
- Have YAML frontmatter (title should be based on the question, tags, created, sources)
- Provide a comprehensive answer
- Reference the wiki articles consulted with [[wikilinks]]
- Be formatted for future reference

Output a complete markdown article."""

        else:
            prompt = f"""Question: {question}

The wiki is currently empty. Create a starter article that:
- Acknowledges the wiki is being built
- Provides what information you can
- Suggests related topics that should be added

Include YAML frontmatter."""

        return prompt

    def _extract_article(self, response: str) -> Optional[str]:
        """Extract article content from response.

        Args:
            response: LLM response

        Returns:
            Article content or None
        """
        # The response should be a complete article
        # Look for frontmatter
        if "---" in response:
            return response.strip()

        # If no frontmatter, add basic frontmatter
        lines = response.strip().split("\n")
        title = lines[0].strip("#").strip() if lines else "Query Response"

        frontmatter = f"""---
title: {title}
created: {datetime.utcnow().isoformat()}
tags: query, qa
---

{response}"""

        return frontmatter

    def _save_query_article(self, question: str, article_content: str) -> int:
        """Save a query result as a wiki article.

        Args:
            question: Original question
            article_content: Article content

        Returns:
            Article database ID
        """
        # Generate filename from question
        safe_question = re.sub(r"[^\w\s-]", "", question.lower())
        safe_question = re.sub(r"[-\s]+", "-", safe_question)[:50]
        filename = f"qa-{safe_question}.md"

        article_path = self.config.wiki_dir / filename

        # Handle duplicates
        counter = 1
        while article_path.exists():
            article_path = self.config.wiki_dir / f"qa-{safe_question}-{counter}.md"
            counter += 1

        # Write article
        with open(article_path, "w", encoding="utf-8") as f:
            f.write(article_content)

        # Extract title from frontmatter or content
        title = question[:100]  # Default
        if article_content.startswith("---"):
            match = re.search(r"title:\s*(.+)", article_content)
            if match:
                title = match.group(1).strip()

        # Word count
        word_count = len(article_content.split())

        # Add to database
        relative_path = str(article_path.relative_to(self.config.kb_root))
        article_id = self.db.add_article(
            path=relative_path,
            title=title,
            summary=f"Q&A: {question}",
            tags=["query", "qa"],
            word_count=word_count,
        )

        return article_id

    def search_articles(self, search_term: str) -> List[Dict[str, Any]]:
        """Search articles by title or tags.

        Args:
            search_term: Search term

        Returns:
            List of matching articles
        """
        all_articles = self.db.get_all_articles()
        search_lower = search_term.lower()

        matches = []
        for article in all_articles:
            title_match = search_lower in article["title"].lower()
            tags_match = False
            if article.get("tags"):
                tags_match = any(
                    search_lower in tag.lower() for tag in article["tags"].split(",")
                )

            if title_match or tags_match:
                matches.append(article)

        return matches

    def get_article_content(self, article_path: str) -> Optional[str]:
        """Get content of a specific article.

        Args:
            article_path: Relative path to article

        Returns:
            Article content or None
        """
        return self._read_article(article_path)
