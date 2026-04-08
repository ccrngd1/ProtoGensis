"""Tests for database operations."""

import pytest
from pathlib import Path
import tempfile
from datetime import datetime
from kw.db import Database


@pytest.fixture
def db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    database = Database(db_path)
    database.init_schema()
    yield database
    database.close()
    db_path.unlink()


def test_init_schema(db):
    """Test database schema initialization."""
    cursor = db.conn.cursor()

    # Check that tables exist
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]

    assert "sources" in tables
    assert "articles" in tables
    assert "source_article_map" in tables
    assert "health_reports" in tables


def test_add_source(db):
    """Test adding a source."""
    source_id = db.add_source(
        path="raw/test.pdf",
        source_type="pdf",
        original_url="https://example.com/test.pdf",
        status="pending",
    )

    assert source_id > 0

    source = db.get_source(source_id)
    assert source is not None
    assert source["path"] == "raw/test.pdf"
    assert source["source_type"] == "pdf"
    assert source["status"] == "pending"


def test_get_pending_sources(db):
    """Test retrieving pending sources."""
    # Add sources
    db.add_source("raw/test1.pdf", "pdf", status="pending")
    db.add_source("raw/test2.md", "markdown", status="compiled")
    db.add_source("raw/test3.txt", "text", status="pending")

    pending = db.get_pending_sources()
    assert len(pending) == 2
    assert all(s["status"] == "pending" for s in pending)


def test_update_source_status(db):
    """Test updating source status."""
    source_id = db.add_source("raw/test.pdf", "pdf", status="pending")

    now = datetime.utcnow().isoformat()
    db.update_source_status(source_id, "compiled", now)

    source = db.get_source(source_id)
    assert source["status"] == "compiled"
    assert source["compiled_at"] == now


def test_add_article(db):
    """Test adding an article."""
    article_id = db.add_article(
        path="wiki/test-article.md",
        title="Test Article",
        summary="A test article",
        tags=["test", "example"],
        word_count=100,
    )

    assert article_id > 0

    article = db.get_article_by_path("wiki/test-article.md")
    assert article is not None
    assert article["title"] == "Test Article"
    assert article["tags"] == "test,example"
    assert article["word_count"] == 100


def test_update_article(db):
    """Test updating an article."""
    article_id = db.add_article(
        path="wiki/test.md",
        title="Original Title",
        word_count=100,
    )

    db.update_article(
        article_id,
        title="Updated Title",
        tags=["updated"],
        word_count=200,
    )

    article = db.get_article_by_path("wiki/test.md")
    assert article["title"] == "Updated Title"
    assert article["tags"] == "updated"
    assert article["word_count"] == 200


def test_link_source_to_article(db):
    """Test linking sources to articles."""
    source_id = db.add_source("raw/test.pdf", "pdf")
    article_id = db.add_article("wiki/article.md", "Article")

    db.link_source_to_article(source_id, article_id)

    articles = db.get_articles_for_source(source_id)
    assert len(articles) == 1
    assert articles[0]["id"] == article_id


def test_add_health_report(db):
    """Test adding a health report."""
    report_id = db.add_health_report(
        report_path="wiki/reports/health-20240101.md",
        issues_found=5,
    )

    assert report_id > 0

    report = db.get_latest_health_report()
    assert report is not None
    assert report["issues_found"] == 5


def test_get_stats(db):
    """Test getting knowledge base statistics."""
    # Add test data
    db.add_article("wiki/a1.md", "Article 1", word_count=100)
    db.add_article("wiki/a2.md", "Article 2", word_count=200)
    db.add_source("raw/s1.pdf", "pdf", status="pending")
    db.add_source("raw/s2.md", "markdown", status="compiled")

    stats = db.get_stats()
    assert stats["articles"] == 2
    assert stats["sources_total"] == 2
    assert stats["sources_pending"] == 1
    assert stats["total_words"] == 300
