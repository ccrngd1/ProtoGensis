"""Tests for compilation engine."""

import pytest
from pathlib import Path
import tempfile
from unittest.mock import Mock, MagicMock
from kw.config import Config
from kw.db import Database
from kw.llm import BedrockLLM
from kw.compiler import Compiler


@pytest.fixture
def temp_kb():
    """Create a temporary knowledge base."""
    with tempfile.TemporaryDirectory() as tmpdir:
        kb_root = Path(tmpdir)

        # Create structure
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


def test_parse_articles_single(temp_kb, mock_llm):
    """Test parsing a single article from LLM response."""
    kb_root, config, db = temp_kb
    compiler = Compiler(config, db, mock_llm)

    response = """---
title: Test Article
tags: test, example
created: 2024-01-01
---

# Test Article

This is a test article with some [[cross-reference]].

## See Also

- [[Related Topic]]

## Sources

- Original source material
"""

    source = {"id": 1, "path": "raw/test.md", "source_type": "markdown"}
    articles = compiler._parse_articles(response, source)

    assert len(articles) == 1
    assert articles[0]["title"] == "Test Article"
    assert articles[0]["tags"] == ["test", "example"]
    assert "test article" in articles[0]["content"].lower()


def test_parse_articles_multiple(temp_kb, mock_llm):
    """Test parsing multiple articles from LLM response."""
    kb_root, config, db = temp_kb
    compiler = Compiler(config, db, mock_llm)

    response = """---
title: Article One
---

Content for article one.

--- ARTICLE ---

---
title: Article Two
---

Content for article two.
"""

    source = {"id": 1, "path": "raw/test.md", "source_type": "markdown"}
    articles = compiler._parse_articles(response, source)

    assert len(articles) == 2
    assert articles[0]["title"] == "Article One"
    assert articles[1]["title"] == "Article Two"


def test_compile_source(temp_kb, mock_llm):
    """Test compiling a source."""
    kb_root, config, db = temp_kb
    compiler = Compiler(config, db, mock_llm)

    # Create a test source file
    source_file = config.raw_dir / "test.txt"
    source_file.write_text("Test content for compilation")

    # Add to database
    source_id = db.add_source(
        path=str(source_file.relative_to(kb_root)),
        source_type="text",
        status="pending",
    )

    # Mock LLM response
    mock_llm.complete.return_value = """---
title: Compiled Article
tags: test
---

# Compiled Article

This article was compiled from the source.
"""

    # Compile
    article_ids = compiler.compile_source(source_id)

    assert len(article_ids) == 1

    # Check article was saved
    articles = db.get_articles_for_source(source_id)
    assert len(articles) == 1
    assert articles[0]["title"] == "Compiled Article"

    # Check source status updated
    source = db.get_source(source_id)
    assert source["status"] == "compiled"


def test_update_index(temp_kb, mock_llm):
    """Test index update."""
    kb_root, config, db = temp_kb
    compiler = Compiler(config, db, mock_llm)

    # Add some articles
    db.add_article("wiki/article1.md", "Article One", tags=["test"])
    db.add_article("wiki/article2.md", "Article Two", tags=["example"])

    # Mock LLM response
    mock_llm.complete.return_value = """# Wiki Index

## Test Articles

- [[Article One]] - A test article
- [[Article Two]] - An example article
"""

    compiler.update_index()

    # Check index was created
    assert config.index_path.exists()
    content = config.index_path.read_text()
    assert "Article One" in content
    assert "Article Two" in content


def test_compilation_failure(temp_kb, mock_llm):
    """Test handling of compilation failure."""
    kb_root, config, db = temp_kb
    compiler = Compiler(config, db, mock_llm)

    # Create a test source
    source_file = config.raw_dir / "test.txt"
    source_file.write_text("Test content")

    source_id = db.add_source(
        path=str(source_file.relative_to(kb_root)),
        source_type="text",
        status="pending",
    )

    # Mock LLM to raise exception
    mock_llm.complete.side_effect = RuntimeError("LLM error")

    # Compilation should fail
    with pytest.raises(RuntimeError):
        compiler.compile_source(source_id)

    # Source should be marked as failed
    source = db.get_source(source_id)
    assert source["status"] == "failed"
