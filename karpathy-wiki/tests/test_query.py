"""Tests for query engine."""

import pytest
from pathlib import Path
import tempfile
from unittest.mock import Mock
from kw.config import Config
from kw.db import Database
from kw.llm import BedrockLLM
from kw.query import QueryEngine


@pytest.fixture
def temp_kb():
    """Create a temporary knowledge base."""
    with tempfile.TemporaryDirectory() as tmpdir:
        kb_root = Path(tmpdir)

        (kb_root / "raw").mkdir()
        (kb_root / "wiki").mkdir()

        config = Config(kb_root)
        db = Database(config.db_path)
        db.init_schema()

        yield kb_root, config, db

        db.close()


@pytest.fixture
def mock_llm():
    """Create a mock LLM."""
    llm = Mock(spec=BedrockLLM)
    return llm


def test_query_with_index(temp_kb, mock_llm):
    """Test querying with an existing index."""
    kb_root, config, db = temp_kb
    engine = QueryEngine(config, db, mock_llm)

    # Create an index
    config.index_path.write_text("""# Wiki Index

- [[Test Article]] - About testing
""")

    # Mock LLM response
    mock_llm.complete.return_value = """---
title: Answer to Test Question
tags: query, qa
---

# Answer to Test Question

Based on the wiki, here is the answer...
"""

    response = engine.query("What is testing?", save_as_article=True)

    assert "Answer to Test Question" in response
    assert mock_llm.complete.called

    # Check article was saved
    articles = db.get_all_articles()
    assert len(articles) == 1


def test_query_without_index(temp_kb, mock_llm):
    """Test querying when index doesn't exist."""
    kb_root, config, db = temp_kb
    engine = QueryEngine(config, db, mock_llm)

    mock_llm.complete.return_value = """---
title: Initial Response
---

The wiki is being built...
"""

    response = engine.query("What is this?", save_as_article=False)

    assert "Initial Response" in response


def test_extract_article(temp_kb, mock_llm):
    """Test extracting article from response."""
    kb_root, config, db = temp_kb
    engine = QueryEngine(config, db, mock_llm)

    # Response with frontmatter
    response = """---
title: Test
---

Content here
"""

    article = engine._extract_article(response)
    assert article is not None
    assert "title: Test" in article


def test_search_articles(temp_kb, mock_llm):
    """Test searching articles."""
    kb_root, config, db = temp_kb
    engine = QueryEngine(config, db, mock_llm)

    # Add test articles
    db.add_article("wiki/python.md", "Python Programming", tags=["programming"])
    db.add_article("wiki/java.md", "Java Programming", tags=["programming"])
    db.add_article("wiki/cooking.md", "Cooking Basics", tags=["food"])

    # Search by title
    results = engine.search_articles("python")
    assert len(results) == 1
    assert results[0]["title"] == "Python Programming"

    # Search by tag
    results = engine.search_articles("programming")
    assert len(results) == 2

    # Search with no match
    results = engine.search_articles("nonexistent")
    assert len(results) == 0


def test_save_query_article(temp_kb, mock_llm):
    """Test saving query result as article."""
    kb_root, config, db = temp_kb
    engine = QueryEngine(config, db, mock_llm)

    article_content = """---
title: Query Response
---

# Query Response

Answer content here.
"""

    article_id = engine._save_query_article("What is this?", article_content)

    assert article_id > 0

    article = db.get_article_by_path(f"wiki/qa-what-is-this.md")
    assert article is not None

    # Check file was created
    article_path = config.kb_root / "wiki/qa-what-is-this.md"
    assert article_path.exists()
