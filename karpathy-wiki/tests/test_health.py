"""Tests for health checker."""

import pytest
from pathlib import Path
import tempfile
from unittest.mock import Mock
from kw.config import Config
from kw.db import Database
from kw.llm import BedrockLLM
from kw.health import HealthChecker


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


def test_check_broken_links(temp_kb, mock_llm):
    """Test checking for broken wikilinks."""
    kb_root, config, db = temp_kb
    checker = HealthChecker(config, db, mock_llm)

    # Create articles
    article1 = config.wiki_dir / "article1.md"
    article1.write_text("""---
title: Article One
---

See [[Article Two]] and [[NonExistent]].
""")

    article2 = config.wiki_dir / "article2.md"
    article2.write_text("""---
title: Article Two
---

Content here.
""")

    # Add to database
    db.add_article("wiki/article1.md", "Article One")
    db.add_article("wiki/article2.md", "Article Two")

    articles = db.get_all_articles()
    broken_links = checker._check_broken_links(articles)

    # Should find broken link to NonExistent
    assert "wiki/article1.md" in broken_links
    assert "NonExistent" in broken_links["wiki/article1.md"]


def test_parse_health_response(temp_kb, mock_llm):
    """Test parsing health check response."""
    kb_root, config, db = temp_kb
    checker = HealthChecker(config, db, mock_llm)

    # Valid JSON response
    response = """[
    {
        "type": "contradiction",
        "severity": "high",
        "affected_articles": ["wiki/a.md"],
        "description": "Conflicting information",
        "recommendation": "Review and resolve"
    }
]"""

    issues = checker._parse_health_response(response)
    assert len(issues) == 1
    assert issues[0]["type"] == "contradiction"
    assert issues[0]["severity"] == "high"


def test_run_health_check(temp_kb, mock_llm):
    """Test running a complete health check."""
    kb_root, config, db = temp_kb
    checker = HealthChecker(config, db, mock_llm)

    # Create test articles
    db.add_article("wiki/test.md", "Test Article")

    # Mock LLM response
    mock_llm.complete.return_value = """[
    {
        "type": "gap",
        "severity": "medium",
        "affected_articles": [],
        "description": "Missing article on X",
        "recommendation": "Create article on X"
    }
]"""

    results = checker.run_health_check()

    assert results["issues_found"] >= 1
    assert "report_path" in results

    # Check report was saved
    report_path = Path(results["report_path"])
    assert (config.kb_root / report_path).exists()

    # Check database record
    latest_report = db.get_latest_health_report()
    assert latest_report is not None


def test_format_broken_links(temp_kb, mock_llm):
    """Test formatting broken links as issues."""
    kb_root, config, db = temp_kb
    checker = HealthChecker(config, db, mock_llm)

    broken_links = {
        "wiki/article1.md": {"Link1", "Link2"},
        "wiki/article2.md": {"Link3"},
    }

    issues = checker._format_broken_links(broken_links)

    assert len(issues) == 2
    assert all(issue["type"] == "broken_link" for issue in issues)
    assert all(issue["severity"] == "medium" for issue in issues)
